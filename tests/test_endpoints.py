"""Integration tests covering the main API endpoints."""

import os
from datetime import date, datetime
import uuid

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

    animal = models.Animal(common_name="Lion", category_id=category.id)
    db.add(animal)
    db.commit()
    db.refresh(animal)

    link = models.ZooAnimal(zoo_id=zoo.id, animal_id=animal.id)
    db.add(link)
    db.commit()

    db.close()
    return {"zoo": zoo, "animal": animal}


@pytest.fixture(scope="module")
def data():
    """Provide seeded data to tests that need it."""
    records = seed_data()
    yield records


_counter = 0  # used to create unique email addresses


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

# --- Authentication and user management tests ---


def test_create_user_and_authenticate():
    """Ensure that a new user can register and obtain a token."""
    token, _ = register_and_login()
    assert token


def test_create_user_empty_fields():
    """Empty strings for required user fields should fail."""
    resp = client.post(
        "/users",
        json={"name": "", "email": "", "password": ""},
    )
    assert resp.status_code == 422


def test_create_user_extra_field_rejected():
    """Unknown fields should result in a 422 error."""
    resp = client.post(
        "/users",
        json={
            "name": "Bob",
            "email": "bob@example.com",
            "password": "secret",
            "unexpected": "boom",
        },
    )
    assert resp.status_code == 422


def test_create_user_name_too_long():
    long_name = "a" * 256
    resp = client.post(
        "/users",
        json={"name": long_name, "email": "toolong@example.com", "password": "secret"},
    )
    assert resp.status_code == 422


def test_create_user_email_too_long():
    # construct an email longer than 255 characters
    local_part = "a" * 244
    long_email = f"{local_part}@example.com"
    resp = client.post(
        "/users",
        json={"name": "Alice", "email": long_email, "password": "secret"},
    )
    assert resp.status_code == 422


def test_create_user_password_too_long():
    long_pw = "p" * 256
    resp = client.post(
        "/users",
        json={"name": "Alice", "email": "alice@example.com", "password": long_pw},
    )
    assert resp.status_code == 422


def test_create_user_requires_json():
    global _counter
    email = f"json{_counter}@example.com"
    _counter += 1
    resp = client.post(
        "/users",
        json={"name": "Alice", "email": email, "password": "secret"},
        headers={"content-type": "text/plain"},
    )
    assert resp.status_code == 415


def test_login_empty_username_password():
    """Login with empty credentials should return 400."""
    resp = client.post(
        "/token",
        data={"username": "", "password": ""},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 400

# --- Visit endpoints ---


def test_post_visit_and_retrieve(data):
    """Create a visit and verify it can be retrieved."""
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


def test_create_visit_requires_json(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        "/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}", "content-type": "text/plain"},
    )
    assert resp.status_code == 415


def test_create_visit_for_user_requires_json(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}", "content-type": "text/plain"},
    )
    assert resp.status_code == 415


def test_post_sighting(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "user_id": str(user_id),
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
        "user_id": str(uuid.uuid4()),
        "sighting_datetime": datetime.utcnow().isoformat(),
    }
    resp = client.post("/sightings", json=sighting)
    assert resp.status_code == 401


def test_sighting_requires_json(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "user_id": str(user_id),
        "sighting_datetime": datetime.utcnow().isoformat(),
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}", "content-type": "text/plain"},
    )
    assert resp.status_code == 415



def test_sighting_other_user_forbidden(data):
    token1, _ = register_and_login()
    _, other_user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.utcnow().isoformat(),
        "user_id": str(other_user_id),
    }
    resp = client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token1}"})
    assert resp.status_code == 403


def test_sighting_invalid_zoo(data):
    token, user_id = register_and_login()
    animal_id = data["animal"].id
    invalid_zoo = uuid.uuid4()
    sighting = {
        "zoo_id": str(invalid_zoo),
        "animal_id": str(animal_id),
        "user_id": str(user_id),
        "sighting_datetime": datetime.utcnow().isoformat(),
    }
    resp = client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_sighting_invalid_animal(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    invalid_animal = uuid.uuid4()
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(invalid_animal),
        "user_id": str(user_id),
        "sighting_datetime": datetime.utcnow().isoformat(),
    }
    resp = client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_sighting_extra_field_rejected(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "user_id": str(user_id),
        "sighting_datetime": datetime.utcnow().isoformat(),
        "unexpected": "boom",
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_sighting_notes_too_long(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "user_id": str(user_id),
        "sighting_datetime": datetime.utcnow().isoformat(),
        "notes": "n" * 1001,
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422

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


def test_get_visits_requires_auth():
    resp = client.get("/visits")
    assert resp.status_code == 401


def test_get_visits_empty(data):
    token, _ = register_and_login()
    resp = client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_visits_are_user_specific(data):
    token1, user1 = register_and_login()
    token2, _ = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user1}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200

    resp = client.get("/visits", headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.get("/visits", headers={"Authorization": f"Bearer {token1}"})
    assert resp.status_code == 200
    visits = resp.json()
    assert len(visits) == 1


def test_visit_missing_zoo_id_fails(data):
    token, user_id = register_and_login()
    visit = {"visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_visit_missing_date_fails(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id)}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_visit_has_user_id_in_db(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {"zoo_id": str(zoo_id), "visit_date": str(date.today())}
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    visit_id = resp.json()["id"]
    db = SessionLocal()
    stored = db.get(models.ZooVisit, uuid.UUID(visit_id))
    db.close()
    assert stored is not None
    assert stored.user_id == uuid.UUID(user_id)


def test_visit_extra_field_rejected(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {
        "zoo_id": str(zoo_id),
        "visit_date": str(date.today()),
        "unexpected": "boom",
    }
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_visit_notes_too_long(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    visit = {
        "zoo_id": str(zoo_id),
        "visit_date": str(date.today()),
        "notes": "n" * 1001,
    }
    resp = client.post(
        f"/users/{user_id}/visits",
        json=visit,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


def test_get_seen_animals_success(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "user_id": str(user_id),
        "sighting_datetime": datetime.utcnow().isoformat(),
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200

    resp = client.get(
        f"/users/{user_id}/animals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    animals = resp.json()
    assert len(animals) == 1
    assert animals[0]["id"] == str(animal_id)


def test_get_seen_animals_requires_auth(data):
    token, user_id = register_and_login()
    resp = client.get(f"/users/{user_id}/animals")
    assert resp.status_code == 401


def test_get_seen_animals_wrong_user(data):
    token1, user1 = register_and_login()
    token2, _ = register_and_login()
    resp = client.get(
        f"/users/{user1}/animals",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403


def test_get_seen_animals_empty(data):
    token, user_id = register_and_login()
    resp = client.get(
        f"/users/{user_id}/animals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


def test_login_alias_route():
    global _counter
    email = f"alias{_counter}@example.com"
    _counter += 1
    resp = client.post(
        "/users",
        json={"name": "Alias", "email": email, "password": "secret"},
    )
    assert resp.status_code == 200
    resp = client.post(
        "/auth/login",
        data={"username": email, "password": "secret"},
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    assert "access_token" in resp.json()
# --- Zoo endpoints ---


def test_get_animals_for_zoo(data):
    resp = client.get(f"/zoos/{data['zoo'].id}/animals")
    assert resp.status_code == 200
    animals = resp.json()
    assert len(animals) == 1
    assert animals[0]["id"] == str(data["animal"].id)

def test_get_animal_detail_success(data):
    resp = client.get(f"/animals/{data['animal'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(data["animal"].id)
    assert body["zoos"][0]["id"] == str(data["zoo"].id)

def test_get_animal_detail_not_found():
    resp = client.get(f"/animals/{uuid.uuid4()}")
    assert resp.status_code == 404

def test_get_zoo_details(data):
    resp = client.get(f"/zoos/{data['zoo'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(data["zoo"].id)
    assert body["address"] == "123 Zoo St"
    assert body["description"] == "A fun place"


def test_get_zoo_invalid_id():
    resp = client.get(f"/zoos/{uuid.uuid4()}")
    assert resp.status_code == 404
