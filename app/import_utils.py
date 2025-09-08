from datetime import datetime, timezone
import re
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from sqlalchemy import types as satypes


def _ensure_animal_columns(dst: Session) -> None:
    """Add missing columns to the `animals` table if absent and fix legacy types."""
    bind = dst.get_bind()
    insp = inspect(bind)
    cols = {c["name"]: c for c in insp.get_columns("animals")}

    # Self-heal older Postgres databases where default_image_url was VARCHAR(512)
    if bind.dialect.name == "postgresql":
        col = cols.get("default_image_url")
        if col and isinstance(col["type"], satypes.String):
            dst.execute(
                text("ALTER TABLE animals ALTER COLUMN default_image_url TYPE TEXT;")
            )
            dst.commit()

    existing = set(cols)
    required = {
        "description_de": "TEXT",
        "description_en": "TEXT",
        "conservation_state": "TEXT",
        "taxon_rank": "TEXT",
    }
    with bind.begin() as conn:
        for name, typ in required.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE animals ADD COLUMN {name} {typ}"))


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
