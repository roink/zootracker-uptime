import uuid
from datetime import datetime, UTC
from sqlalchemy import text
from .conftest import register_and_login, SessionLocal
from app import models

async def test_post_sighting(client, data):
    token, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = await client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["animal_id"] == str(animal_id)


async def test_sighting_notes_round_trip(client, data):
    token, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
        "notes": "Feeding time observation",
    }
    resp = await client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    created = resp.json()
    assert created["notes"] == "Feeding time observation"

    sighting_id = created["id"]
    resp = await client.patch(
        f"/sightings/{sighting_id}",
        json={"notes": "Feeding time moved to afternoon"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["notes"] == "Feeding time moved to afternoon"

    resp = await client.get(
        f"/sightings/{sighting_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    fetched = resp.json()
    assert fetched["notes"] == "Feeding time moved to afternoon"


async def test_sighting_notes_can_be_cleared(client, data):
    token, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
        "notes": "  Observed enrichment session  ",
    }
    resp = await client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    created = resp.json()
    assert created["notes"] == "Observed enrichment session"

    sighting_id = created["id"]
    resp = await client.patch(
        f"/sightings/{sighting_id}",
        json={"notes": None},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    updated = resp.json()
    assert updated["notes"] is None

    resp = await client.get(
        f"/sightings/{sighting_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    fetched = resp.json()
    assert fetched["notes"] is None

async def test_sighting_requires_auth(client, data):
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = await client.post("/sightings", json=sighting)
    assert resp.status_code == 401

async def test_sighting_requires_json(client, data):
    token, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = await client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}", "content-type": "text/plain"},
    )
    assert resp.status_code == 415

async def test_sighting_accepts_charset(client, data):
    token, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = await client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}", "content-type": "application/json; charset=utf-8"},
    )
    assert resp.status_code == 200

async def test_sighting_user_id_field_rejected(client, data):
    token, _ = await register_and_login()
    _, other_user_id = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
        "user_id": str(other_user_id),
    }
    resp = await client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 422

async def test_sighting_invalid_zoo(client, data):
    token, _ = await register_and_login()
    animal_id = data["animal"].id
    invalid_zoo = uuid.uuid4()
    sighting = {
        "zoo_id": str(invalid_zoo),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = await client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404

async def test_sighting_invalid_animal(client, data):
    token, _ = await register_and_login()
    zoo_id = data["zoo"].id
    invalid_animal = uuid.uuid4()
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(invalid_animal),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = await client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404

async def test_sighting_extra_field_rejected(client, data):
    token, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
        "unexpected": "boom",
    }
    resp = await client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422

async def test_sighting_notes_too_long(client, data):
    token, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
        "notes": "n" * 1001,
    }
    resp = await client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422

async def test_delete_sighting_success(client, data):
    token, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = await client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    sighting_id = resp.json()["id"]

    resp = await client.delete(
        f"/sightings/{sighting_id}", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 204
    db = SessionLocal()
    deleted = db.get(models.AnimalSighting, uuid.UUID(sighting_id))
    db.close()
    assert deleted is None

async def test_delete_sighting_unauthorized(client, data):
    token1, _ = await register_and_login()
    token2, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = await client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200
    sighting_id = resp.json()["id"]

    resp = await client.delete(
        f"/sightings/{sighting_id}", headers={"Authorization": f"Bearer {token2}"}
    )
    assert resp.status_code == 403

async def test_patch_sighting_success(client, data):
    token, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = await client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    sighting_id = resp.json()["id"]

    # update to the secondary zoo and add a photo
    new_zoo = data["far_zoo"].id
    photo = "http://example.com/photo.jpg"
    resp = await client.patch(
        f"/sightings/{sighting_id}",
        json={"zoo_id": str(new_zoo), "photo_url": photo},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["photo_url"] == photo
    assert body["zoo_id"] == str(new_zoo)

async def test_patch_sighting_forbidden(client, data):
    token1, _ = await register_and_login()
    token2, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
        "notes": "Original keeper note",
    }
    resp = await client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200
    sighting_id = resp.json()["id"]

    resp = await client.patch(
        f"/sightings/{sighting_id}",
        json={"notes": "oops"},
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403

    resp = await client.get(
        f"/sightings/{sighting_id}",
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200
    assert resp.json()["notes"] == "Original keeper note"


async def test_get_sighting_owner_only(client, data):
    token1, _ = await register_and_login()
    token2, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = await client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200
    sighting_id = resp.json()["id"]

    # owner can fetch
    resp = await client.get(
        f"/sightings/{sighting_id}", headers={"Authorization": f"Bearer {token1}"}
    )
    assert resp.status_code == 200

    # other user forbidden
    resp = await client.get(
        f"/sightings/{sighting_id}", headers={"Authorization": f"Bearer {token2}"}
    )
    assert resp.status_code == 403


async def test_sightings_are_user_specific(client, data):
    token1, _ = await register_and_login()
    token2, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    resp = await client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp.status_code == 200

    resp = await client.get("/sightings", headers={"Authorization": f"Bearer {token2}"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_sightings_requires_auth(client):
    resp = await client.get("/sightings")
    assert resp.status_code == 401


async def test_sighting_list_sorted_and_named(client, data):
    token, _ = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id

    # First sighting on a recent day
    sight1 = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime(2024, 1, 1, tzinfo=UTC).isoformat(),
    }
    r1 = await client.post(
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
    r2 = await client.post(
        "/sightings", json=sight2, headers={"Authorization": f"Bearer {token}"}
    )
    assert r2.status_code == 200

    # Same day as first but created later
    sight3 = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime(2024, 1, 1, tzinfo=UTC).isoformat(),
    }
    r3 = await client.post(
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

    resp = await client.get("/sightings", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    dates = [s["sighting_datetime"][:10] for s in body]
    assert dates == ["2024-01-01", "2024-01-01", "2023-01-01"]
    assert body[0]["created_at"] >= body[1]["created_at"]
    assert body[0]["animal_name_de"]

