"""Utility helpers used when importing legacy datasets.

These functions are used by the data import scripts and some of the tests to
"self-heal" older database dumps.  The original implementation only ensured a
handful of optional columns existed which worked for SQLite based tests but
left the table in an incomplete state when running the PostgreSQL tests.  One
of the tests purposely recreates the ``animals`` table with only two columns and
then calls :func:`_ensure_animal_columns`.  Because only a subset of columns
were restored, subsequent tests failed with ``no such column`` errors.

To make the import helper robust we now compare the existing columns in the
database with the full set defined by :class:`app.models.Animal` and add any
missing ones.  This mirrors what a migration would do and ensures the database
schema matches the ORM model after the function runs.
"""

from datetime import datetime, timezone
import re
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateColumn
from sqlalchemy.exc import ProgrammingError

# ``models`` is imported lazily inside ``_ensure_animal_columns`` to avoid a
# circular import during normal application start-up.


def _ensure_animal_columns(dst: Session) -> None:
    """Add missing columns to the `animals` table if absent and fix legacy types."""
    bind = dst.get_bind()
    insp = inspect(bind)
    cols = {c["name"]: c for c in insp.get_columns("animals")}

    existing = set(cols)

    # Import here to avoid circular imports when this module is loaded by
    # scripts that also import ``models``.
    from . import models

    table = models.Animal.__table__
    indexes = {idx["name"] for idx in insp.get_indexes("animals")}
    art_exists = "art" in existing

    with bind.begin() as conn:
        if art_exists and "idx_animals_art" not in indexes:
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_animals_art ON animals (art)"
                )
            )
        if bind.dialect.name == "postgresql" and "default_image_url" in cols:
            try:
                conn.execute(
                    text(
                        "ALTER TABLE animals ALTER COLUMN default_image_url TYPE TEXT"
                    )
                )
            except ProgrammingError:
                # Already TEXT or not changeable; ignore to keep idempotence.
                pass

        # Add any columns missing from the current ``animals`` table by
        # comparing against the ORM model definition.  ``CreateColumn`` generates
        # the appropriate SQL for the active dialect so types such as UUID work
        # both on SQLite (as TEXT) and PostgreSQL.
        for column in table.columns:
            if column.name not in existing:
                ddl = CreateColumn(column).compile(dialect=bind.dialect)
                conn.execute(text(f"ALTER TABLE animals ADD COLUMN {ddl}"))

    if not art_exists:
        refreshed_indexes = {
            idx["name"] for idx in inspect(bind).get_indexes("animals")
        }
        if "idx_animals_art" not in refreshed_indexes:
            with bind.begin() as conn:
                conn.execute(
                    text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS idx_animals_art ON animals (art)"
                    )
                )


def _ensure_image_columns(dst: Session) -> None:
    """Add missing columns to the `images` table if absent."""

    bind = dst.get_bind()
    insp = inspect(bind)
    if not insp.has_table("images"):
        return
    existing = {c["name"] for c in insp.get_columns("images")}
    required = {
        "width": "INTEGER",
        "height": "INTEGER",
        "size_bytes": "INTEGER",
        "sha1": "TEXT",
        "mime": "TEXT",
        "uploaded_at": "TIMESTAMP",
        "uploader": "TEXT",
        "title": "TEXT",
        "artist_raw": "TEXT",
        "artist_plain": "TEXT",
        "license": "TEXT",
        "license_short": "TEXT",
        "license_url": "TEXT",
        "attribution_required": "BOOLEAN",
        "usage_terms": "TEXT",
        "credit_line": "TEXT",
        "retrieved_at": "TIMESTAMP DEFAULT (CURRENT_TIMESTAMP)",
    }
    with bind.begin() as conn:
        for name, typ in required.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE images ADD COLUMN {name} {typ}"))


def _clean_text(s: str | None) -> str | None:
    """Normalize whitespace and return ``None`` for blank strings."""

    if not s:
        return None
    s = s.replace("\x00", "")
    s = s.replace("\r\n", "\n")
    s = re.sub(r"[ \t\u00A0]+", " ", s)
    s = s.strip()
    return s or None


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO timestamps, returning timezone-aware UTC datetimes."""

    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
