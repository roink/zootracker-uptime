import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dotenv import load_dotenv


def pytest_addoption(parser):
    parser.addoption("--pg", action="store_true", help="legacy option; no longer required")


def pytest_configure(config):
    config.addinivalue_line("markers", "postgres: mark test that requires Postgres")


def pytest_collection_modifyitems(config, items):
    """Legacy hook retained for compatibility with the old --pg option."""
    # The test suite now always runs against PostgreSQL, so the collection phase
    # no longer needs to skip any tests. Keeping the hook avoids breaking users
    # that still pass --pg out of habit while making the flag a no-op.
    config.getoption("--pg", default=False)


# Load environment configuration from a local .env file if present so developers
# can point the test suite at their own database without exporting variables
# manually. The repository ships a .env.example template in the project root, so
# we look for a sibling `.env` file relative to this test module.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
dotenv_path = PROJECT_ROOT / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path, override=False)

# The pytest suite relies on specific security header and CORS behaviour. Local
# `.env` files used for manual testing often disable or narrow those settings,
# so normalise the values after loading environment variables. This preserves a
# developer's custom database credentials while keeping the tests deterministic.
# Keep this default in sync with `app.config.DEFAULT_STRICT_TRANSPORT_SECURITY`.
_DEFAULT_STRICT_TRANSPORT_SECURITY = "max-age=63072000; includeSubDomains; preload"

_strict_transport_security = os.getenv("STRICT_TRANSPORT_SECURITY")
if _strict_transport_security is None:
    os.environ["STRICT_TRANSPORT_SECURITY"] = _DEFAULT_STRICT_TRANSPORT_SECURITY
else:
    normalised_sts = _strict_transport_security.strip()
    if not normalised_sts:
        os.environ["STRICT_TRANSPORT_SECURITY"] = _DEFAULT_STRICT_TRANSPORT_SECURITY
    else:
        os.environ["STRICT_TRANSPORT_SECURITY"] = normalised_sts

_ALLOWED_ORIGIN = "http://allowed.example"
existing_origins = os.getenv("ALLOWED_ORIGINS")
if existing_origins:
    origins = [origin.strip() for origin in existing_origins.split(",") if origin.strip()]
    if _ALLOWED_ORIGIN not in origins:
        origins.append(_ALLOWED_ORIGIN)
    os.environ["ALLOWED_ORIGINS"] = ",".join(origins)
else:
    os.environ["ALLOWED_ORIGINS"] = _ALLOWED_ORIGIN

# set up database url before importing app
DEFAULT_TEST_DATABASE_URL = (
    "postgresql://zootracker_test:zootracker_test@localhost:5432/zootracker_test"
)
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_TEST_DATABASE_URL)

if not DATABASE_URL.startswith("postgresql"):
    raise RuntimeError("Tests require a PostgreSQL database")

os.environ["DATABASE_URL"] = DATABASE_URL
os.environ.setdefault("APP_ENV", "test")
os.environ["AUTH_RATE_LIMIT"] = "1000"
os.environ["GENERAL_RATE_LIMIT"] = "10000"
os.environ.setdefault("SMTP_HOST", "smtp.test")
os.environ.setdefault("CONTACT_EMAIL", "contact@zootracker.app")
os.environ.pop("SMTP_SSL", None)
os.environ.setdefault(
    "SECRET_KEY",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
)
os.environ.setdefault("JWT_SECRET", os.environ["SECRET_KEY"])
os.environ.setdefault("TOKEN_PEPPER", "unit-test-pepper")
os.environ.setdefault("COOKIE_SECURE", "false")

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
        slug="central-zoo",
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
        slug="far-zoo",
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
    client.cookies.clear()
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
    body = login_resp.json()
    assert "expires_in" in body
    token = body["access_token"]
    if return_register_resp:
        return token, user_id, register_resp
    return token, user_id
