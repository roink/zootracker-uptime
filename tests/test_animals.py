import uuid
from datetime import UTC, datetime

import pytest

from app import models
from app.database import SessionLocal

from .conftest import register_and_login


# Helper to get a specific zoo entry without depending on overall order
def _get_zoo(zoos: list[dict], slug: str) -> dict:
    return next(z for z in zoos if z["slug"] == slug)


async def test_get_animal_detail_success(client, data):
    resp = await client.get(f"/animals/{data['animal'].slug}")
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

    # With enriched seed, parent+subspecies aggregation should include both zoos
    assert {z["id"] for z in body["zoos"]} == {
        str(data["zoo"].id),
        str(data["far_zoo"].id),
    }


async def test_get_animal_detail_includes_name_de(client, data):
    resp = await client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert "name_de" in body


async def test_get_animal_detail_includes_description_en(client, data):
    resp = await client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["description_en"] == "King of the jungle"


async def test_get_animal_detail_zoos_include_coordinates(client, data):
    resp = await client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    zoos = resp.json()["zoos"]
    assert zoos, "expected at least one zoo in the animal detail response"
    for zoo in zoos:
        assert "latitude" in zoo
        assert "longitude" in zoo
        assert zoo["latitude"] is not None
        assert zoo["longitude"] is not None


async def test_get_animal_detail_includes_taxon_names(client, data):
    resp = await client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["class_name_en"] == "Mammals"
    assert body["order_name_de"] == "Raubtiere"
    assert body["family_name_en"] == "Cats"


async def test_get_animal_detail_includes_images(client, data):
    resp = await client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["images"]) == 2
    assert body["images"][0]["variants"][0]["thumb_url"].startswith(
        "http://example.com/"
    )
    assert "commons_page_url" not in body["images"][0]
    assert "commons_title" not in body["images"][0]


async def test_get_animal_detail_variants_sorted(client, data):
    resp = await client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    variants = resp.json()["images"][0]["variants"]
    widths = [v["width"] for v in variants]
    # Variants should be returned in ascending width order
    assert widths == sorted(widths)
    assert 320 in widths and 640 in widths


async def test_get_animal_detail_includes_parent_metadata(client, data):
    subspecies = data["lion_subspecies"]
    resp = await client.get(f"/animals/{subspecies.slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["parent"] is not None
    assert body["parent"]["slug"] == data["animal"].slug
    assert body["parent"]["scientific_name"] == data["animal"].scientific_name
    assert body["subspecies"] == []


async def test_parent_species_lists_subspecies(client, data):
    resp = await client.get(f"/animals/{data['animal'].slug}")
    assert resp.status_code == 200
    subspecies = resp.json()["subspecies"]
    assert any(child["slug"] == data["lion_subspecies"].slug for child in subspecies)
    child_entry = next(
        child for child in subspecies if child["slug"] == data["lion_subspecies"].slug
    )
    assert child_entry["scientific_name"] == data["lion_subspecies"].scientific_name


async def test_parent_species_includes_subspecies_zoos_deduped(client, data):
    """
    If a zoo keeps both the parent species and a subspecies, it should appear only once
    in the parent's aggregated zoos list.
    """
    session = SessionLocal()
    combo = None
    try:
        combo = models.Zoo(
            name="Combo Zoo",
            slug="combo-zoo",
            city="Overlap City",
            continent_id=data["zoo"].continent_id,
            country_id=data["zoo"].country_id,
            latitude=30.0,
            longitude=40.0,
        )
        session.add(combo)
        session.commit()
        session.refresh(combo)
        session.add_all(
            [
                models.ZooAnimal(zoo_id=combo.id, animal_id=data["animal"].id),
                models.ZooAnimal(
                    zoo_id=combo.id, animal_id=data["lion_subspecies"].id
                ),
            ]
        )
        session.commit()

        resp = await client.get(f"/animals/{data['animal'].slug}")
        assert resp.status_code == 200
        slugs = [z["slug"] for z in resp.json()["zoos"]]
        assert slugs.count("combo-zoo") == 1
    finally:
        if combo is not None:
            session.query(models.ZooAnimal).filter(
                models.ZooAnimal.zoo_id == combo.id
            ).delete(synchronize_session=False)
            session.query(models.Zoo).filter(models.Zoo.id == combo.id).delete()
            session.commit()
        session.close()


async def test_subspecies_only_lists_own_zoos(client, data):
    resp = await client.get(f"/animals/{data['lion_subspecies'].slug}")
    assert resp.status_code == 200
    zoos = resp.json()["zoos"]
    assert {z["id"] for z in zoos} == {
        str(data["zoo"].id),
        str(data["far_zoo"].id),
    }


async def test_subspecies_ignores_parent_only_zoos(client, data):
    """
    A zoo that keeps only the parent species should NOT appear on a subspecies page.
    """
    session = SessionLocal()
    parent_only_zoo = models.Zoo(
        name="Parent Only Habitat",
        slug="parent-only-habitat",
        address="789 Parent St",
        latitude=15.0,
        longitude=25.0,
        description_en="Parent species only",
        description_de="Nur Eltern",
        city="Parentville",
        continent_id=data["zoo"].continent_id,
        country_id=data["zoo"].country_id,
    )
    try:
        session.add(parent_only_zoo)
        session.commit()
        session.refresh(parent_only_zoo)
        session.add(
            models.ZooAnimal(zoo_id=parent_only_zoo.id, animal_id=data["animal"].id)
        )
        session.commit()

        parent_resp = await client.get(f"/animals/{data['animal'].slug}")
        assert parent_resp.status_code == 200
        parent_slugs = {z["slug"] for z in parent_resp.json()["zoos"]}
        assert parent_only_zoo.slug in parent_slugs

        subspecies_resp = await client.get(f"/animals/{data['lion_subspecies'].slug}")
        assert subspecies_resp.status_code == 200
        subspecies_slugs = {z["slug"] for z in subspecies_resp.json()["zoos"]}
        assert parent_only_zoo.slug not in subspecies_slugs
    finally:
        session.query(models.ZooAnimal).filter(
            models.ZooAnimal.zoo_id == parent_only_zoo.id
        ).delete(synchronize_session=False)
        session.query(models.Zoo).filter(
            models.Zoo.id == parent_only_zoo.id
        ).delete()
        session.commit()
        session.close()


async def test_parent_species_without_direct_zoos_uses_subspecies(client, data):
    """
    If a parent species has no direct zoo links, the parent's page should still
    surface zoos via its subspecies.
    """
    session = SessionLocal()
    parent = models.Animal(
        name_en="Ghost Lion",
        scientific_name="Panthera leo ghost",
        category_id=data["animal"].category_id,
        slug="ghost-lion",
        art=9001,
    )
    child = models.Animal(
        name_en="Ghost Lion Subspecies",
        scientific_name="Panthera leo ghost subspecies",
        category_id=data["animal"].category_id,
        slug="ghost-lion-sub",
        art=9002,
        parent_art=9001,
    )
    try:
        session.add_all([parent, child])
        session.commit()
        session.refresh(parent)
        session.refresh(child)
        session.add(models.ZooAnimal(zoo_id=data["far_zoo"].id, animal_id=child.id))
        session.commit()

        resp = await client.get(f"/animals/{parent.slug}")
        assert resp.status_code == 200
        slugs = {z["slug"] for z in resp.json()["zoos"]}
        assert data["far_zoo"].slug in slugs
    finally:
        session.query(models.ZooAnimal).filter(
            models.ZooAnimal.animal_id == child.id
        ).delete(synchronize_session=False)
        session.query(models.Animal).filter(
            models.Animal.id.in_([child.id, parent.id])
        ).delete(synchronize_session=False)
        session.commit()
        session.close()
async def test_list_animals_includes_name_de(client, data):
    resp = await client.get("/animals", params={"limit": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert "name_de" in body[0]
    assert "slug" in body[0]


async def test_get_animal_detail_with_distance(client, data):
    params = {"latitude": data["zoo"].latitude, "longitude": data["zoo"].longitude}
    resp = await client.get(f"/animals/{data['animal'].slug}", params=params)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["zoos"]) >= 2, "expect aggregated zoos for parent species"
    first = _get_zoo(body["zoos"], data["zoo"].slug)
    assert first["id"] == str(data["zoo"].id)
    assert first["slug"] == data["zoo"].slug
    # nearest first when coordinates are present
    assert first["distance_km"] == 0
    assert first["city"] == "Metropolis"
    ids = [z["id"] for z in body["zoos"]]
    assert str(data["far_zoo"].id) in ids


async def test_parent_species_distance_sorting_with_subspecies(client, data):
    """
    When distance sorting is active, verify nearest zoo is first and the farther
    child-only zoo has distance > 0 in the aggregated view.
    """
    session = SessionLocal()
    try:
        # Ensure the subspecies is present in both central and far zoos
        session.merge(
            models.ZooAnimal(
                zoo_id=data["zoo"].id, animal_id=data["lion_subspecies"].id
            )
        )
        session.merge(
            models.ZooAnimal(
                zoo_id=data["far_zoo"].id, animal_id=data["lion_subspecies"].id
            )
        )
        session.commit()

        params = {
            "latitude": data["zoo"].latitude,
            "longitude": data["zoo"].longitude,
        }
        resp = await client.get(f"/animals/{data['animal'].slug}", params=params)
        assert resp.status_code == 200
        zoos = resp.json()["zoos"]
        assert _get_zoo(zoos, data["zoo"].slug)["distance_km"] == 0
        assert _get_zoo(zoos, data["far_zoo"].slug)["distance_km"] > 0
    finally:
        session.close()


async def test_get_animal_detail_invalid_params(client, data):
    bad = await client.get(
        f"/animals/{data['animal'].slug}", params={"latitude": 200, "longitude": 0}
    )
    assert bad.status_code == 400


async def test_get_animal_detail_lon_invalid(client, data):
    resp = await client.get(
        f"/animals/{data['animal'].slug}", params={"latitude": 0, "longitude": 200}
    )
    assert resp.status_code == 400


async def test_get_animal_detail_coords_must_be_pair(client, data):
    resp = await client.get(f"/animals/{data['animal'].slug}", params={"latitude": 0})
    assert resp.status_code == 400
    resp = await client.get(f"/animals/{data['animal'].slug}", params={"longitude": 0})
    assert resp.status_code == 400


async def test_get_animal_detail_not_found(client):
    resp = await client.get("/animals/not-found")
    assert resp.status_code == 404


async def test_cf_headers_used(client, data):
    headers = {
        "cf-iplatitude": str(data["zoo"].latitude),
        "cf-iplongitude": str(data["zoo"].longitude),
    }
    resp = await client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["zoos"][0]["slug"] == data["zoo"].slug
    assert body["zoos"][0]["distance_km"] == 0


async def test_invalid_cf_headers_ignored(client, data):
    headers = {"cf-iplatitude": "not-a-number", "cf-iplongitude": "20"}
    resp = await client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["zoos"][0]["slug"] == data["zoo"].slug
    assert body["zoos"][0]["distance_km"] is None


async def test_explicit_coords_override_cf_headers(client, data):
    headers = {"cf-iplatitude": "0", "cf-iplongitude": "0"}
    params = {
        "latitude": data["zoo"].latitude,
        "longitude": data["zoo"].longitude,
    }
    resp = await client.get(f"/animals/{data['animal'].slug}", headers=headers, params=params)
    assert resp.status_code == 200
    assert resp.json()["zoos"][0]["distance_km"] == 0


async def test_only_one_cf_header_is_ignored(client, data):
    headers = {"cf-iplatitude": str(data["zoo"].latitude)}
    resp = await client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["zoos"][0]["distance_km"] is None


async def test_out_of_range_cf_headers_ignored(client, data):
    headers = {"cf-iplatitude": "91", "cf-iplongitude": "0"}
    resp = await client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["zoos"][0]["distance_km"] is None


async def test_animal_sightings_require_auth(client, data):
    resp = await client.get(f"/animals/{data['animal'].slug}/sightings")
    assert resp.status_code == 401


async def test_animal_sightings_return_user_history(client, data):
    token, _user_id = await register_and_login()
    other_token, _other_user = await register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    first_time = datetime(2024, 4, 12, 9, 45, tzinfo=UTC)
    second_time = datetime(2024, 6, 3, 18, 20, tzinfo=UTC)
    other_time = datetime(2024, 5, 1, 10, 0, tzinfo=UTC)

    await client.post(
        "/sightings",
        json={
            "zoo_id": str(data["zoo"].id),
            "animal_id": str(data["animal"].id),
            "sighting_datetime": first_time.isoformat(),
            "notes": "Morning visit",
        },
        headers=headers,
    )
    await client.post(
        "/sightings",
        json={
            "zoo_id": str(data["far_zoo"].id),
            "animal_id": str(data["animal"].id),
            "sighting_datetime": second_time.isoformat(),
            "notes": "Evening encounter",
        },
        headers=headers,
    )
    await client.post(
        "/sightings",
        json={
            "zoo_id": str(data["zoo"].id),
            "animal_id": str(data["animal"].id),
            "sighting_datetime": other_time.isoformat(),
            "notes": "Different user",
        },
        headers={"Authorization": f"Bearer {other_token}"},
    )
    await client.post(
        "/sightings",
        json={
            "zoo_id": str(data["zoo"].id),
            "animal_id": str(data["tiger"].id),
            "sighting_datetime": other_time.isoformat(),
            "notes": "Another species",
        },
        headers=headers,
    )

    resp = await client.get(
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


async def test_animal_sightings_pagination(client, data):
    token, _user_id = await register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    times = [
        datetime(2024, 7, 10, 8, 0, tzinfo=UTC),
        datetime(2024, 7, 9, 11, 30, tzinfo=UTC),
        datetime(2024, 7, 8, 14, 15, tzinfo=UTC),
    ]

    for index, moment in enumerate(times):
        await client.post(
            "/sightings",
            json={
                "zoo_id": str(data["zoo"].id if index % 2 == 0 else data["far_zoo"].id),
                "animal_id": str(data["animal"].id),
                "sighting_datetime": moment.isoformat(),
                "notes": f"History {index}",
            },
            headers=headers,
        )

    resp = await client.get(
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

    resp_next = await client.get(
        f"/animals/{data['animal'].slug}/sightings",
        params={"limit": 2, "offset": 2},
        headers=headers,
    )
    assert resp_next.status_code == 200
    next_page = resp_next.json()
    assert next_page["total"] == 3
    assert len(next_page["items"]) == 1
    assert next_page["items"][0]["sighting_datetime"].startswith("2024-07-08")


async def test_list_animals_returns_details_and_pagination(client, data):
    resp = await client.get("/animals", params={"limit": 2, "offset": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert [a["slug"] for a in body] == [
        data["lion_subspecies"].slug,
        data["animal"].slug,
    ]
    entries = {item["slug"]: item for item in body}
    lion = entries[data["animal"].slug]
    assert lion["zoo_count"] == 1
    assert lion["slug"]
    assert lion["is_favorite"] is False

    subspecies = entries[data["lion_subspecies"].slug]
    assert subspecies["zoo_count"] == 2  # now present in two zoos in seed
    assert subspecies["scientific_name"] == data["lion_subspecies"].scientific_name
    assert subspecies["category"] == "Mammal"
    assert subspecies["slug"]
    assert subspecies["is_favorite"] is False

    resp2 = await client.get("/animals", params={"limit": 2, "offset": 2})
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


async def test_list_animals_tiebreaker_uses_id_when_names_match(client, data):
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

        resp = await client.get("/animals", params={"limit": 5, "offset": 0})
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


async def test_list_animals_invalid_pagination(client):
    assert await client.get("/animals", params={"limit": 0}).status_code == 422


async def test_list_animals_invalid_pagination_upper_bound(client):
    assert await client.get("/animals", params={"limit": 101}).status_code == 422


async def test_list_animals_invalid_offset(client):
    assert await client.get("/animals", params={"offset": -1}).status_code == 422


async def test_list_animals_category_filter(client):
    resp = await client.get("/animals", params={"category": "Mammal"})
    assert resp.status_code == 200
    names = [a["name_en"] for a in resp.json()]
    assert names == ["Asiatic Lion", "Lion", "Tiger"]

    resp = await client.get("/animals", params={"category": "Bird"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["name_en"] == "Eagle"


async def test_list_animals_empty_page(client):
    resp = await client.get("/animals", params={"limit": 5, "offset": 10})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_taxonomy_endpoints_and_filters(client, data):
    classes = await client.get("/animals/classes").json()
    assert classes == [{"id": 1, "name_de": "S\u00e4ugetiere", "name_en": "Mammals"}]

    orders = await client.get("/animals/orders", params={"class_id": 1}).json()
    assert orders == [{"id": 1, "name_de": "Raubtiere", "name_en": "Carnivorans"}]

    families = await client.get("/animals/families", params={"order_id": 1}).json()
    assert families == [{"id": 1, "name_de": "Katzen", "name_en": "Cats"}]

    resp = await client.get("/animals", params={"class_id": 1})
    names = [a["name_en"] for a in resp.json()]
    assert names == ["Lion"]

    resp = await client.get("/animals", params={"order_id": 1})
    names = [a["name_en"] for a in resp.json()]
    assert names == ["Lion"]

    resp = await client.get("/animals", params={"family_id": 1})
    names = [a["name_en"] for a in resp.json()]
    assert names == ["Lion"]


async def test_list_animals_invalid_order_for_class(client, data):
    resp = await client.get("/animals", params={"class_id": 1, "order_id": 999})
    assert resp.status_code == 400


async def test_list_animals_invalid_family_for_order(client, data):
    resp = await client.get("/animals", params={"order_id": 1, "family_id": 999})
    assert resp.status_code == 400


async def test_animal_favorites_flow(client, data):
    token, _ = await register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.put(
        f"/animals/{data['animal'].slug}/favorite",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"favorite": True}

    fav_resp = await client.get(
        "/animals", params={"favorites_only": "true"}, headers=headers
    )
    assert fav_resp.status_code == 200
    favorites = fav_resp.json()
    assert len(favorites) == 1
    assert favorites[0]["id"] == str(data["animal"].id)
    assert favorites[0]["is_favorite"] is True

    detail_resp = await client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["is_favorite"] is True

    resp = await client.delete(
        f"/animals/{data['animal'].slug}/favorite",
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"favorite": False}

    cleared = await client.get("/animals", params={"favorites_only": "true"}, headers=headers)
    assert cleared.status_code == 200
    assert cleared.json() == []

    detail_after = await client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert detail_after.status_code == 200
    assert detail_after.json()["is_favorite"] is False


async def test_animal_detail_marks_favorite_zoos(client, data):
    token, _ = await register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    fav_resp = await client.put(f"/zoos/{data['zoo'].slug}/favorite", headers=headers)
    assert fav_resp.status_code == 200

    detail_resp = await client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert detail_resp.status_code == 200
    zoos = detail_resp.json()["zoos"]
    assert zoos, "expected at least one zoo for the animal detail response"
    target = next(z for z in zoos if z["id"] == str(data["zoo"].id))
    assert target["is_favorite"] is True


async def test_animal_favorites_filter_requires_auth(client):
    resp = await client.get("/animals", params={"favorites_only": "true"})
    assert resp.status_code == 401


async def test_animals_personalized_responses_disable_caching(client, data):
    token, _ = await register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/animals", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "private, no-store, max-age=0"
    assert "Authorization" in resp.headers["vary"]

    detail = await client.get(f"/animals/{data['animal'].slug}", headers=headers)
    assert detail.status_code == 200
    assert detail.headers["cache-control"] == "private, no-store, max-age=0"
    assert "Authorization" in detail.headers["vary"]


@pytest.mark.postgres
async def test_get_animal_detail_with_distance_postgres(client, data):
    params = {"latitude": data["zoo"].latitude, "longitude": data["zoo"].longitude}
    resp = await client.get(f"/animals/{data['animal'].slug}", params=params)
    assert resp.status_code == 200
    body = resp.json()
    assert body["zoos"][0]["distance_km"] == 0
