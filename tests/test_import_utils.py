import os
import uuid

import pytest
from sqlalchemy import create_engine, inspect, text, types as satypes
from sqlalchemy.orm import sessionmaker

from app.import_utils import _ensure_animal_columns


@pytest.mark.postgres
def test_ensure_animal_columns_widens_default_image_url():
    tmp_engine = create_engine(os.environ["DATABASE_URL"], future=True)
    schema = f"tmp_{uuid.uuid4().hex}"
    with tmp_engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
        conn.execute(text(f"SET search_path TO {schema}"))
        conn.execute(
            text(
                "CREATE TABLE animals (id UUID PRIMARY KEY, default_image_url VARCHAR(512))"
            )
        )

    Session = sessionmaker(bind=tmp_engine)
    db = Session()
    try:
        db.execute(text(f"SET search_path TO {schema}"))
        _ensure_animal_columns(db)
    finally:
        db.close()

    insp = inspect(tmp_engine)
    col = next(
        c
        for c in insp.get_columns("animals", schema=schema)
        if c["name"] == "default_image_url"
    )
    assert isinstance(col["type"], satypes.Text)

    with tmp_engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
