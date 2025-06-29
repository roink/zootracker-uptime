import uuid
from datetime import date, datetime
from .conftest import client, register_and_login, SessionLocal
from app import models

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

