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
