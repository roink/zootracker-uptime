import uuid
from .conftest import client

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
    assert body["description_de"] == "Ein lustiger Ort"
    assert body["city"] == "Metropolis"

def test_get_zoo_invalid_id():
    resp = client.get(f"/zoos/{uuid.uuid4()}")
    assert resp.status_code == 404

def test_search_zoos_with_radius_returns_all(data):
    """Even with a radius parameter all zoos should be returned."""
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
    assert str(data["far_zoo"].id) in ids
    dists = [z["distance_km"] for z in body]
    assert dists == sorted(dists)
    assert any(z["city"] == "Metropolis" for z in body)


def test_search_zoos_without_radius_returns_all(data):
    """Supplying coordinates without a radius should return all zoos."""
    params = {
        "latitude": data["zoo"].latitude,
        "longitude": data["zoo"].longitude,
    }
    resp = client.get("/zoos", params=params)
    assert resp.status_code == 200
    ids = {z["id"] for z in resp.json()}
    assert str(data["zoo"].id) in ids
    assert str(data["far_zoo"].id) in ids

def test_search_zoos_name_only(data):
    """Name search should work without location parameters."""
    resp = client.get("/zoos", params={"q": "Central"})
    assert resp.status_code == 200
    names = [z["name"] for z in resp.json()]
    assert "Central Zoo" in names


def test_search_zoos_by_city(data):
    resp = client.get("/zoos", params={"q": data["zoo"].city})
    assert resp.status_code == 200
    names = [z["name"] for z in resp.json()]
    assert "Central Zoo" in names

