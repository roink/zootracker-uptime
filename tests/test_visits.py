from datetime import datetime, date, UTC
from uuid import UUID
from .conftest import register_and_login
from app.database import SessionLocal
from app import models

from .conftest import get_client


async def create_sighting(token, _user_id, zoo_id, animal_id, dt=None):
    client = get_client()
    dt = dt or datetime.now(UTC)
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": dt.isoformat(),
    }
    resp = await client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    return resp.json(), dt.date()


def create_visit(token, user_id, zoo_id, vdate=None):
    """Helper to insert a visit record for the user."""
    vdate = vdate or date.today()
    db = SessionLocal()
    visit = models.ZooVisit(
        user_id=UUID(str(user_id)),
        zoo_id=UUID(str(zoo_id)),
        visit_date=vdate,
    )
    db.add(visit)
    db.commit()
    db.close()
    return vdate


async def _count_visits(token):
    client = get_client()
    resp = await client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    return resp.json()


async def test_sighting_creates_visit(client, data):
    token, user_id = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    _, vdate = await create_sighting(token, user_id, zoo_id, animal_id)
    resp = await client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    visits = resp.json()
    assert len(visits) == 1
    assert visits[0]["zoo_id"] == str(zoo_id)
    assert visits[0]["visit_date"] == str(vdate)


async def test_multiple_sightings_single_visit(client, data):
    token, user_id = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    await create_sighting(token, user_id, zoo_id, animal_id)
    await create_sighting(token, user_id, zoo_id, animal_id)
    resp = await client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_delete_sighting_removes_visit(client, data):
    token, user_id = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sight, _ = await create_sighting(token, user_id, zoo_id, animal_id)
    sighting_id = sight["id"]
    resp = await client.delete(
        f"/sightings/{sighting_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
    resp = await client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_visit_updated_on_sighting_change(client, data):
    token, user_id = await register_and_login()
    zoo_id = data["zoo"].id
    far_zoo = data["far_zoo"].id
    animal_id = data["animal"].id
    today = date.today()
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "sighting_datetime": datetime.combine(today, datetime.min.time(), tzinfo=UTC).isoformat(),
    }
    resp = await client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    sighting_id = resp.json()["id"]
    visits = await _count_visits(token)
    assert len(visits) == 1
    assert visits[0]["zoo_id"] == str(zoo_id)
    tomorrow = today.fromordinal(today.toordinal() + 1)
    resp = await client.patch(
        f"/sightings/{sighting_id}",
        json={"zoo_id": str(far_zoo), "sighting_datetime": datetime.combine(tomorrow, datetime.min.time(), tzinfo=UTC).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    visits = await _count_visits(token)
    assert len(visits) == 1
    assert visits[0]["zoo_id"] == str(far_zoo)
    assert visits[0]["visit_date"] == str(tomorrow)


async def test_visit_ids_requires_auth(client):
    resp = await client.get("/visits/ids")
    assert resp.status_code == 401


async def test_visit_ids_returns_only_ids(client, data):
    token, user_id = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    await create_sighting(token, user_id, zoo_id, animal_id)
    resp = await client.get("/visits/ids", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == [str(zoo_id)]


async def test_visit_ids_isolated_per_user(client, data):
    token1, user1 = await register_and_login()
    token2, user2 = await register_and_login()
    zoo1 = data["zoo"].id
    zoo2 = data["far_zoo"].id
    animal = data["animal"].id
    await create_sighting(token1, user1, zoo1, animal)
    await create_sighting(token2, user2, zoo2, animal)
    resp1 = await client.get("/visits/ids", headers={"Authorization": f"Bearer {token1}"})
    resp2 = await client.get("/visits/ids", headers={"Authorization": f"Bearer {token2}"})
    assert resp1.status_code == 200
    assert resp1.json() == [str(zoo1)]
    assert resp2.status_code == 200
    assert resp2.json() == [str(zoo2)]


async def test_visit_ids_unique(client, data):
    token, user_id = await register_and_login()
    zoo = data["zoo"].id
    animal = data["animal"].id
    await create_sighting(token, user_id, zoo, animal)
    await create_sighting(token, user_id, zoo, animal)
    resp = await client.get("/visits/ids", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == [str(zoo)]


async def test_visit_ids_include_sightings(client, data):
    token, user_id = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    await create_sighting(token, user_id, zoo_id, animal_id)
    db = SessionLocal()
    db.query(models.ZooVisit).delete()
    db.commit()
    db.close()
    resp = await client.get("/visits/ids", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == [str(zoo_id)]


async def test_visit_ids_dedup_across_visits_and_sightings(client, data):
    token, user_id = await register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    create_visit(token, user_id, zoo_id)
    await create_sighting(token, user_id, zoo_id, animal_id)
    resp = await client.get("/visits/ids", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == [str(zoo_id)]


async def test_has_visited_endpoint_true(client, data):
    token, user_id = await register_and_login()
    zoo_id = data["zoo"].id
    zoo_slug = data["zoo"].slug
    animal_id = data["animal"].id
    await create_sighting(token, user_id, zoo_id, animal_id)
    resp = await client.get(
        f"/zoos/{zoo_slug}/visited",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"visited": True}


async def test_has_visited_endpoint_false(client, data):
    token, _ = await register_and_login()
    zoo_slug = data["zoo"].slug
    resp = await client.get(
        f"/zoos/{zoo_slug}/visited",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"visited": False}


async def test_has_visited_without_zoo_visit(client, data):
    token, user_id = await register_and_login()
    zoo_id = data["zoo"].id
    zoo_slug = data["zoo"].slug
    animal_id = data["animal"].id
    await create_sighting(token, user_id, zoo_id, animal_id)
    db = SessionLocal()
    db.query(models.ZooVisit).delete()
    db.commit()
    db.close()
    resp = await client.get(
        f"/zoos/{zoo_slug}/visited",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"visited": True}


async def test_has_visited_requires_auth(client, data):
    zoo_slug = data["zoo"].slug
    resp = await client.get(f"/zoos/{zoo_slug}/visited")
    assert resp.status_code == 401
