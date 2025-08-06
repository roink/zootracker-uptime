import uuid
from .conftest import client

def test_get_animal_detail_success(data):
    resp = client.get(f"/animals/{data['animal'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(data["animal"].id)
    assert body["zoos"][0]["id"] == str(data["zoo"].id)

def test_get_animal_detail_not_found():
    resp = client.get(f"/animals/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_list_animals_returns_details_and_pagination(data):
    resp = client.get("/animals", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert [a["common_name"] for a in body] == ["Eagle", "Lion"]
    item = body[0]
    assert item["scientific_name"] == "Aquila chrysaetos"
    assert item["category"] == "Bird"
    assert item["default_image_url"].startswith("http://example.com/")

    resp2 = client.get("/animals", params={"limit": 2, "offset": 2})
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert len(body2) == 1
    assert body2[0]["scientific_name"] == "Panthera tigris"


def test_list_animals_invalid_pagination():
    assert client.get("/animals", params={"limit": 0}).status_code == 400
    assert client.get("/animals", params={"limit": 101}).status_code == 400
    assert client.get("/animals", params={"offset": -1}).status_code == 400


def test_list_animals_category_filter():
    resp = client.get("/animals", params={"category": "Mammal"})
    assert resp.status_code == 200
    names = [a["common_name"] for a in resp.json()]
    assert names == ["Lion", "Tiger"]

    resp = client.get("/animals", params={"category": "Bird"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["common_name"] == "Eagle"
