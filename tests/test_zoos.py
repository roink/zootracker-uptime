import uuid
from datetime import date, datetime
from .conftest import client, register_and_login, SessionLocal
from app import models

def test_get_animals_for_zoo(data):
    resp = client.get(f"/zoos/{data['zoo'].id}/animals")
    assert resp.status_code == 200
    animals = resp.json()
    assert len(animals) == 1
    assert animals[0]["id"] == str(data["animal"].id)

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

def test_search_zoos_with_radius(data):
    """Zoos outside the radius should not be returned."""
    params = {
        "latitude": data["zoo"].latitude,
        "longitude": data["zoo"].longitude,
        "radius_km": 100,
    }
    resp = client.get("/zoos", params=params)
    assert resp.status_code == 200
    body = resp.json()
    ids = {z["id"] for z in body}
    assert str(data["zoo"].id) in ids
    assert str(data["far_zoo"].id) not in ids
    dists = [z["distance_km"] for z in body]
    assert dists == sorted(dists)

def test_search_zoos_name_only(data):
    """Name search should work without location parameters."""
    resp = client.get("/zoos", params={"q": "Central"})
    assert resp.status_code == 200
    names = [z["name"] for z in resp.json()]
    assert "Central Zoo" in names

def test_animal_zoos_sorted_by_distance(data):
    """Zoos for an animal should be ordered by proximity when location is given."""
    # link far_zoo to the animal for this test
    db = SessionLocal()
    db.add(models.ZooAnimal(zoo_id=data["far_zoo"].id, animal_id=data["animal"].id))
    db.commit()
    db.close()

    params = {
        "latitude": data["zoo"].latitude,
        "longitude": data["zoo"].longitude,
    }
    resp = client.get(f"/animals/{data['animal'].id}/zoos", params=params)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 2
    assert body[0]["id"] == str(data["zoo"].id)
    dists = [z["distance_km"] for z in body]
    assert dists == sorted(dists)

def test_animal_zoos_invalid_params(data):
    """Invalid animal ids or coordinates should fail."""
    bad = client.get(f"/animals/{uuid.uuid4()}/zoos")
    assert bad.status_code == 404

    params = {"latitude": 200, "longitude": 0}
    resp = client.get(f"/animals/{data['animal'].id}/zoos", params=params)
    assert resp.status_code == 400

    params = {"latitude": 0, "longitude": 200}
    resp = client.get(f"/animals/{data['animal'].id}/zoos", params=params)
    assert resp.status_code == 400

