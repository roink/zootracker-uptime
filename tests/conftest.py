import os
from datetime import date, datetime
import uuid

import pytest
from fastapi.testclient import TestClient

# set up database url before importing app
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
os.environ["AUTH_RATE_LIMIT"] = "1000"
os.environ["GENERAL_RATE_LIMIT"] = "10000"

# ensure a fresh database for every test run
if os.path.exists("test.db"):
    os.remove("test.db")

from app.database import Base, engine, SessionLocal
from app import models
from app.main import app, get_db


def override_get_db():
    """Provide a test database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

Base.metadata.create_all(bind=engine)

client = TestClient(app)


def seed_data():
    """Populate the test database with minimal reference data."""
    db = SessionLocal()
    category = models.Category(name="Mammal")
    db.add(category)
    db.commit()
    db.refresh(category)

    zoo = models.Zoo(
        name="Central Zoo",
        address="123 Zoo St",
        latitude=10.0,
        longitude=20.0,
        description="A fun place",
    )
    db.add(zoo)
    db.commit()
    db.refresh(zoo)

    far_zoo = models.Zoo(
        name="Far Zoo",
        address="456 Distant Rd",
        latitude=50.0,
        longitude=60.0,
        description="Too far away",
    )
    db.add(far_zoo)
    db.commit()
    db.refresh(far_zoo)

    animal = models.Animal(common_name="Lion", category_id=category.id)
    db.add(animal)
    db.commit()
    db.refresh(animal)

    link = models.ZooAnimal(zoo_id=zoo.id, animal_id=animal.id)
    db.add(link)
    db.commit()

    db.close()
    return {"zoo": zoo, "animal": animal, "far_zoo": far_zoo}


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
        "/token",
        data={"username": email, "password": TEST_PASSWORD},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    if return_register_resp:
        return token, user_id, register_resp
    return token, user_id
