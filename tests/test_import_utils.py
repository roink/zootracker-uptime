import os
import uuid

import pytest
from sqlalchemy import inspect, text, types as satypes
from sqlalchemy.orm import sessionmaker

from app.database import make_sync_engine
from app.import_utils import _ensure_animal_columns


@pytest.mark.postgres
async def test_ensure_animal_columns_widens_default_image_url(client):
    tmp_engine = make_sync_engine(os.environ["DATABASE_URL"])
    if tmp_engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL database required for this test")

    schema = f"tmp_{uuid.uuid4().hex}"
    with tmp_engine.begin() as conn:
        conn.execute(text(f"CREATE SCHEMA {schema}"))
        conn.execute(
            text(
                f"CREATE TABLE {schema}.animals (id UUID PRIMARY KEY, default_image_url VARCHAR(512))"
            )
        )

    scoped_engine = tmp_engine.execution_options(
        schema_translate_map={None: schema}
    )
    Session = sessionmaker(bind=scoped_engine)
    db = Session()
    try:
        _ensure_animal_columns(db)
    finally:
        db.close()

    insp = inspect(scoped_engine)
    col = next(
        c for c in insp.get_columns("animals") if c["name"] == "default_image_url"
    )
    assert isinstance(col["type"], satypes.Text)

    with tmp_engine.begin() as conn:
        conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))

    tmp_engine.dispose()
