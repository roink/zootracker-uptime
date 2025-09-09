import os

import pytest
from sqlalchemy import create_engine, inspect, text, types as satypes
from sqlalchemy.orm import sessionmaker

from app.import_utils import _ensure_animal_columns
from app.database import Base, engine
from app.triggers import create_triggers
from .conftest import seed_data


@pytest.mark.postgres

def test_ensure_animal_columns_widens_default_image_url():
    tmp_engine = create_engine(os.environ["DATABASE_URL"], future=True)
    with tmp_engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS animals"))
        conn.execute(
            text(
                "CREATE TABLE animals (id UUID PRIMARY KEY, default_image_url VARCHAR(512))"
            )
        )
    Session = sessionmaker(bind=tmp_engine)
    db = Session()
    try:
        _ensure_animal_columns(db)
    finally:
        db.close()
    insp = inspect(tmp_engine)
    col = next(
        c for c in insp.get_columns("animals") if c["name"] == "default_image_url"
    )
    assert isinstance(col["type"], satypes.Text)

    # Restore the database schema and reference data for subsequent tests.
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    create_triggers(engine)
    seed_data()
