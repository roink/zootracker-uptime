import os
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

# set up database url before importing app
os.environ["DATABASE_URL"] = "sqlite:///./test.db"

# ensure a fresh database for every test run
if os.path.exists("test.db"):
    os.remove("test.db")

from app.database import Base, engine, SessionLocal
from app import models
from app.main import app, get_db


def override_get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

Base.metadata.create_all(bind=engine)

client = TestClient(app)


def seed_data():
    db = SessionLocal()
    category = models.Category(name="Mammal")
    db.add(category)
    db.commit()
    db.refresh(category)

    zoo = models.Zoo(name="Central Zoo")
    db.add(zoo)
    db.commit()
    db.refresh(zoo)

    animal = models.Animal(common_name="Lion", category_id=category.id)
    db.add(animal)
    db.commit()
    db.refresh(animal)

    db.close()
    return {"zoo": zoo, "animal": animal}


@pytest.fixture(scope="module")
def data():
    records = seed_data()
    yield records


_counter = 0


def register_and_login():
    """Create a new user and return an auth token and user id."""
    global _counter
    email = f"alice{_counter}@example.com"
    _counter += 1
    resp = client.post(
        "/users",
        json={"name": "Alice", "email": email, "password": "secret"},
    )
    assert resp.status_code == 200
    user_id = resp.json()["id"]
    resp = client.post(
        "/token",
        data={"username": email, "password": "secret"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"], user_id


def test_create_user_and_authenticate():
    token, _ = register_and_login()
    assert token


def test_post_visit_and_retrieve(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    resp = client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    visits = resp.json()
    assert len(visits) == 1
    assert visits[0]["zoo_id"] == str(zoo_id)


def test_visit_requires_auth(data):
    _, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(f"/users/{user_id}/visits", json=visit)
    assert resp.status_code == 401


def test_post_sighting(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.utcnow().isoformat(),
    }
    resp = client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["animal_id"] == str(animal_id)


def test_sighting_requires_auth(data):
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.utcnow().isoformat(),
    }
    resp = client.post("/sightings", json=sighting)
    assert resp.status_code == 401


def test_visit_wrong_user(data):
    token1, user1 = register_and_login()
    _, user2 = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user2}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 403


def test_multiple_visits(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit1 = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit1,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    tomorrow = date.fromordinal(date.today().toordinal() + 1)
    visit2 = {"zoo_id": str(zoo_id), "visit_date": str(tomorrow)}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit2,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    resp = client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    visits = resp.json()
    assert len(visits) == 2

