from datetime import datetime, date, UTC
from .conftest import client, register_and_login
from app.database import SessionLocal
from app import models


def create_sighting(token, user_id, zoo_id, animal_id, dt=None):
    dt = dt or datetime.now(UTC)
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "user_id": str(user_id),
        "sighting_datetime": dt.isoformat(),
    }
    resp = client.post(
        "/sightings",
        json=sighting,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    return resp.json(), dt.date()


def _count_visits(token):
    resp = client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    return resp.json()


def test_sighting_creates_visit(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    _, vdate = create_sighting(token, user_id, zoo_id, animal_id)
    resp = client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    visits = resp.json()
    assert len(visits) == 1
    assert visits[0]["zoo_id"] == str(zoo_id)
    assert visits[0]["visit_date"] == str(vdate)


def test_multiple_sightings_single_visit(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    create_sighting(token, user_id, zoo_id, animal_id)
    create_sighting(token, user_id, zoo_id, animal_id)
    resp = client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_delete_sighting_removes_visit(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    sight, _ = create_sighting(token, user_id, zoo_id, animal_id)
    sighting_id = sight["id"]
    resp = client.delete(
        f"/sightings/{sighting_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
    resp = client.get("/visits", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_visit_updated_on_sighting_change(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    far_zoo = data["far_zoo"].id
    animal_id = data["animal"].id
    today = date.today()
    sighting = {
        "zoo_id": str(zoo_id),
        "animal_id": str(animal_id),
        "user_id": str(user_id),
        "sighting_datetime": datetime.combine(today, datetime.min.time(), tzinfo=UTC).isoformat(),
    }
    resp = client.post("/sightings", json=sighting, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    sighting_id = resp.json()["id"]
    visits = _count_visits(token)
    assert len(visits) == 1
    assert visits[0]["zoo_id"] == str(zoo_id)
    tomorrow = today.fromordinal(today.toordinal() + 1)
    resp = client.patch(
        f"/sightings/{sighting_id}",
        json={"zoo_id": str(far_zoo), "sighting_datetime": datetime.combine(tomorrow, datetime.min.time(), tzinfo=UTC).isoformat()},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    visits = _count_visits(token)
    assert len(visits) == 1
    assert visits[0]["zoo_id"] == str(far_zoo)
    assert visits[0]["visit_date"] == str(tomorrow)


def test_visit_ids_requires_auth():
    resp = client.get("/visits/ids")
    assert resp.status_code == 401


def test_visit_ids_returns_only_ids(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    create_sighting(token, user_id, zoo_id, animal_id)
    resp = client.get("/visits/ids", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == [str(zoo_id)]


def test_visit_ids_isolated_per_user(data):
    token1, user1 = register_and_login()
    token2, user2 = register_and_login()
    zoo1 = data["zoo"].id
    zoo2 = data["far_zoo"].id
    animal = data["animal"].id
    create_sighting(token1, user1, zoo1, animal)
    create_sighting(token2, user2, zoo2, animal)
    resp1 = client.get("/visits/ids", headers={"Authorization": f"Bearer {token1}"})
    resp2 = client.get("/visits/ids", headers={"Authorization": f"Bearer {token2}"})
    assert resp1.status_code == 200
    assert resp1.json() == [str(zoo1)]
    assert resp2.status_code == 200
    assert resp2.json() == [str(zoo2)]


def test_visit_ids_unique(data):
    token, user_id = register_and_login()
    zoo = data["zoo"].id
    animal = data["animal"].id
    create_sighting(token, user_id, zoo, animal)
    create_sighting(token, user_id, zoo, animal)
    resp = client.get("/visits/ids", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == [str(zoo)]


def test_visit_ids_include_sightings(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    create_sighting(token, user_id, zoo_id, animal_id)
    db = SessionLocal()
    db.query(models.ZooVisit).delete()
    db.commit()
    db.close()
    resp = client.get("/visits/ids", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == [str(zoo_id)]


def test_has_visited_endpoint_true(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    create_sighting(token, user_id, zoo_id, animal_id)
    resp = client.get(
        f"/zoos/{zoo_id}/visited",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"visited": True}


def test_has_visited_endpoint_false(data):
    token, _ = register_and_login()
    zoo_id = data["zoo"].id
    resp = client.get(
        f"/zoos/{zoo_id}/visited",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"visited": False}


def test_has_visited_without_zoo_visit(data):
    token, user_id = register_and_login()
    zoo_id = data["zoo"].id
    animal_id = data["animal"].id
    create_sighting(token, user_id, zoo_id, animal_id)
    db = SessionLocal()
    db.query(models.ZooVisit).delete()
    db.commit()
    db.close()
    resp = client.get(
        f"/zoos/{zoo_id}/visited",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"visited": True}


def test_has_visited_requires_auth(data):
    zoo_id = data["zoo"].id
    resp = client.get(f"/zoos/{zoo_id}/visited")
    assert resp.status_code == 401
