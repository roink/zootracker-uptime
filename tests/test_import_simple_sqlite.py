from pathlib import Path

from datetime import datetime
import uuid

import pytest
from sqlalchemy import MetaData, create_engine, text, event
from sqlalchemy.orm import sessionmaker

from app import import_simple_sqlite_data
from app import models
from app.database import Base, engine as app_engine
from app.db_extensions import ensure_pg_extensions
from app.triggers import create_triggers


pytestmark = pytest.mark.postgres


@pytest.fixture
def session_factory(monkeypatch):
    schema = f"import_test_{uuid.uuid4().hex}"
    with app_engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(
        app_engine.url.render_as_string(hide_password=False),
        future=True,
        connect_args={"options": f"-c search_path={schema},public"},
    )

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute(f'SET search_path TO "{schema}", public')
        cursor.close()

    Session = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False
    )
    monkeypatch.setattr(import_simple_sqlite_data, "SessionLocal", Session)

    ensure_pg_extensions(engine)

    metadata = MetaData()
    for table in Base.metadata.tables.values():
        table.to_metadata(metadata, schema=schema)
    metadata.create_all(bind=engine, checkfirst=False)
    create_triggers(engine)
    yield Session
    engine.dispose()
    with app_engine.begin() as conn:
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))


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
                parent_art TEXT,
                latin_name TEXT,
                normalized_latin_name TEXT,
                zootierliste_description TEXT,
                name_de TEXT,
                name_en TEXT,
                slug TEXT UNIQUE,
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
            CREATE TABLE continent_name (
                id INTEGER PRIMARY KEY,
                name_de TEXT NOT NULL UNIQUE,
                name_en TEXT
            );
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE country_name (
                id INTEGER PRIMARY KEY,
                name_de TEXT NOT NULL UNIQUE,
                name_en TEXT,
                continent_id INTEGER REFERENCES continent_name(id)
            );
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE zoo (
                zoo_id INTEGER PRIMARY KEY,
                continent INTEGER REFERENCES continent_name(id),
                country INTEGER REFERENCES country_name(id),
                city TEXT,
                name TEXT,
                slug TEXT UNIQUE,
                latitude REAL,
                longitude REAL,
                latitude_google REAL,
                longitude_google REAL,
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
        conn.execute(text(
            """
            CREATE TABLE klasse_name (
                klasse INTEGER PRIMARY KEY,
                name_de TEXT,
                name_en TEXT
            );
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE ordnung_name (
                ordnung INTEGER PRIMARY KEY,
                name_de TEXT,
                name_en TEXT
            );
            """
        ))
        conn.execute(text(
            """
            CREATE TABLE familie_name (
                familie INTEGER PRIMARY KEY,
                name_de TEXT,
                name_en TEXT
            );
            """
        ))
        conn.execute(
            text(
                "INSERT INTO animal (art, klasse, ordnung, familie, parent_art, latin_name, normalized_latin_name, name_de, name_en, slug, description_de, description_en, iucn_conservation_status, taxon_rank) VALUES ('1001',1,1,1,NULL,'Panthera leo','Panthera leo','L\u00f6we','Lion','lion','Deutsche Beschreibung','English description','VU','species');"
            )
        )
        conn.execute(
            text(
                "INSERT INTO animal (art, klasse, ordnung, familie, parent_art, latin_name, normalized_latin_name, name_de, name_en, slug) VALUES ('2001',2,1,1,'1001','Aquila chrysaetos','Aquila chrysaetos','Adler','Golden Eagle','golden-eagle');"
            )
        )
        conn.execute(
            text(
                "INSERT INTO animal (art, latin_name, normalized_latin_name, parent_art, zootierliste_description, name_en, slug) VALUES ('1002','Unknownus testus','Unknownus testus','1001','Legacy description','Unknownus Testus','unknownus-testus');"
            )
        )
        conn.execute(text("INSERT INTO continent_name (id, name_de, name_en) VALUES (1,'Europa','Europe');"))
        conn.execute(text("INSERT INTO country_name (id, name_de, name_en, continent_id) VALUES (1,'Deutschland','Germany',1);"))
        conn.execute(
            text(
                "INSERT INTO zoo (zoo_id, continent, country, city, name, slug, latitude, longitude, latitude_google, longitude_google, website, description_en, description_de) VALUES (1,1,1,'Berlin','Berlin Zoo','berlin-zoo',52.5,13.4,52.55,13.45,'http://example.org','English zoo','Deutscher Zoo');"
            )
        )
        conn.execute(text("INSERT INTO zoo_animal (zoo_id, art) VALUES (1,'1001');"))
        conn.execute(text("INSERT INTO zoo_animal (zoo_id, art) VALUES (1,'2001');"))
        conn.execute(text("INSERT INTO zoo_animal (zoo_id, art) VALUES (1,'1002');"))
        conn.execute(text("INSERT INTO klasse_name (klasse, name_de, name_en) VALUES (1,'S\u00e4ugetiere','Mammals');"))
        conn.execute(text("INSERT INTO klasse_name (klasse, name_de, name_en) VALUES (2,'V\u00f6gel','Birds');"))
        conn.execute(text("INSERT INTO ordnung_name (ordnung, name_de, name_en) VALUES (1,'Raubtiere','Carnivorans');"))
        conn.execute(text("INSERT INTO familie_name (familie, name_de, name_en) VALUES (1,'Katzen','Cats');"))
        conn.execute(
            text(
                """
            INSERT INTO image (
                mid, animal_art, commons_title, commons_page_url, original_url,
                width, height, size_bytes, sha1, mime, uploaded_at, uploader, title,
                artist_raw, artist_plain, license, license_short, license_url,
                attribution_required, usage_terms, credit_line, source, retrieved_at
            ) VALUES (
                :mid, '1001', 'File:Lion.jpg', 'http://commons.org/File:Lion.jpg',
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


def test_import_simple_sqlite(tmp_path, session_factory):
    src_path = _build_source_db(tmp_path / "src.db")

    # dry run should not write anything
    import_simple_sqlite_data.main(str(src_path), dry_run=True)
    with session_factory() as db:
        assert db.query(models.Animal).count() == 0
        assert db.query(models.Zoo).count() == 0

    # real import
    import_simple_sqlite_data.main(str(src_path))

    with session_factory() as db:
        assert db.query(models.Animal).count() == 3
        assert db.query(models.Zoo).count() == 1
        assert db.query(models.ContinentName).count() == 1
        assert db.query(models.CountryName).count() == 1
        categories = db.query(models.Category).order_by(models.Category.name).all()
        assert [c.name for c in categories] == ["Klasse 1", "Klasse 2", "Uncategorized"]
        zoo = db.query(models.Zoo).first()
        assert zoo.animal_count == 3
        assert zoo.name == "Berlin Zoo"
        assert zoo.slug == "berlin-zoo"
        assert zoo.country_id == 1
        assert zoo.country.name_en == "Germany"
        assert zoo.continent_id == 1
        assert zoo.continent.name_en == "Europe"
        assert zoo.city == "Berlin"
        assert float(zoo.latitude) == 52.55
        assert float(zoo.longitude) == 13.45
        assert zoo.description_en == "English zoo"
        assert zoo.description_de == "Deutscher Zoo"
        lion = db.query(models.Animal).filter_by(scientific_name="Panthera leo").one()
        assert lion.name_en == "Lion"
        assert lion.name_de == "L\u00f6we"
        assert lion.description_de == "Deutsche Beschreibung"
        assert lion.description_en == "English description"
        assert lion.conservation_state == "VU"
        assert lion.taxon_rank == "species"
        assert lion.slug == "lion"
        assert lion.parent_art is None
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
        assert unknown.parent_art == 1001
        eagle = db.query(models.Animal).filter_by(scientific_name="Aquila chrysaetos").one()
        assert eagle.parent_art == 1001
        cls = db.query(models.ClassName).filter_by(klasse=1).one()
        assert cls.name_en == "Mammals"
        ordn = db.query(models.OrderName).filter_by(ordnung=1).one()
        assert ordn.name_de == "Raubtiere"
        fam = db.query(models.FamilyName).filter_by(familie=1).one()
        assert fam.name_en == "Cats"

    # idempotent re-run
    import_simple_sqlite_data.main(str(src_path))
    with session_factory() as db:
        assert db.query(models.Animal).count() == 3
        assert db.query(models.Zoo).count() == 1
        assert db.query(models.ZooAnimal).count() == 3


def test_import_simple_sqlite_uses_fallback_coordinates(tmp_path, session_factory):
    src_path = _build_source_db(tmp_path / "fallback.db")
    override_engine = create_engine(f"sqlite:///{src_path}", future=True)
    with override_engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE zoo SET latitude=48.1, longitude=11.6, latitude_google=52.55, longitude_google=NULL WHERE zoo_id=1"
            )
        )

    import_simple_sqlite_data.main(str(src_path))

    with session_factory() as db:
        zoo = db.query(models.Zoo).first()
        assert float(zoo.latitude) == pytest.approx(48.1)
        assert float(zoo.longitude) == pytest.approx(11.6)


def test_skip_banned_mid(tmp_path, session_factory):
    src_path = _build_source_db(tmp_path / "src.db", mid="M1723980")
    import_simple_sqlite_data.main(str(src_path))
    with session_factory() as db:
        assert db.query(models.Image).count() == 0
        assert db.query(models.ImageVariant).count() == 0


def test_import_simple_updates_existing_animals(tmp_path, session_factory):
    src_path = _build_source_db(tmp_path / "src.db")
    import_simple_sqlite_data.main(str(src_path))

    # build new source with extra metadata for the eagle
    src2_path = _build_source_db(tmp_path / "src2.db")
    engine = create_engine(f"sqlite:///{src2_path}", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE animal SET description_de=:de, description_en=:en, iucn_conservation_status='Endangered', taxon_rank='species' WHERE art='2001'"
            ),
            {"de": " Neue Beschreibung \x00", "en": "New description\r\n"},
        )
        conn.execute(
            text(
                "UPDATE animal SET parent_art='2001' WHERE art='1002'"
            )
        )

    import_simple_sqlite_data.main(str(src2_path))

    with session_factory() as db:
        eagle = db.query(models.Animal).filter_by(scientific_name="Aquila chrysaetos").one()
        assert eagle.description_de == "Neue Beschreibung"
        assert eagle.description_en == "New description"
        assert eagle.conservation_state == "EN"
        assert eagle.taxon_rank == "species"
        unknown = db.query(models.Animal).filter_by(scientific_name="Unknownus testus").one()
        assert unknown.parent_art == 1001


def test_import_simple_overwrites_when_requested(tmp_path, session_factory):
    src_path = _build_source_db(tmp_path / "src.db")
    import_simple_sqlite_data.main(str(src_path))

    src2_path = _build_source_db(tmp_path / "src2.db")
    engine = create_engine(f"sqlite:///{src2_path}", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE animal SET description_de=' Neue Beschreibung ' WHERE art='1001'"
            )
        )
        conn.execute(
            text(
                "UPDATE animal SET parent_art=NULL WHERE art='1002'"
            )
        )

    import_simple_sqlite_data.main(str(src2_path), overwrite=True)

    with session_factory() as db:
        lion = db.query(models.Animal).filter_by(scientific_name="Panthera leo").one()
        assert lion.description_de == "Neue Beschreibung"
        unknown = db.query(models.Animal).filter_by(scientific_name="Unknownus testus").one()
        assert unknown.parent_art is None


def test_import_simple_clear_fields_with_overwrite(tmp_path, session_factory):
    """Overwriting with missing values should clear existing text."""
    src_path = _build_source_db(tmp_path / "src.db")
    import_simple_sqlite_data.main(str(src_path))

    # new source where the lion has no description_de
    src2_path = _build_source_db(tmp_path / "src2.db")
    engine = create_engine(f"sqlite:///{src2_path}", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE animal SET description_de=NULL WHERE art='1001'"
            )
        )

    import_simple_sqlite_data.main(str(src2_path), overwrite=True)

    with session_factory() as db:
        lion = db.query(models.Animal).filter_by(scientific_name="Panthera leo").one()
        assert lion.description_de is None


def test_import_simple_updates_existing_zoo(tmp_path, session_factory):
    src_path = _build_source_db(tmp_path / "src.db")
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

    with session_factory() as db:
        zoo = db.query(models.Zoo).one()
        assert zoo.description_en == "New EN"
        assert zoo.description_de == "Neue DE"

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

    with session_factory() as db:
        zoo = db.query(models.Zoo).one()
        assert zoo.description_en == "New EN"
        assert zoo.description_de == "Neue DE"


def test_import_skips_animals_without_zoo(tmp_path, session_factory):
    src_path = _build_source_db(tmp_path / "src.db")
    engine = create_engine(f"sqlite:///{src_path}", future=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO animal (art, klasse, ordnung, familie, latin_name, normalized_latin_name, name_de, name_en) "
                "VALUES ('Lonelyus testus',1,1,1,'Lonelyus testus','Lonelyus testus','Lonelyus','Lonelyus');"
            )
        )

    import_simple_sqlite_data.main(str(src_path))

    with session_factory() as db:
        assert (
            db.query(models.Animal)
            .filter_by(scientific_name="Lonelyus testus")
            .first()
            is None
        )
        assert db.query(models.Animal).count() == 3
