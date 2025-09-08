import uuid

import pytest

from .conftest import client

def test_get_animal_detail_success(data):
    resp = client.get(f"/animals/{data['animal'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(data["animal"].id)
    assert body["zoos"][0]["id"] == str(data["zoo"].id)
    # distance should be included but undefined without coordinates
    assert body["zoos"][0]["distance_km"] is None
    assert body["zoos"][0]["city"] == "Metropolis"


def test_get_animal_detail_includes_images(data):
    resp = client.get(f"/animals/{data['animal'].id}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["images"]) == 2
    assert body["images"][0]["variants"][0]["thumb_url"].startswith("http://example.com/")
    assert body["images"][0]["commons_page_url"].startswith("http://commons.org/")
    assert body["images"][0]["commons_title"] == "File:Lion.jpg"


def test_get_animal_detail_variants_sorted(data):
    resp = client.get(f"/animals/{data['animal'].id}")
    assert resp.status_code == 200
    variants = resp.json()["images"][0]["variants"]
    widths = [v["width"] for v in variants]
    # Variants should be returned in ascending width order
    assert widths == sorted(widths)
    assert 320 in widths and 640 in widths


def test_get_animal_detail_with_distance(data):
    params = {"latitude": data["zoo"].latitude, "longitude": data["zoo"].longitude}
    resp = client.get(f"/animals/{data['animal'].id}", params=params)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["zoos"]) == 1
    assert body["zoos"][0]["id"] == str(data["zoo"].id)
    assert body["zoos"][0]["distance_km"] == 0
    assert body["zoos"][0]["city"] == "Metropolis"


def test_get_animal_detail_invalid_params(data):
    bad = client.get(f"/animals/{data['animal'].id}", params={"latitude": 200, "longitude": 0})
    assert bad.status_code == 400


def test_get_animal_detail_lon_invalid(data):
    resp = client.get(
        f"/animals/{data['animal'].id}", params={"latitude": 0, "longitude": 200}
    )
    assert resp.status_code == 400


def test_get_animal_detail_coords_must_be_pair(data):
    resp = client.get(f"/animals/{data['animal'].id}", params={"latitude": 0})
    assert resp.status_code == 400
    resp = client.get(f"/animals/{data['animal'].id}", params={"longitude": 0})
    assert resp.status_code == 400

def test_get_animal_detail_not_found():
    resp = client.get(f"/animals/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_cf_headers_used(data):
    headers = {
        "cf-iplatitude": str(data["zoo"].latitude),
        "cf-iplongitude": str(data["zoo"].longitude),
    }
    resp = client.get(f"/animals/{data['animal'].id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["zoos"][0]["distance_km"] == 0


def test_invalid_cf_headers_ignored(data):
    headers = {"cf-iplatitude": "not-a-number", "cf-iplongitude": "20"}
    resp = client.get(f"/animals/{data['animal'].id}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["zoos"][0]["distance_km"] is None


def test_explicit_coords_override_cf_headers(data):
    headers = {"cf-iplatitude": "0", "cf-iplongitude": "0"}
    params = {
        "latitude": data["zoo"].latitude,
        "longitude": data["zoo"].longitude,
    }
    resp = client.get(
        f"/animals/{data['animal'].id}", headers=headers, params=params
    )
    assert resp.status_code == 200
    assert resp.json()["zoos"][0]["distance_km"] == 0


def test_only_one_cf_header_is_ignored(data):
    headers = {"cf-iplatitude": str(data["zoo"].latitude)}
    resp = client.get(f"/animals/{data['animal'].id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["zoos"][0]["distance_km"] is None


def test_out_of_range_cf_headers_ignored(data):
    headers = {"cf-iplatitude": "91", "cf-iplongitude": "0"}
    resp = client.get(f"/animals/{data['animal'].id}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["zoos"][0]["distance_km"] is None




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


def test_list_animals_invalid_pagination_upper_bound():
    assert client.get("/animals", params={"limit": 101}).status_code == 400


def test_list_animals_invalid_offset():
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


def test_list_animals_empty_page():
    resp = client.get("/animals", params={"limit": 5, "offset": 10})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.postgres
def test_get_animal_detail_with_distance_postgres(data):
    params = {"latitude": data["zoo"].latitude, "longitude": data["zoo"].longitude}
    resp = client.get(f"/animals/{data['animal'].id}", params=params)
    assert resp.status_code == 200
    body = resp.json()
    assert body["zoos"][0]["distance_km"] == 0
