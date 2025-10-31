import os
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport
from sqlalchemy import delete, select


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


# The pytest suite relies on specific security header and CORS behaviour. Local
# environment overrides used for manual testing often disable or narrow those settings,
# so normalise the values before the app initialises. This preserves a
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
# Default to the standard local Postgres superuser instance so developers can
# run the test suite without provisioning a dedicated database. Individual
# environments can still override DATABASE_URL before importing the fixtures.
DEFAULT_TEST_DATABASE_URL = (
    "postgresql+psycopg_async://postgres:postgres@localhost:5432/postgres"
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
os.environ.setdefault("APP_BASE_URL", "http://frontend.test")
os.environ.setdefault("SITE_BASE_URL", os.environ["APP_BASE_URL"])
os.environ.setdefault("EMAIL_VERIFICATION_RESEND_COOLDOWN", "60")
os.environ.setdefault("EMAIL_VERIFICATION_DAILY_LIMIT", "5")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("PASSWORD_RESET_TTL_MINUTES", "30")
os.environ.setdefault("PASSWORD_RESET_REQUEST_COOLDOWN", "1")
os.environ.setdefault("PASSWORD_RESET_DAILY_LIMIT", "10")
os.environ.setdefault("PASSWORD_RESET_REQUEST_IP_LIMIT", "100")
os.environ.setdefault("PASSWORD_RESET_REQUEST_IDENTIFIER_LIMIT", "100")
os.environ.setdefault("PASSWORD_RESET_REQUEST_PERIOD", "60")
os.environ.setdefault("PASSWORD_RESET_TOKEN_IP_LIMIT", "100")
os.environ.setdefault("PASSWORD_RESET_TOKEN_PERIOD", "60")

from app.database import (  # noqa: E402
    AsyncSessionLocal,
    Base,
    SessionLocal,
    async_engine,
)
from app import models  # noqa: E402
from app.triggers import create_triggers  # noqa: E402
from app.db_extensions import ensure_pg_extensions_async  # noqa: E402
from app.main import app, get_async_db, get_db  # noqa: E402


def override_get_db():
    """Provide a test database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db


async def override_get_async_db():
    async with AsyncSessionLocal() as session:
        yield session


app.dependency_overrides[get_async_db] = override_get_async_db

pytestmark = pytest.mark.asyncio

_client_ctx: ContextVar[httpx.AsyncClient | None] = ContextVar(
    "_client_ctx", default=None
)


def get_client() -> httpx.AsyncClient:
    client = _client_ctx.get()
    if client is None:
        raise RuntimeError("The async client fixture must be used in this test")
    return client


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _bootstrap_db():
    await ensure_pg_extensions_async(async_engine)
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(lambda sync_conn: create_triggers(sync_conn.engine))
    yield


@pytest_asyncio.fixture
async def client(_bootstrap_db):
    transport = ASGITransport(app=app, lifespan="on")
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        token = _client_ctx.set(async_client)
        try:
            yield async_client
        finally:
            _client_ctx.reset(token)


@pytest.fixture(scope="session")
def openapi_schema():
    """Build the OpenAPI schema once and cache it for all tests."""
    return app.openapi()



async def seed_data():
    """Populate the test database with minimal reference data."""

    async with AsyncSessionLocal() as db:
        mammal = models.Category(name="Mammal")
        bird = models.Category(name="Bird")
        db.add_all([mammal, bird])
        await db.commit()
        await db.refresh(mammal)
        await db.refresh(bird)

        europe = models.ContinentName(id=1, name_de="Europa", name_en="Europe")
        america = models.ContinentName(
            id=2, name_de="Nordamerika", name_en="North America"
        )
        db.add_all([europe, america])
        await db.commit()

        germany = models.CountryName(
            id=1, name_de="Deutschland", name_en="Germany", continent_id=1
        )
        usa = models.CountryName(
            id=2, name_de="USA", name_en="United States", continent_id=2
        )
        db.add_all([germany, usa])
        await db.commit()

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
        await db.commit()
        await db.refresh(zoo)

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
        await db.commit()
        await db.refresh(far_zoo)

        cls = models.ClassName(klasse=1, name_de="Säugetiere", name_en="Mammals")
        ordn = models.OrderName(ordnung=1, name_de="Raubtiere", name_en="Carnivorans")
        fam = models.FamilyName(familie=1, name_de="Katzen", name_en="Cats")
        db.add_all([cls, ordn, fam])
        await db.commit()

        animal = models.Animal(
            name_en="Lion",
            scientific_name="Panthera leo",
            category_id=mammal.id,
            default_image_url="http://example.com/lion.jpg",
            name_de="Löwe",
            description_en="King of the jungle",
            description_de="König der Tiere",
            klasse=1,
            ordnung=1,
            familie=1,
            slug="lion",
            art=1001,
        )
        tiger = models.Animal(
            name_en="Tiger",
            scientific_name="Panthera tigris",
            category_id=mammal.id,
            default_image_url="http://example.com/tiger.jpg",
            name_de="Tiger",
            slug="tiger",
            art=1002,
        )
        eagle = models.Animal(
            name_en="Eagle",
            scientific_name="Aquila chrysaetos",
            category_id=bird.id,
            default_image_url="http://example.com/eagle.jpg",
            name_de="Adler",
            slug="eagle",
            art=2001,
        )
        asiatic_lion = models.Animal(
            name_en="Asiatic Lion",
            scientific_name="Panthera leo persica",
            category_id=mammal.id,
            name_de="Asiatischer Löwe",
            slug="asiatic-lion",
            art=1003,
            parent_art=1001,
        )
        db.add_all([animal, tiger, eagle, asiatic_lion])
        await db.commit()
        await db.refresh(animal)
        await db.refresh(tiger)
        await db.refresh(eagle)
        await db.refresh(asiatic_lion)

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
        await db.commit()

        link = models.ZooAnimal(zoo_id=zoo.id, animal_id=animal.id)
        # Enrich seed: link the subspecies to TWO zoos to exercise aggregation + dedupe.
        subspecies_link_far = models.ZooAnimal(
            zoo_id=far_zoo.id, animal_id=asiatic_lion.id
        )
        subspecies_link_central = models.ZooAnimal(
            zoo_id=zoo.id, animal_id=asiatic_lion.id
        )
        db.add_all([link, subspecies_link_far, subspecies_link_central])
        await db.commit()

    return {
        "zoo": zoo,
        "animal": animal,
        "far_zoo": far_zoo,
        "tiger": tiger,
        "eagle": eagle,
        "lion_subspecies": asiatic_lion,
    }


@pytest_asyncio.fixture(scope="session")
async def data():
    """Provide seeded data to tests that need it."""

    records = await seed_data()
    yield records


_counter = 0  # used to create unique email addresses


TEST_PASSWORD = "supersecret"
CONSENT_VERSION = "2025-10-01"


class _RegisterResponsePayload(dict):
    """Dictionary-like payload exposing the registration email for tests.

    The registration endpoint intentionally returns a generic message so the
    public API does not leak whether an email address is already in use. A
    handful of tests need access to the email they just registered, so the
    fixture returns a mapping that behaves like the original response but also
    exposes the email address. Equality is implemented to keep assertions that
    expect the exact generic payload working without modification.
    """

    __slots__ = ()

    def __init__(self, *, detail: str | None, email: str) -> None:
        super().__init__({"detail": detail or "", "email": email})

    def __eq__(self, other):  # type: ignore[override]
        if isinstance(other, dict):
            expected = {"detail": self.get("detail", "")}
            return expected == other
        return super().__eq__(other)


class _RegisterResponseWrapper:
    """Proxy the original response while customising ``.json()`` for tests."""

    __slots__ = ("_response", "_email", "_cached")

    def __init__(self, response, email: str) -> None:
        self._response = response
        self._email = email
        self._cached: _RegisterResponsePayload | None = None

    def json(self):  # type: ignore[override]
        if self._cached is None:
            try:
                base = self._response.json()
            except ValueError:
                base = {}
            detail = base.get("detail") if isinstance(base, dict) else None
            self._cached = _RegisterResponsePayload(detail=detail, email=self._email)
        return self._cached

    def __getattr__(self, item):
        return getattr(self._response, item)



async def register_and_login(
    return_register_resp: bool = False,
    client: httpx.AsyncClient | None = None,
):
    """Create a new user and return an auth token and user id."""

    global _counter
    email = f"alice{_counter}@example.com"
    _counter += 1
    client_instance = client or _client_ctx.get()
    if client_instance is None:
        raise RuntimeError("register_and_login requires the client fixture")

    client_instance.cookies.clear()
    register_resp = await client_instance.post(
        "/users",
        json={
            "name": "Alice",
            "email": email,
            "password": TEST_PASSWORD,
            "accepted_data_protection": True,
            "privacy_consent_version": CONSENT_VERSION,
        },
    )
    assert register_resp.status_code == 202

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(models.User).where(models.User.email == email)
        )
        user = result.scalar_one()
        user_id = str(user.id)

    await mark_user_verified(user_id)

    login_resp = await client_instance.post(
        "/auth/login",
        data={"username": email, "password": TEST_PASSWORD},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert login_resp.status_code == 200
    body = login_resp.json()
    assert "expires_in" in body
    token = body["access_token"]
    if return_register_resp:
        return token, user_id, _RegisterResponseWrapper(register_resp, email)
    return token, user_id


async def mark_user_verified(user_id: str | uuid.UUID) -> None:
    """Set the verification timestamp for ``user_id`` in the database."""

    async with AsyncSessionLocal() as db:
        record = await db.get(models.User, uuid.UUID(str(user_id)))
        assert record is not None
        record.email_verified_at = datetime.now(timezone.utc)
        await db.execute(
            delete(models.VerificationToken).where(
                models.VerificationToken.user_id == record.id
            )
        )
        await db.commit()
