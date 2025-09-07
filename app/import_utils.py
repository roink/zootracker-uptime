from sqlalchemy import inspect, text
from sqlalchemy.orm import Session


def _ensure_animal_columns(dst: Session) -> None:
    """Add missing columns to the `animals` table if absent (SQLite/Postgres-safe)."""
    engine = dst.get_bind()
    inspector = inspect(engine)
    existing = {col["name"] for col in inspector.get_columns("animals")}
    required = {
        "description_de": "TEXT",
        "description_en": "TEXT",
        "conservation_state": "TEXT",
        "taxon_rank": "TEXT",
    }
    with engine.begin() as conn:
        for name, typ in required.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE animals ADD COLUMN {name} {typ}"))
