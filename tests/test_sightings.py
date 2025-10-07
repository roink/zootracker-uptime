import uuid
from datetime import datetime, UTC
from sqlalchemy import text
from .conftest import client, register_and_login, SessionLocal
from app import models

def test_post_sighting(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["animal_id"] == str(animal_id)


def test_sighting_notes_round_trip(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
        "notes": "Feeding time observation",
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    created = resp.json()
    assert created["notes"] == "Feeding time observation"

    sighting_id = created["id"]
    resp = client.patch(
        f"/sightings/{sighting_id}",
        json={"notes": "Feeding time moved to afternoon"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["notes"] == "Feeding time moved to afternoon"

    resp = client.get(
        f"/sightings/{sighting_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    fetched = resp.json()
    assert fetched["notes"] == "Feeding time moved to afternoon"


def test_sighting_notes_can_be_cleared(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
        "notes": "  Observed enrichment session  ",
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    created = resp.json()
    assert created["notes"] == "Observed enrichment session"

    sighting_id = created["id"]
    resp = client.patch(
        f"/sightings/{sighting_id}",
        json={"notes": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["notes"] is None

    resp = client.get(
        f"/sightings/{sighting_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    fetched = resp.json()
    assert fetched["notes"] is None

def test_sighting_requires_auth(data):
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = client.post("/sightings", json=sighting)
    assert resp.status_code == 401

def test_sighting_requires_json(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}", "content-type": "text/plain"},
    )
    assert resp.status_code == 415

def test_sighting_accepts_charset(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}", "content-type": "application/json; charset=utf-8"},
    )
    assert resp.status_code == 200

def test_sighting_user_id_field_rejected(data):
    token, _ = register_and_login()
    _, other_user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
        "user_id": str(other_user_id),
    }
    resp = client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422

def test_sighting_invalid_zoo(data):
    token, _ = register_and_login()
    animal_id = data["animal"].id
    invalid_zoo = uuid.uuid4()
    sighting = {
        "zoo_id": str(invalid_zoo),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404

def test_sighting_invalid_animal(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    invalid_animal = uuid.uuid4()
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(invalid_animal),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404

def test_sighting_extra_field_rejected(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
        "unexpected": "boom",
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422

def test_sighting_notes_too_long(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
        "notes": "n" * 1001,
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422

def test_delete_sighting_success(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
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
    token1, _ = register_and_login()
    token2, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
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
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
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
    token1, _ = register_and_login()
    token2, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
        "notes": "Original keeper note",
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

    resp = client.get(
        f"/sightings/{sighting_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Original keeper note"


def test_get_sighting_owner_only(data):
    token1, _ = register_and_login()
    token2, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
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


def test_sightings_are_user_specific(data):
    token1, _ = register_and_login()
    token2, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200

    resp = client.get("/sightings", headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_sightings_requires_auth():
    resp = client.get("/sightings")
    assert resp.status_code == 401


def test_sighting_list_sorted_and_named(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id

    # First sighting on a recent day
    sight1 = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime(2024, 1, 1, tzinfo=UTC).isoformat(),
    }
    r1 = client.post(
        "/sightings", json=sight1, headers={"Authorization": f"Bearer {token}"}
    )
    assert r1.status_code == 200
    id1 = r1.json()["id"]

    # Older day
    sight2 = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime(2023, 1, 1, tzinfo=UTC).isoformat(),
    }
    r2 = client.post(
        "/sightings", json=sight2, headers={"Authorization": f"Bearer {token}"}
    )
    assert r2.status_code == 200

    # Same day as first but created later
    sight3 = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime(2024, 1, 1, tzinfo=UTC).isoformat(),
    }
    r3 = client.post(
        "/sightings", json=sight3, headers={"Authorization": f"Bearer {token}"}
    )
    assert r3.status_code == 200

    with SessionLocal() as session:
        session.execute(
            text(
                "UPDATE animal_sightings SET created_at = created_at - interval '1 second' WHERE id = :id"
            ),
            {"id": id1},
        )
        session.commit()

    resp = client.get("/sightings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    dates = [s["sighting_datetime"][:10] for s in body]
    assert dates == ["2024-01-01", "2024-01-01", "2023-01-01"]
    assert body[0]["created_at"] >= body[1]["created_at"]
    assert body[0]["animal_name_de"]

