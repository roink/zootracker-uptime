from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app import import_sqlite_data
from app import models


def _build_source_db(path: Path) -> Path:
    engine = create_engine(f"sqlite:///{path}", future=True)
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE animal (
                animal_id INTEGER PRIMARY KEY AUTOINCREMENT,
                klasse INTEGER,
                ordnung INTEGER,
                familie INTEGER,
                art TEXT,
                latin_name TEXT,
                zoo_count INTEGER NOT NULL DEFAULT 0,
                wikidata_id TEXT,
                english_label TEXT,
                german_label TEXT,
                taxon_rank TEXT,
                parent_taxon TEXT,
                wikipedia_en TEXT,
                wikipedia_de TEXT,
                iucn_conservation_status TEXT,
                zootierliste_description TEXT,
                zootierliste_name TEXT,
                english_summary TEXT,
                german_summary TEXT,
                UNIQUE(klasse, ordnung, familie, art, latin_name)
            );
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE zoo (
                zoo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                continent TEXT,
                country TEXT,
                city TEXT,
                name TEXT,
                default_label TEXT,
                label_en TEXT,
                label_de TEXT,
                wikidata_id TEXT,
                UNIQUE(continent, country, city, name)
            );
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE zoo_openAI_descriptions (
                zoo_id INTEGER PRIMARY KEY,
                latitude REAL,
                longitude REAL,
                official_website TEXT,
                wikipedia_en TEXT,
                wikipedia_de TEXT,
                wikidata_id TEXT,
                description_en TEXT,
                description_de TEXT,
                FOREIGN KEY(zoo_id) REFERENCES zoo(zoo_id)
            );
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE zoo_animal (
                zoo_id INTEGER,
                animal_id INTEGER,
                PRIMARY KEY(zoo_id, animal_id)
            );
            """
        ))
        conn.execute(text(
            "INSERT INTO animal (klasse, ordnung, familie, art, latin_name, english_label, german_label, english_summary, german_summary) VALUES (1,1,1,'Lion','Panthera leo','Lion','Löwe','King of the jungle','König des Dschungels');"
        ))
        conn.execute(text(
            "INSERT INTO animal (klasse, ordnung, familie, art, latin_name, english_label, german_label) VALUES (2,1,1,'Eagle','Aquila chrysaetos','Eagle','Adler');"
        ))
        conn.execute(text(
            "INSERT INTO zoo (continent,country,city,name,label_en,label_de) VALUES ('Europe','Germany','Berlin','Berlin Zoo','Berlin Zoo','Berliner Zoo');"
        ))
        conn.execute(text(
            "INSERT INTO zoo_openAI_descriptions (zoo_id,latitude,longitude,official_website,description_en,description_de) VALUES (1,52.5,13.4,'http://example.org','Nice zoo','Schöner Zoo');"
        ))
        conn.execute(text(
            "INSERT INTO zoo_animal (zoo_id,animal_id) VALUES (1,1);"
        ))
        conn.execute(text(
            "INSERT INTO zoo_animal (zoo_id,animal_id) VALUES (1,2);"
        ))
    return path


def test_import_sqlite(monkeypatch, tmp_path):
    src_path = _build_source_db(tmp_path / "src.db")
    target_url = f"sqlite:///{tmp_path}/target.db"
    target_engine = create_engine(target_url, future=True)
    Session = sessionmaker(bind=target_engine)
    monkeypatch.setattr(import_sqlite_data, "SessionLocal", Session)

    import_sqlite_data.main(str(src_path))

    db = Session()
    try:
        assert db.query(models.Animal).count() == 2
        assert db.query(models.Zoo).count() == 1
        categories = db.query(models.Category).order_by(models.Category.name).all()
        assert [c.name for c in categories] == ["Klasse 1", "Klasse 2"]
        zoo = db.query(models.Zoo).first()
        assert zoo.animal_count == 2
        lion = db.query(models.Animal).filter_by(scientific_name="Panthera leo").one()
        assert lion.common_name == "Lion"
        assert lion.zoo_count == 1
    finally:
        db.close()
