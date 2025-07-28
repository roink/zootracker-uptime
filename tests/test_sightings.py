import uuid
from datetime import date, datetime
from .conftest import client, register_and_login, SessionLocal
from app import models

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

def test_sighting_accepts_charset(data):
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
        headers={"Authorization": f"Bearer {token}", "content-type": "application/json; charset=utf-8"},
    )
    assert resp.status_code == 200

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

def test_delete_sighting_success(data):
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
    sighting_id = resp.json()["id"]

    resp = client.delete(
        f"/sightings/{sighting_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204
    db = SessionLocal()
    deleted = db.get(models.AnimalSighting, uuid.UUID(sighting_id))
    db.close()
    assert deleted is None

def test_delete_sighting_unauthorized(data):
    token1, user1 = register_and_login()
    token2, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "user_id": str(user1),
        "sighting_datetime": datetime.utcnow().isoformat(),
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200
    sighting_id = resp.json()["id"]

    resp = client.delete(
        f"/sightings/{sighting_id}", headers={"Authorization": f"Bearer {token2}"}
    )
    assert resp.status_code == 403

def test_patch_sighting_success(data):
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
    sighting_id = resp.json()["id"]

    # update to the secondary zoo and add a photo
    new_zoo = data["far_zoo"].id
    photo = "http://example.com/photo.jpg"
    resp = client.patch(
        f"/sightings/{sighting_id}",
        json={"zoo_id": str(new_zoo), "photo_url": photo},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["photo_url"] == photo
    assert body["zoo_id"] == str(new_zoo)

def test_patch_sighting_forbidden(data):
    token1, user1 = register_and_login()
    token2, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "user_id": str(user1),
        "sighting_datetime": datetime.utcnow().isoformat(),
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200
    sighting_id = resp.json()["id"]

    resp = client.patch(
        f"/sightings/{sighting_id}",
        json={"notes": "oops"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403


def test_get_sighting_owner_only(data):
    token1, user1 = register_and_login()
    token2, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "user_id": str(user1),
        "sighting_datetime": datetime.utcnow().isoformat(),
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200
    sighting_id = resp.json()["id"]

    # owner can fetch
    resp = client.get(
        f"/sightings/{sighting_id}", headers={"Authorization": f"Bearer {token1}"}
    )
    assert resp.status_code == 200

    # other user forbidden
    resp = client.get(
        f"/sightings/{sighting_id}", headers={"Authorization": f"Bearer {token2}"}
    )
    assert resp.status_code == 403

