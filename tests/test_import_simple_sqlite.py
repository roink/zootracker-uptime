from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import import_simple_sqlite_data
from app import models


def _build_source_db(path: Path) -> Path:
    engine = create_engine(f"sqlite:///{path}", future=True)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE animal (
                art TEXT PRIMARY KEY,
                klasse INTEGER,
                ordnung INTEGER,
                familie INTEGER,
                latin_name TEXT,
                zootierliste_description TEXT,
                name_de TEXT,
                name_en TEXT,
                zootierlexikon_link TEXT
            );
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE zoo (
                zoo_id INTEGER PRIMARY KEY,
                continent TEXT,
                country TEXT,
                city TEXT,
                name TEXT,
                latitude REAL,
                longitude REAL,
                website TEXT
            );
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE zoo_animal (
                zoo_id INTEGER,
                art TEXT,
                PRIMARY KEY(zoo_id, art)
            );
            """
        ))
        conn.execute(text("INSERT INTO animal (art, klasse, ordnung, familie, latin_name, name_de, name_en) VALUES ('Panthera leo',1,1,1,'Panthera leo','L\u00f6we','Lion');"))
        conn.execute(text("INSERT INTO animal (art, klasse, ordnung, familie, latin_name, name_de) VALUES ('Aquila chrysaetos',2,1,1,'Aquila chrysaetos','Adler');"))
        conn.execute(text("INSERT INTO animal (art, latin_name) VALUES ('Unknownus testus','Unknownus testus');"))
        conn.execute(text("INSERT INTO zoo (zoo_id, continent, country, city, name, latitude, longitude, website) VALUES (1,'Europe','Germany','Berlin','Berlin Zoo',52.5,13.4,'http://example.org');"))
        conn.execute(text("INSERT INTO zoo_animal (zoo_id, art) VALUES (1,'Panthera leo');"))
        conn.execute(text("INSERT INTO zoo_animal (zoo_id, art) VALUES (1,'Aquila chrysaetos');"))
        conn.execute(text("INSERT INTO zoo_animal (zoo_id, art) VALUES (1,'Unknownus testus');"))
    return path


def test_import_simple_sqlite(monkeypatch, tmp_path):
    src_path = _build_source_db(tmp_path / "src.db")
    target_url = f"sqlite:///{tmp_path}/target.db"
    target_engine = create_engine(target_url, future=True)
    Session = sessionmaker(bind=target_engine)
    monkeypatch.setattr(import_simple_sqlite_data, "SessionLocal", Session)

    # dry run should not write anything
    import_simple_sqlite_data.main(str(src_path), dry_run=True)
    db = Session()
    try:
        assert db.query(models.Animal).count() == 0
        assert db.query(models.Zoo).count() == 0
    finally:
        db.close()

    # real import
    import_simple_sqlite_data.main(str(src_path))

    db = Session()
    try:
        assert db.query(models.Animal).count() == 3
        assert db.query(models.Zoo).count() == 1
        categories = db.query(models.Category).order_by(models.Category.name).all()
        assert [c.name for c in categories] == ["Klasse 1", "Klasse 2", "Uncategorized"]
        zoo = db.query(models.Zoo).first()
        assert zoo.animal_count == 3
        assert zoo.name == "Berlin Zoo"
        assert zoo.country == "Germany"
        assert zoo.city == "Berlin"
        assert float(zoo.latitude) == 52.5
        assert float(zoo.longitude) == 13.4
        lion = db.query(models.Animal).filter_by(scientific_name="Panthera leo").one()
        assert lion.common_name == "L\u00f6we"
        assert lion.name_de == "L\u00f6we"
    finally:
        db.close()

    # idempotent re-run
    import_simple_sqlite_data.main(str(src_path))
    db = Session()
    try:
        assert db.query(models.Animal).count() == 3
        assert db.query(models.Zoo).count() == 1
        assert db.query(models.ZooAnimal).count() == 3
    finally:
        db.close()
