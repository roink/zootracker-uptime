import os

import pytest
from fastapi.testclient import TestClient


def pytest_addoption(parser):
    parser.addoption("--pg", action="store_true", help="run tests that require Postgres")


def pytest_configure(config):
    config.addinivalue_line("markers", "postgres: mark test that requires Postgres")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--pg"):
        return
    skip_pg = pytest.mark.skip(reason="need --pg option to run")
    for item in items:
        if "postgres" in item.keywords:
            item.add_marker(skip_pg)


# set up database url before importing app
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")
os.environ["DATABASE_URL"] = DATABASE_URL
os.environ["AUTH_RATE_LIMIT"] = "1000"
os.environ["GENERAL_RATE_LIMIT"] = "10000"
os.environ.setdefault("SMTP_HOST", "smtp.test")
os.environ.setdefault("CONTACT_EMAIL", "contact@zootracker.app")
os.environ.pop("SMTP_SSL", None)
os.environ.setdefault("ALLOWED_ORIGINS", "http://allowed.example")
os.environ.setdefault(
    "SECRET_KEY",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
)

# ensure a fresh database for every test run when using sqlite
if DATABASE_URL.startswith("sqlite") and os.path.exists("test.db"):
    os.remove("test.db")

from app.database import Base, engine, SessionLocal  # noqa: E402
from app import models  # noqa: E402
from app.triggers import create_triggers  # noqa: E402
from app.db_extensions import ensure_pg_extensions  # noqa: E402
from app.main import app, get_db  # noqa: E402


def override_get_db():
    """Provide a test database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

ensure_pg_extensions(engine)

# ensure a clean schema for every run to avoid duplicate indexes
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
create_triggers(engine)

client = TestClient(app)


@pytest.fixture(scope="session")
def openapi_schema():
    """Build the OpenAPI schema once and cache it for all tests."""
    return app.openapi()


def seed_data():
    """Populate the test database with minimal reference data."""
    db = SessionLocal()
    mammal = models.Category(name="Mammal")
    bird = models.Category(name="Bird")
    db.add_all([mammal, bird])
    db.commit()
    db.refresh(mammal)
    db.refresh(bird)

    europe = models.ContinentName(id=1, name_de="Europa", name_en="Europe")
    america = models.ContinentName(id=2, name_de="Nordamerika", name_en="North America")
    db.add_all([europe, america])
    db.commit()

    germany = models.CountryName(id=1, name_de="Deutschland", name_en="Germany", continent_id=1)
    usa = models.CountryName(id=2, name_de="USA", name_en="United States", continent_id=2)
    db.add_all([germany, usa])
    db.commit()

    zoo = models.Zoo(
        name="Central Zoo",
        address="123 Zoo St",
        latitude=10.0,
        longitude=20.0,
        description_en="A fun place",
        description_de="Ein lustiger Ort",
        city="Metropolis",
        continent_id=1,
        country_id=1,
    )
    db.add(zoo)
    db.commit()
    db.refresh(zoo)

    far_zoo = models.Zoo(
        name="Far Zoo",
        address="456 Distant Rd",
        latitude=50.0,
        longitude=60.0,
        description_en="Too far away",
        description_de="Zu weit entfernt",
        city="Remoteville",
        continent_id=2,
        country_id=2,
    )
    db.add(far_zoo)
    db.commit()
    db.refresh(far_zoo)

    cls = models.ClassName(klasse=1, name_de="Säugetiere", name_en="Mammals")
    ordn = models.OrderName(ordnung=1, name_de="Raubtiere", name_en="Carnivorans")
    fam = models.FamilyName(familie=1, name_de="Katzen", name_en="Cats")
    db.add_all([cls, ordn, fam])
    db.commit()

    animal = models.Animal(
        name_en="Lion",
        scientific_name="Panthera leo",
        category_id=mammal.id,
        default_image_url="http://example.com/lion.jpg",
        name_de="L\u00f6we",
        description_en="King of the jungle",
        description_de="K\u00f6nig der Tiere",
        klasse=1,
        ordnung=1,
        familie=1,
        slug="lion",
    )
    tiger = models.Animal(
        name_en="Tiger",
        scientific_name="Panthera tigris",
        category_id=mammal.id,
        default_image_url="http://example.com/tiger.jpg",
        name_de="Tiger",
        slug="tiger",
    )
    eagle = models.Animal(
        name_en="Eagle",
        scientific_name="Aquila chrysaetos",
        category_id=bird.id,
        default_image_url="http://example.com/eagle.jpg",
        name_de="Adler",
        slug="eagle",
    )
    db.add_all([animal, tiger, eagle])
    db.commit()
    db.refresh(animal)
    db.refresh(tiger)
    db.refresh(eagle)

    img1 = models.Image(
        mid="M1",
        animal_id=animal.id,
        commons_title="File:Lion.jpg",
        commons_page_url="http://commons.org/File:Lion.jpg",
        original_url="http://example.com/lion.jpg",
        width=640,
        height=480,
        size_bytes=1000,
        sha1="0" * 40,
        mime="image/jpeg",
        artist_plain="Jane Smith",
        license="CC BY-SA 4.0",
        license_url="http://creativecommons.org/licenses/by-sa/4.0/",
        source="WIKIDATA_P18",
        variants=[
            models.ImageVariant(
                width=320,
                height=240,
                thumb_url="http://example.com/lion-320.jpg",
            ),
            models.ImageVariant(
                width=640, height=480, thumb_url="http://example.com/lion.jpg"
            ),
        ],
        attribution_required=True,
        credit_line="Photo by Jane",
    )
    img2 = models.Image(
        mid="M2",
        animal_id=animal.id,
        commons_title="File:Lion2.jpg",
        commons_page_url="http://commons.org/File:Lion2.jpg",
        original_url="http://example.com/lion2.jpg",
        width=640,
        height=480,
        size_bytes=2000,
        sha1="1" * 40,
        mime="image/jpeg",
        artist_plain="John Doe",
        license="CC BY-SA 4.0",
        license_url="http://creativecommons.org/licenses/by-sa/4.0/",
        source="WIKIDATA_P18",
        variants=[
            models.ImageVariant(
                width=640, height=480, thumb_url="http://example.com/lion2.jpg"
            )
        ],
    )
    db.add_all([img1, img2])
    db.commit()

    link = models.ZooAnimal(zoo_id=zoo.id, animal_id=animal.id)
    db.add(link)
    db.commit()

    db.close()
    return {
        "zoo": zoo,
        "animal": animal,
        "far_zoo": far_zoo,
        "tiger": tiger,
        "eagle": eagle,
    }


@pytest.fixture(scope="session")
def data():
    """Provide seeded data to tests that need it."""
    records = seed_data()
    yield records


_counter = 0  # used to create unique email addresses


TEST_PASSWORD = "supersecret"


def register_and_login(return_register_resp: bool = False):
    """Create a new user and return an auth token and user id.

    If ``return_register_resp`` is ``True``, also return the response from the
    registration request so tests can inspect the payload returned by the API.
    """
    global _counter
    email = f"alice{_counter}@example.com"
    _counter += 1
    register_resp = client.post(
        "/users",
        json={"name": "Alice", "email": email, "password": TEST_PASSWORD},
    )
    assert register_resp.status_code == 200
    user_id = register_resp.json()["id"]
    login_resp = client.post(
        "/auth/login",
        data={"username": email, "password": TEST_PASSWORD},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    if return_register_resp:
        return token, user_id, register_resp
    return token, user_id
