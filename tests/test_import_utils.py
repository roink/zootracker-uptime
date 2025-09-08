import os

import pytest
from sqlalchemy import create_engine, inspect, text, types as satypes
from sqlalchemy.orm import sessionmaker

from app.import_utils import _ensure_animal_columns


@pytest.mark.postgres

def test_ensure_animal_columns_widens_default_image_url():
    engine = create_engine(os.environ["DATABASE_URL"], future=True)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS animals"))
        conn.execute(
            text(
                "CREATE TABLE animals (id UUID PRIMARY KEY, default_image_url VARCHAR(512))"
            )
        )
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        _ensure_animal_columns(db)
    finally:
        db.close()
    insp = inspect(engine)
    col = next(c for c in insp.get_columns("animals") if c["name"] == "default_image_url")
    assert isinstance(col["type"], satypes.Text)
