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
                latitude REAL,
                longitude REAL,
                official_website TEXT,
                wikipedia_en TEXT,
                wikipedia_de TEXT,
                description_en TEXT,
                description_de TEXT,
                UNIQUE(continent, country, city, name)
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
            """
            CREATE TABLE image (
                mid TEXT PRIMARY KEY,
                animal_id INTEGER NOT NULL,
                commons_title TEXT,
                commons_page_url TEXT,
                original_url TEXT,
                source TEXT
            );
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE image_variant (
                mid TEXT,
                width INTEGER,
                height INTEGER,
                thumb_url TEXT,
                PRIMARY KEY(mid, width)
            );
            """
        ))
        conn.execute(
            text(
                "INSERT INTO animal (klasse, ordnung, familie, art, latin_name, english_label, german_label, english_summary, german_summary, iucn_conservation_status, taxon_rank) VALUES (1,1,1,'Lion','Panthera leo','Lion','Löwe','King of the jungle','König des Dschungels','EN','species');"
            )
        )
        conn.execute(text(
            "INSERT INTO animal (klasse, ordnung, familie, art, latin_name, english_label, german_label) VALUES (2,1,1,'Eagle','Aquila chrysaetos','Eagle','Adler');"
        ))
        conn.execute(
            text(
                "INSERT INTO zoo (continent,country,city,name,default_label,label_en,label_de,latitude,longitude,official_website,description_en,description_de) VALUES ('Europe','Germany','Berlin','Berlin Zoo','Zoo Berlin','Berlin Zoo','Berliner Zoo',52.5,13.4,'http://example.org','Nice zoo','Schöner Zoo');"
            )
        )
        conn.execute(text(
            "INSERT INTO zoo_animal (zoo_id,animal_id) VALUES (1,1);"
        ))
        conn.execute(text(
            "INSERT INTO zoo_animal (zoo_id,animal_id) VALUES (1,2);"
        ))
        conn.execute(text("INSERT INTO image (mid, animal_id, commons_title, commons_page_url, original_url, source) VALUES ('M1',1,'File:Lion.jpg','http://commons.org/File:Lion.jpg','http://example.com/lion.jpg','TEST');"))
        conn.execute(text("INSERT INTO image_variant (mid, width, height, thumb_url) VALUES ('M1',640,480,'http://example.com/lion.jpg');"))
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
        assert zoo.name == "Berlin Zoo"
        assert zoo.label_en == "Berlin Zoo"
        assert zoo.label_de == "Berliner Zoo"
        assert zoo.default_label == "Zoo Berlin"
        lion = db.query(models.Animal).filter_by(scientific_name="Panthera leo").one()
        assert lion.common_name == "Lion"
        assert lion.art == "Lion"
        assert lion.english_label == "Lion"
        assert lion.german_label == "Löwe"
        assert lion.latin_name == "Panthera leo"
        assert lion.zoo_count == 1
        assert lion.conservation_state == "EN"
        assert lion.taxon_rank == "species"
        assert lion.description_en == "King of the jungle"
        assert lion.description_de == "König des Dschungels"
        assert db.query(models.Image).count() == 1
        assert db.query(models.ImageVariant).count() == 1
        assert lion.default_image_url == "http://example.com/lion.jpg"
    finally:
        db.close()


def test_import_sqlite_updates_existing_animals(monkeypatch, tmp_path):
    src_path = _build_source_db(tmp_path / "src.db")
    target_url = f"sqlite:///{tmp_path}/target.db"
    target_engine = create_engine(target_url, future=True)
    Session = sessionmaker(bind=target_engine)
    monkeypatch.setattr(import_sqlite_data, "SessionLocal", Session)

    import_sqlite_data.main(str(src_path))

    # create new source with more metadata for the eagle
    src2_path = _build_source_db(tmp_path / "src2.db")
    engine = create_engine(f"sqlite:///{src2_path}", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE animal SET english_summary='Mighty eagle', german_summary='Mächtiger Adler', iucn_conservation_status='Vulnerable', taxon_rank='species' WHERE latin_name='Aquila chrysaetos'"
            )
        )

    import_sqlite_data.main(str(src2_path))

    db = Session()
    try:
        eagle = db.query(models.Animal).filter_by(scientific_name="Aquila chrysaetos").one()
        assert eagle.description_en == "Mighty eagle"
        assert eagle.description_de == "Mächtiger Adler"
        assert eagle.conservation_state == "VU"
        assert eagle.taxon_rank == "species"
    finally:
        db.close()


def test_import_sqlite_overwrites_when_requested(monkeypatch, tmp_path):
    src_path = _build_source_db(tmp_path / "src.db")
    target_url = f"sqlite:///{tmp_path}/target.db"
    target_engine = create_engine(target_url, future=True)
    Session = sessionmaker(bind=target_engine)
    monkeypatch.setattr(import_sqlite_data, "SessionLocal", Session)

    import_sqlite_data.main(str(src_path))

    src2_path = _build_source_db(tmp_path / "src2.db")
    engine = create_engine(f"sqlite:///{src2_path}", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE animal SET english_summary=' New king ', german_summary=' Neuer König ', iucn_conservation_status='LC' WHERE latin_name='Panthera leo'"
            )
        )

    import_sqlite_data.main(str(src2_path), overwrite=True)

    db = Session()
    try:
        lion = db.query(models.Animal).filter_by(scientific_name="Panthera leo").one()
        assert lion.description_en == "New king"
        assert lion.description_de == "Neuer König"
        assert lion.conservation_state == "LC"
    finally:
        db.close()


def test_import_sqlite_clear_fields_with_overwrite(monkeypatch, tmp_path):
    """Overwrite mode should clear fields when source lacks values."""
    src_path = _build_source_db(tmp_path / "src.db")
    target_url = f"sqlite:///{tmp_path}/target.db"
    target_engine = create_engine(target_url, future=True)
    Session = sessionmaker(bind=target_engine)
    monkeypatch.setattr(import_sqlite_data, "SessionLocal", Session)

    import_sqlite_data.main(str(src_path))

    # new source with missing summaries for the lion
    src2_path = _build_source_db(tmp_path / "src2.db")
    engine = create_engine(f"sqlite:///{src2_path}", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE animal SET english_summary=NULL, german_summary=NULL WHERE latin_name='Panthera leo'"
            )
        )

    import_sqlite_data.main(str(src2_path), overwrite=True)

    db = Session()
    try:
        lion = db.query(models.Animal).filter_by(scientific_name="Panthera leo").one()
        assert lion.description_en is None
        assert lion.description_de is None
    finally:
        db.close()
