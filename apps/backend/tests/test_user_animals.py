from datetime import datetime, UTC
from .conftest import register_and_login

async def test_get_seen_animals_success(client, data):
    token, user_id = await register_and_login()
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

    resp = await client.get(
        f"/users/{user_id}/animals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    animals = resp.json()
    assert len(animals) == 1
    assert animals[0]["id"] == str(animal_id)

async def test_get_seen_animals_requires_auth(client, data):
    token, user_id = await register_and_login()
    resp = await client.get(f"/users/{user_id}/animals")
    assert resp.status_code == 401

async def test_get_seen_animals_wrong_user(client, data):
    token1, user1 = await register_and_login()
    token2, _ = await register_and_login()
    resp = await client.get(
        f"/users/{user1}/animals",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403
    assert resp.json() == {
        "detail": "Cannot access this resource for another user"
    }

async def test_get_seen_animals_empty(client, data):
    token, user_id = await register_and_login()
    resp = await client.get(
        f"/users/{user_id}/animals",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_seen_animal_ids_success(client, data):
    token, user_id = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    payload = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    await client.post(
        "/sightings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get(
        f"/users/{user_id}/animals/ids",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == [str(animal_id)]


async def test_get_seen_animal_ids_requires_auth(client, data):
    token, user_id = await register_and_login()
    resp = await client.get(f"/users/{user_id}/animals/ids")
    assert resp.status_code == 401


async def test_get_seen_animal_ids_wrong_user(client, data):
    token1, user1 = await register_and_login()
    token2, _ = await register_and_login()
    resp = await client.get(
        f"/users/{user1}/animals/ids",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403
    assert resp.json() == {
        "detail": "Cannot access this resource for another user"
    }


async def test_get_seen_animal_ids_empty(client, data):
    token, user_id = await register_and_login()
    resp = await client.get(
        f"/users/{user_id}/animals/ids",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == []


async def test_get_seen_animal_ids_deduplicates_same_animal(client, data):
    token, user_id = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    payload = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    # create duplicate sightings of same animal
    await client.post(
        "/sightings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/sightings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get(
        f"/users/{user_id}/animals/ids",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == [str(animal_id)]


async def test_get_seen_animal_count_success(client, data):
    token, user_id = await register_and_login()
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

    resp = await client.get(
        f"/users/{user_id}/animals/count",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"count": 1}


async def test_get_seen_animal_count_requires_auth(client, data):
    token, user_id = await register_and_login()
    resp = await client.get(f"/users/{user_id}/animals/count")
    assert resp.status_code == 401


async def test_get_seen_animal_count_wrong_user(client, data):
    token1, user1 = await register_and_login()
    token2, _ = await register_and_login()
    resp = await client.get(
        f"/users/{user1}/animals/count",
        headers={"Authorization": f"Bearer {token2}"},
    )
    assert resp.status_code == 403
    assert resp.json() == {
        "detail": "Cannot access this resource for another user"
    }


async def test_get_seen_animal_count_empty(client, data):
    token, user_id = await register_and_login()
    resp = await client.get(
        f"/users/{user_id}/animals/count",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"count": 0}


async def test_seen_animal_count_deduplicates_same_animal(client, data):
    token, user_id = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    payload = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.now(UTC).isoformat(),
    }
    await client.post(
        "/sightings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        "/sightings",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get(
        f"/users/{user_id}/animals/count",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"count": 1}


async def test_seen_animal_count_two_animals(client, data):
    token, user_id = await register_and_login()
    zoo_id = data["zoo"].id
    lion_id = data["animal"].id
    tiger_id = data["tiger"].id
    for animal_id in (lion_id, tiger_id):
        payload = {
            "zoo_id": str(zoo_id),
            "animal_id": str(animal_id),
            "sighting_datetime": datetime.now(UTC).isoformat(),
        }
        await client.post(
            "/sightings",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
    resp = await client.get(
        f"/users/{user_id}/animals/count",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"count": 2}

