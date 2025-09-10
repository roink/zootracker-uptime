from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from datetime import datetime

from app import import_simple_sqlite_data
from app import models


def _build_source_db(path: Path, mid: str = "M1") -> Path:
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
                zootierlexikon_link TEXT,
                description_en TEXT,
                description_de TEXT,
                iucn_conservation_status TEXT,
                taxon_rank TEXT
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
                website TEXT,
                description_en TEXT,
                description_de TEXT
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
        conn.execute(text(
            """
            CREATE TABLE image (
                mid TEXT PRIMARY KEY,
                animal_art TEXT NOT NULL,
                commons_title TEXT NOT NULL,
                commons_page_url TEXT NOT NULL,
                original_url TEXT NOT NULL,
                width INTEGER NOT NULL,
                height INTEGER NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha1 TEXT NOT NULL,
                mime TEXT NOT NULL,
                uploaded_at TEXT,
                uploader TEXT,
                title TEXT,
                artist_raw TEXT,
                artist_plain TEXT,
                license TEXT,
                license_short TEXT,
                license_url TEXT,
                attribution_required INTEGER,
                usage_terms TEXT,
                credit_line TEXT,
                source TEXT NOT NULL,
                retrieved_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
                UNIQUE(commons_title)
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
                "INSERT INTO animal (art, klasse, ordnung, familie, latin_name, name_de, name_en, description_de, description_en, iucn_conservation_status, taxon_rank) VALUES ('Panthera leo',1,1,1,'Panthera leo','L\u00f6we','Lion','Deutsche Beschreibung','English description','VU','species');"
            )
        )
        conn.execute(text("INSERT INTO animal (art, klasse, ordnung, familie, latin_name, name_de) VALUES ('Aquila chrysaetos',2,1,1,'Aquila chrysaetos','Adler');"))
        conn.execute(
            text(
                "INSERT INTO animal (art, latin_name, zootierliste_description) VALUES ('Unknownus testus','Unknownus testus','Legacy description');"
            )
        )
        conn.execute(text("INSERT INTO zoo (zoo_id, continent, country, city, name, latitude, longitude, website, description_en, description_de) VALUES (1,'Europe','Germany','Berlin','Berlin Zoo',52.5,13.4,'http://example.org','English zoo','Deutscher Zoo');"))
        conn.execute(text("INSERT INTO zoo_animal (zoo_id, art) VALUES (1,'Panthera leo');"))
        conn.execute(text("INSERT INTO zoo_animal (zoo_id, art) VALUES (1,'Aquila chrysaetos');"))
        conn.execute(text("INSERT INTO zoo_animal (zoo_id, art) VALUES (1,'Unknownus testus');"))
        conn.execute(
            text(
                """
            INSERT INTO image (
                mid, animal_art, commons_title, commons_page_url, original_url,
                width, height, size_bytes, sha1, mime, uploaded_at, uploader, title,
                artist_raw, artist_plain, license, license_short, license_url,
                attribution_required, usage_terms, credit_line, source, retrieved_at
            ) VALUES (
                :mid, 'Panthera leo', 'File:Lion.jpg', 'http://commons.org/File:Lion.jpg',
                'http://example.com/lion.jpg', 1000, 800, 12345,
                '0123456789abcdef0123456789abcdef01234567',
                'image/jpeg', '2024-01-01T00:00:00Z', ' User:Example \n', ' Lion ',
                'Raw Artist\n', ' Plain Artist ', ' CC BY-SA 4.0 ', ' CC-BY-SA-4.0 ',
                ' https://creativecommons.org/licenses/by-sa/4.0/ ', 1, ' Some terms\r\n',
                ' Credit line ', 'WIKIDATA_P18', '2024-01-02T00:00:00Z'
            );
        """,
            ),
            {"mid": mid},
        )
        conn.execute(
            text(
                "INSERT INTO image_variant (mid, width, height, thumb_url) VALUES (:mid,640,480,'http://example.com/lion.jpg');"
            ),
            {"mid": mid},
        )
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
        assert zoo.description_en == "English zoo"
        assert zoo.description_de == "Deutscher Zoo"
        lion = db.query(models.Animal).filter_by(scientific_name="Panthera leo").one()
        assert lion.name_en == "Lion"
        assert lion.name_de == "L\u00f6we"
        assert lion.description_de == "Deutsche Beschreibung"
        assert lion.description_en == "English description"
        assert lion.conservation_state == "VU"
        assert lion.taxon_rank == "species"
        assert db.query(models.Image).count() == 1
        assert db.query(models.ImageVariant).count() == 1
        assert lion.default_image_url == "http://example.com/lion.jpg"
        image = db.query(models.Image).filter_by(mid="M1").one()
        assert image.width == 1000
        assert image.height == 800
        assert image.size_bytes == 12345
        assert image.sha1 == "0123456789abcdef0123456789abcdef01234567"
        assert image.mime == "image/jpeg"
        assert image.uploaded_at == datetime(2024, 1, 1, tzinfo=image.uploaded_at.tzinfo)
        assert image.uploader == "User:Example"
        assert image.title == "Lion"
        assert image.artist_raw == "Raw Artist"
        assert image.artist_plain == "Plain Artist"
        assert image.license == "CC BY-SA 4.0"
        assert image.license_short == "CC-BY-SA-4.0"
        assert image.license_url == "https://creativecommons.org/licenses/by-sa/4.0/"
        assert image.attribution_required is True
        assert image.usage_terms == "Some terms"
        assert image.credit_line == "Credit line"
        assert image.retrieved_at == datetime(2024, 1, 2, tzinfo=image.retrieved_at.tzinfo)
        unknown = db.query(models.Animal).filter_by(scientific_name="Unknownus testus").one()
        assert unknown.description_de is None
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


def test_skip_banned_mid(monkeypatch, tmp_path):
    src_path = _build_source_db(tmp_path / "src.db", mid="M1723980")
    target_url = f"sqlite:///{tmp_path}/target.db"
    target_engine = create_engine(target_url, future=True)
    Session = sessionmaker(bind=target_engine)
    monkeypatch.setattr(import_simple_sqlite_data, "SessionLocal", Session)
    import_simple_sqlite_data.main(str(src_path))
    db = Session()
    try:
        assert db.query(models.Image).count() == 0
        assert db.query(models.ImageVariant).count() == 0
    finally:
        db.close()


def test_import_simple_updates_existing_animals(monkeypatch, tmp_path):
    src_path = _build_source_db(tmp_path / "src.db")
    target_url = f"sqlite:///{tmp_path}/target.db"
    target_engine = create_engine(target_url, future=True)
    Session = sessionmaker(bind=target_engine)
    monkeypatch.setattr(import_simple_sqlite_data, "SessionLocal", Session)

    import_simple_sqlite_data.main(str(src_path))

    # build new source with extra metadata for the eagle
    src2_path = _build_source_db(tmp_path / "src2.db")
    engine = create_engine(f"sqlite:///{src2_path}", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE animal SET description_de=:de, description_en=:en, iucn_conservation_status='Endangered', taxon_rank='species' WHERE art='Aquila chrysaetos'"
            ),
            {"de": " Neue Beschreibung \x00", "en": "New description\r\n"},
        )

    import_simple_sqlite_data.main(str(src2_path))

    db = Session()
    try:
        eagle = db.query(models.Animal).filter_by(scientific_name="Aquila chrysaetos").one()
        assert eagle.description_de == "Neue Beschreibung"
        assert eagle.description_en == "New description"
        assert eagle.conservation_state == "EN"
        assert eagle.taxon_rank == "species"
    finally:
        db.close()


def test_import_simple_overwrites_when_requested(monkeypatch, tmp_path):
    src_path = _build_source_db(tmp_path / "src.db")
    target_url = f"sqlite:///{tmp_path}/target.db"
    target_engine = create_engine(target_url, future=True)
    Session = sessionmaker(bind=target_engine)
    monkeypatch.setattr(import_simple_sqlite_data, "SessionLocal", Session)

    import_simple_sqlite_data.main(str(src_path))

    src2_path = _build_source_db(tmp_path / "src2.db")
    engine = create_engine(f"sqlite:///{src2_path}", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE animal SET description_de=' Neue Beschreibung ' WHERE art='Panthera leo'"
            )
        )

    import_simple_sqlite_data.main(str(src2_path), overwrite=True)

    db = Session()
    try:
        lion = db.query(models.Animal).filter_by(scientific_name="Panthera leo").one()
        assert lion.description_de == "Neue Beschreibung"
    finally:
        db.close()


def test_import_simple_clear_fields_with_overwrite(monkeypatch, tmp_path):
    """Overwriting with missing values should clear existing text."""
    src_path = _build_source_db(tmp_path / "src.db")
    target_url = f"sqlite:///{tmp_path}/target.db"
    target_engine = create_engine(target_url, future=True)
    Session = sessionmaker(bind=target_engine)
    monkeypatch.setattr(import_simple_sqlite_data, "SessionLocal", Session)

    import_simple_sqlite_data.main(str(src_path))

    # new source where the lion has no description_de
    src2_path = _build_source_db(tmp_path / "src2.db")
    engine = create_engine(f"sqlite:///{src2_path}", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE animal SET description_de=NULL WHERE art='Panthera leo'"
            )
        )

    import_simple_sqlite_data.main(str(src2_path), overwrite=True)

    db = Session()
    try:
        lion = db.query(models.Animal).filter_by(scientific_name="Panthera leo").one()
        assert lion.description_de is None
    finally:
        db.close()


def test_import_simple_updates_existing_zoo(monkeypatch, tmp_path):
    src_path = _build_source_db(tmp_path / "src.db")
    target_url = f"sqlite:///{tmp_path}/target.db"
    target_engine = create_engine(target_url, future=True)
    Session = sessionmaker(bind=target_engine)
    monkeypatch.setattr(import_simple_sqlite_data, "SessionLocal", Session)

    import_simple_sqlite_data.main(str(src_path))

    src2_path = _build_source_db(tmp_path / "src2.db")
    engine = create_engine(f"sqlite:///{src2_path}", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE zoo SET description_en=:en, description_de=:de WHERE zoo_id=1"
            ),
            {"en": " New EN \x00", "de": " Neue DE\r\n"},
        )

    import_simple_sqlite_data.main(str(src2_path))

    db = Session()
    try:
        zoo = db.query(models.Zoo).one()
        assert zoo.description_en == "New EN"
        assert zoo.description_de == "Neue DE"
    finally:
        db.close()

    # incoming empty descriptions should not overwrite existing text
    src3_path = _build_source_db(tmp_path / "src3.db")
    engine3 = create_engine(f"sqlite:///{src3_path}", future=True)
    with engine3.begin() as conn:
        conn.execute(
            text(
                "UPDATE zoo SET description_en=:en, description_de=:de WHERE zoo_id=1"
            ),
            {"en": "", "de": None},
        )
    import_simple_sqlite_data.main(str(src3_path))

    db = Session()
    try:
        zoo = db.query(models.Zoo).one()
        assert zoo.description_en == "New EN"
        assert zoo.description_de == "Neue DE"
    finally:
        db.close()
