import uuid
from datetime import UTC, datetime

import pytest

from app import models
from app.database import SessionLocal

from .conftest import client, register_and_login


def test_get_animal_detail_success(data):
    resp = client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(data["animal"].id)
    assert body["slug"] == data["animal"].slug
    assert body["zoos"][0]["id"] == str(data["zoo"].id)
    assert body["zoos"][0]["slug"] == data["zoo"].slug
    # distance should be included but undefined without coordinates
    assert body["zoos"][0]["distance_km"] is None
    assert body["zoos"][0]["city"] == "Metropolis"
    assert body["is_favorite"] is False


def test_get_animal_detail_includes_name_de(data):
    resp = client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert "name_de" in body


def test_get_animal_detail_includes_description_en(data):
    resp = client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["description_en"] == "King of the jungle"


def test_get_animal_detail_zoos_include_coordinates(data):
    resp = client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    zoos = resp.json()["zoos"]
    assert zoos, "expected at least one zoo in the animal detail response"
    for zoo in zoos:
        assert "latitude" in zoo
        assert "longitude" in zoo
        assert zoo["latitude"] is not None
        assert zoo["longitude"] is not None


def test_get_animal_detail_includes_taxon_names(data):
    resp = client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["class_name_en"] == "Mammals"
    assert body["order_name_de"] == "Raubtiere"
    assert body["family_name_en"] == "Cats"


def test_get_animal_detail_includes_images(data):
    resp = client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["images"]) == 2
    assert body["images"][0]["variants"][0]["thumb_url"].startswith(
        "http://example.com/"
    )
    assert "commons_page_url" not in body["images"][0]
    assert "commons_title" not in body["images"][0]


def test_get_animal_detail_variants_sorted(data):
    resp = client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    variants = resp.json()["images"][0]["variants"]
    widths = [v["width"] for v in variants]
    # Variants should be returned in ascending width order
    assert widths == sorted(widths)
    assert 320 in widths and 640 in widths


def test_get_animal_detail_includes_parent_metadata(data):
    subspecies = data["lion_subspecies"]
    resp = client.get(f"/animals/{subspecies.slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["parent"] is not None
    assert body["parent"]["slug"] == data["animal"].slug
    assert body["parent"]["scientific_name"] == data["animal"].scientific_name
    assert body["subspecies"] == []


def test_parent_species_lists_subspecies(data):
    resp = client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    subspecies = resp.json()["subspecies"]
    assert any(child["slug"] == data["lion_subspecies"].slug for child in subspecies)
    child_entry = next(
        child for child in subspecies if child["slug"] == data["lion_subspecies"].slug
    )
    assert child_entry["scientific_name"] == data["lion_subspecies"].scientific_name


def test_list_animals_includes_name_de(data):
    resp = client.get("/animals", params={"limit": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert "name_de" in body[0]
    assert "slug" in body[0]


def test_get_animal_detail_with_distance(data):
    params = {"latitude": data["zoo"].latitude, "longitude": data["zoo"].longitude}
    resp = client.get(f"/animals/{data['animal'].slug}", params=params)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["zoos"]) == 1
    assert body["zoos"][0]["id"] == str(data["zoo"].id)
    assert body["zoos"][0]["slug"] == data["zoo"].slug
    assert body["zoos"][0]["distance_km"] == 0
    assert body["zoos"][0]["city"] == "Metropolis"


def test_get_animal_detail_invalid_params(data):
    bad = client.get(
        f"/animals/{data['animal'].slug}", params={"latitude": 200, "longitude": 0}
    )
    assert bad.status_code == 400


def test_get_animal_detail_lon_invalid(data):
    resp = client.get(
        f"/animals/{data['animal'].slug}", params={"latitude": 0, "longitude": 200}
    )
    assert resp.status_code == 400


def test_get_animal_detail_coords_must_be_pair(data):
    resp = client.get(f"/animals/{data['animal'].slug}", params={"latitude": 0})
    assert resp.status_code == 400
    resp = client.get(f"/animals/{data['animal'].slug}", params={"longitude": 0})
    assert resp.status_code == 400


def test_get_animal_detail_not_found():
    resp = client.get("/animals/not-found")
    assert resp.status_code == 404


def test_cf_headers_used(data):
    headers = {
        "cf-iplatitude": str(data["zoo"].latitude),
        "cf-iplongitude": str(data["zoo"].longitude),
    }
    resp = client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["zoos"][0]["slug"] == data["zoo"].slug
    assert body["zoos"][0]["distance_km"] == 0


def test_invalid_cf_headers_ignored(data):
    headers = {"cf-iplatitude": "not-a-number", "cf-iplongitude": "20"}
    resp = client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["zoos"][0]["slug"] == data["zoo"].slug
    assert body["zoos"][0]["distance_km"] is None


def test_explicit_coords_override_cf_headers(data):
    headers = {"cf-iplatitude": "0", "cf-iplongitude": "0"}
    params = {
        "latitude": data["zoo"].latitude,
        "longitude": data["zoo"].longitude,
    }
    resp = client.get(f"/animals/{data['animal'].slug}", headers=headers, params=params)
    assert resp.status_code == 200
    assert resp.json()["zoos"][0]["distance_km"] == 0


def test_only_one_cf_header_is_ignored(data):
    headers = {"cf-iplatitude": str(data["zoo"].latitude)}
    resp = client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["zoos"][0]["distance_km"] is None


def test_out_of_range_cf_headers_ignored(data):
    headers = {"cf-iplatitude": "91", "cf-iplongitude": "0"}
    resp = client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["zoos"][0]["distance_km"] is None


def test_animal_sightings_require_auth(data):
    resp = client.get(f"/animals/{data['animal'].slug}/sightings")
    assert resp.status_code == 401


def test_animal_sightings_return_user_history(data):
    token, _user_id = register_and_login()
    other_token, _other_user = register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    first_time = datetime(2024, 4, 12, 9, 45, tzinfo=UTC)
    second_time = datetime(2024, 6, 3, 18, 20, tzinfo=UTC)
    other_time = datetime(2024, 5, 1, 10, 0, tzinfo=UTC)

    client.post(
        "/sightings",
        json={
            "zoo_id": str(data["zoo"].id),
            "animal_id": str(data["animal"].id),
            "sighting_datetime": first_time.isoformat(),
            "notes": "Morning visit",
        },
        headers=headers,
    )
    client.post(
        "/sightings",
        json={
            "zoo_id": str(data["far_zoo"].id),
            "animal_id": str(data["animal"].id),
            "sighting_datetime": second_time.isoformat(),
            "notes": "Evening encounter",
        },
        headers=headers,
    )
    client.post(
        "/sightings",
        json={
            "zoo_id": str(data["zoo"].id),
            "animal_id": str(data["animal"].id),
            "sighting_datetime": other_time.isoformat(),
            "notes": "Different user",
        },
        headers={"Authorization": f"Bearer {other_token}"},
    )
    client.post(
        "/sightings",
        json={
            "zoo_id": str(data["zoo"].id),
            "animal_id": str(data["tiger"].id),
            "sighting_datetime": other_time.isoformat(),
            "notes": "Another species",
        },
        headers=headers,
    )

    resp = client.get(
        f"/animals/{data['animal'].slug}/sightings",
        headers=headers,
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 2
    assert payload["limit"] == 50
    assert payload["offset"] == 0
    assert resp.headers["X-Total-Count"] == "2"
    assert resp.headers["Cache-Control"] == "private, no-store, max-age=0"
    assert resp.headers["Vary"] == "Authorization"

    items = payload["items"]
    assert len(items) == 2
    assert items[0]["zoo_id"] == str(data["far_zoo"].id)
    assert items[0]["notes"] == "Evening encounter"
    assert items[0]["sighting_datetime"].startswith("2024-06-03")
    assert items[1]["zoo_id"] == str(data["zoo"].id)
    assert items[1]["notes"] == "Morning visit"
    assert items[1]["sighting_datetime"].startswith("2024-04-12")


def test_animal_sightings_pagination(data):
    token, _user_id = register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    times = [
        datetime(2024, 7, 10, 8, 0, tzinfo=UTC),
        datetime(2024, 7, 9, 11, 30, tzinfo=UTC),
        datetime(2024, 7, 8, 14, 15, tzinfo=UTC),
    ]

    for index, moment in enumerate(times):
        client.post(
            "/sightings",
            json={
                "zoo_id": str(data["zoo"].id if index % 2 == 0 else data["far_zoo"].id),
                "animal_id": str(data["animal"].id),
                "sighting_datetime": moment.isoformat(),
                "notes": f"History {index}",
            },
            headers=headers,
        )

    resp = client.get(
        f"/animals/{data['animal'].slug}/sightings",
        params={"limit": 2, "offset": 0},
        headers=headers,
    )
    assert resp.status_code == 200
    page = resp.json()
    assert page["total"] == 3
    assert len(page["items"]) == 2
    first, second = page["items"]
    assert first["sighting_datetime"].startswith("2024-07-10")
    assert second["sighting_datetime"].startswith("2024-07-09")

    resp_next = client.get(
        f"/animals/{data['animal'].slug}/sightings",
        params={"limit": 2, "offset": 2},
        headers=headers,
    )
    assert resp_next.status_code == 200
    next_page = resp_next.json()
    assert next_page["total"] == 3
    assert len(next_page["items"]) == 1
    assert next_page["items"][0]["sighting_datetime"].startswith("2024-07-08")


def test_list_animals_returns_details_and_pagination(data):
    resp = client.get("/animals", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert [a["slug"] for a in body] == [
        data["animal"].slug,
        data["lion_subspecies"].slug,
    ]
    lion = body[0]
    assert lion["zoo_count"] == 1
    assert lion["slug"]
    assert lion["is_favorite"] is False

    subspecies = body[1]
    assert subspecies["zoo_count"] == 0
    assert subspecies["scientific_name"] == data["lion_subspecies"].scientific_name
    assert subspecies["category"] == "Mammal"
    assert subspecies["slug"]
    assert subspecies["is_favorite"] is False

    resp2 = client.get("/animals", params={"limit": 2, "offset": 2})
    assert resp2.status_code == 200
    body2 = resp2.json()
    assert len(body2) == 2
    eagle = body2[0]
    assert eagle["scientific_name"] == "Aquila chrysaetos"
    assert eagle["category"] == "Bird"
    assert eagle["default_image_url"].startswith("http://example.com/")
    assert eagle["slug"]
    assert eagle["zoo_count"] == 0
    assert eagle["is_favorite"] is False

    tiger = body2[1]
    assert tiger["scientific_name"] == "Panthera tigris"
    assert tiger["slug"]
    assert tiger["zoo_count"] == 0
    assert tiger["is_favorite"] is False


def test_list_animals_tiebreaker_uses_id_when_names_match(data):
    session = SessionLocal()
    try:
        base_category = data["animal"].category_id
        first_id = uuid.UUID("00000000-0000-0000-0000-000000000010")
        second_id = uuid.UUID("00000000-0000-0000-0000-000000000011")
        first = models.Animal(
            id=first_id,
            name_en="Aardwolf",
            name_de="Aardwolf",
            slug="aardwolf-alpha",
            category_id=base_category,
            zoo_count=0,
        )
        second = models.Animal(
            id=second_id,
            name_en="Aardwolf",
            name_de="Aardwolf",
            slug="aardwolf-beta",
            category_id=base_category,
            zoo_count=0,
        )
        session.add_all([first, second])
        session.commit()

        resp = client.get("/animals", params={"limit": 5, "offset": 0})
        assert resp.status_code == 200
        body = resp.json()
        slugs = [a["slug"] for a in body]
        first_index = slugs.index("aardwolf-alpha")
        second_index = slugs.index("aardwolf-beta")
        assert second_index == first_index + 1
    finally:
        (
            session.query(models.Animal)
            .filter(models.Animal.slug.in_(["aardwolf-alpha", "aardwolf-beta"]))
            .delete(synchronize_session=False)
        )
        session.commit()
        session.close()


def test_list_animals_invalid_pagination():
    assert client.get("/animals", params={"limit": 0}).status_code == 422


def test_list_animals_invalid_pagination_upper_bound():
    assert client.get("/animals", params={"limit": 101}).status_code == 422


def test_list_animals_invalid_offset():
    assert client.get("/animals", params={"offset": -1}).status_code == 422


def test_list_animals_category_filter():
    resp = client.get("/animals", params={"category": "Mammal"})
    assert resp.status_code == 200
    names = [a["name_en"] for a in resp.json()]
    assert names == ["Lion", "Asiatic Lion", "Tiger"]

    resp = client.get("/animals", params={"category": "Bird"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name_en"] == "Eagle"


def test_list_animals_empty_page():
    resp = client.get("/animals", params={"limit": 5, "offset": 10})
    assert resp.status_code == 200
    assert resp.json() == []


def test_taxonomy_endpoints_and_filters(data):
    classes = client.get("/animals/classes").json()
    assert classes == [{"id": 1, "name_de": "S\u00e4ugetiere", "name_en": "Mammals"}]

    orders = client.get("/animals/orders", params={"class_id": 1}).json()
    assert orders == [{"id": 1, "name_de": "Raubtiere", "name_en": "Carnivorans"}]

    families = client.get("/animals/families", params={"order_id": 1}).json()
    assert families == [{"id": 1, "name_de": "Katzen", "name_en": "Cats"}]

    resp = client.get("/animals", params={"class_id": 1})
    names = [a["name_en"] for a in resp.json()]
    assert names == ["Lion"]

    resp = client.get("/animals", params={"order_id": 1})
    names = [a["name_en"] for a in resp.json()]
    assert names == ["Lion"]

    resp = client.get("/animals", params={"family_id": 1})
    names = [a["name_en"] for a in resp.json()]
    assert names == ["Lion"]


def test_list_animals_invalid_order_for_class(data):
    resp = client.get("/animals", params={"class_id": 1, "order_id": 999})
    assert resp.status_code == 400


def test_list_animals_invalid_family_for_order(data):
    resp = client.get("/animals", params={"order_id": 1, "family_id": 999})
    assert resp.status_code == 400


def test_animal_favorites_flow(data):
    token, _ = register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.put(
        f"/animals/{data['animal'].slug}/favorite",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"favorite": True}

    fav_resp = client.get(
        "/animals", params={"favorites_only": "true"}, headers=headers
    )
    assert fav_resp.status_code == 200
    favorites = fav_resp.json()
    assert len(favorites) == 1
    assert favorites[0]["id"] == str(data["animal"].id)
    assert favorites[0]["is_favorite"] is True

    detail_resp = client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["is_favorite"] is True

    resp = client.delete(
        f"/animals/{data['animal'].slug}/favorite",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"favorite": False}

    cleared = client.get("/animals", params={"favorites_only": "true"}, headers=headers)
    assert cleared.status_code == 200
    assert cleared.json() == []

    detail_after = client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert detail_after.status_code == 200
    assert detail_after.json()["is_favorite"] is False


def test_animal_detail_marks_favorite_zoos(data):
    token, _ = register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    fav_resp = client.put(f"/zoos/{data['zoo'].slug}/favorite", headers=headers)
    assert fav_resp.status_code == 200

    detail_resp = client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert detail_resp.status_code == 200
    zoos = detail_resp.json()["zoos"]
    assert zoos, "expected at least one zoo for the animal detail response"
    target = next(z for z in zoos if z["id"] == str(data["zoo"].id))
    assert target["is_favorite"] is True


def test_animal_favorites_filter_requires_auth():
    resp = client.get("/animals", params={"favorites_only": "true"})
    assert resp.status_code == 401


def test_animals_personalized_responses_disable_caching(data):
    token, _ = register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/animals", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "private, no-store, max-age=0"
    assert "Authorization" in resp.headers["vary"]

    detail = client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert detail.status_code == 200
    assert detail.headers["cache-control"] == "private, no-store, max-age=0"
    assert "Authorization" in detail.headers["vary"]


@pytest.mark.postgres
def test_get_animal_detail_with_distance_postgres(data):
    params = {"latitude": data["zoo"].latitude, "longitude": data["zoo"].longitude}
    resp = client.get(f"/animals/{data['animal'].slug}", params=params)
    assert resp.status_code == 200
    body = resp.json()
    assert body["zoos"][0]["distance_km"] == 0
