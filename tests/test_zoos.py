from datetime import UTC, date, datetime

from .conftest import SessionLocal, models, register_and_login


def _extract_items(response_json):
    """Helper to unwrap paginated zoo responses."""

    if isinstance(response_json, dict) and "items" in response_json:
        return response_json["items"], response_json
    return (
        response_json,
        {
            "items": response_json,
            "total": len(response_json),
            "limit": len(response_json),
            "offset": 0,
        },
    )


async def test_get_animals_for_zoo(client, data):
    resp = await client.get(f"/zoos/{data['zoo'].slug}/animals")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 2
    items = payload["items"]
    assert len(items) == 2
    slugs = {animal["slug"] for animal in items}
    assert slugs == {data["animal"].slug, data["lion_subspecies"].slug}
    lion_entry = next(a for a in items if a["id"] == str(data["animal"].id))
    assert lion_entry["is_favorite"] is False
    assert lion_entry["seen"] is False
    facets = payload["facets"]
    assert facets["classes"]
    assert facets["orders"]
    assert facets["families"]


async def test_zoo_animal_search_and_taxonomy_filters(client, data):
    base_url = f"/zoos/{data['zoo'].slug}/animals"

    resp = await client.get(f"{base_url}?q=asiatic")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["total"] == 1
    assert payload["items"][0]["slug"] == data["lion_subspecies"].slug

    resp = await client.get(f"{base_url}?class=1")
    assert resp.status_code == 200
    class_payload = resp.json()
    assert class_payload["total"] == 1

    resp = await client.get(f"{base_url}?family=999")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


async def test_zoo_animal_seen_and_favorite_filters(client, data):
    token, _user_id = await register_and_login()
    headers = {"Authorization": f"Bearer {token}"}
    base_url = f"/zoos/{data['zoo'].slug}/animals"

    # Mark the lion as a favorite and log a sighting so both filters can be applied.
    fav_resp = await client.put(
        f"/animals/{data['animal'].slug}/favorite",
        headers=headers,
    )
    assert fav_resp.status_code == 200

    sighting_time = datetime(2024, 7, 1, 12, 0, tzinfo=UTC)
    log_resp = await client.post(
        "/sightings",
        json={
            "zoo_id": str(data["zoo"].id),
            "animal_id": str(data["animal"].id),
            "sighting_datetime": sighting_time.isoformat(),
            "notes": "Filter test sighting",
        },
        headers=headers,
    )
    assert log_resp.status_code == 200

    fav_filter = await client.get(f"{base_url}?favorites=1", headers=headers)
    assert fav_filter.status_code == 200
    fav_payload = fav_filter.json()
    assert fav_payload["total"] == 1
    assert fav_payload["items"][0]["id"] == str(data["animal"].id)
    assert fav_payload["items"][0]["is_favorite"] is True

    seen_filter = await client.get(f"{base_url}?seen=1", headers=headers)
    assert seen_filter.status_code == 200
    seen_payload = seen_filter.json()
    assert seen_payload["total"] == 1
    assert seen_payload["items"][0]["id"] == str(data["animal"].id)
    assert seen_payload["items"][0]["seen"] is True

    # Combine filters to ensure AND semantics.
    combined = await client.get(f"{base_url}?seen=1&favorites=1", headers=headers)
    assert combined.status_code == 200
    combined_payload = combined.json()
    assert combined_payload["total"] == 1
    assert combined_payload["items"][0]["id"] == str(data["animal"].id)
async def test_get_zoo_details(client, data):
    resp = await client.get(f"/zoos/{data['zoo'].slug}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(data["zoo"].id)
    assert body["slug"] == data["zoo"].slug
    assert body["address"] == "123 Zoo St"
    assert body["description_en"] == "A fun place"
    assert body["description_de"] == "Ein lustiger Ort"
    assert body["city"] == "Metropolis"
    assert body["is_favorite"] is False

async def test_get_zoo_invalid_id(client):
    resp = await client.get("/zoos/missing-zoo")
    assert resp.status_code == 404


async def test_zoo_sightings_require_auth(client, data):
    resp = await client.get(f"/zoos/{data['zoo'].slug}/sightings")
    assert resp.status_code == 401


async def test_zoo_sightings_return_user_history(client, data):
    token, _user_id = await register_and_login()
    other_token, _other_user_id = await register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    first_time = datetime(2024, 5, 1, 9, 30, tzinfo=UTC)
    second_time = datetime(2024, 6, 2, 15, 5, tzinfo=UTC)
    other_time = datetime(2024, 7, 4, 8, 0, tzinfo=UTC)

    await client.post(
        "/sightings",
        json={
            "zoo_id": str(data["zoo"].id),
            "animal_id": str(data["animal"].id),
            "sighting_datetime": first_time.isoformat(),
            "notes": "Early lion encounter",
        },
        headers=headers,
    )
    await client.post(
        "/sightings",
        json={
            "zoo_id": str(data["zoo"].id),
            "animal_id": str(data["tiger"].id),
            "sighting_datetime": second_time.isoformat(),
            "notes": "Afternoon tiger sighting",
        },
        headers=headers,
    )
    await client.post(
        "/sightings",
        json={
            "zoo_id": str(data["zoo"].id),
            "animal_id": str(data["animal"].id),
            "sighting_datetime": other_time.isoformat(),
            "notes": "Different user note",
        },
        headers={"Authorization": f"Bearer {other_token}"},
    )
    await client.post(
        "/sightings",
        json={
            "zoo_id": str(data["far_zoo"].id),
            "animal_id": str(data["animal"].id),
            "sighting_datetime": other_time.isoformat(),
            "notes": "Another zoo",
        },
        headers=headers,
    )

    resp = await client.get(
        f"/zoos/{data['zoo'].slug}/sightings",
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
    assert all("user_id" not in item for item in items)
    assert items[0]["animal_id"] == str(data["tiger"].id)
    assert items[0]["notes"] == "Afternoon tiger sighting"
    assert items[0]["zoo_id"] == str(data["zoo"].id)
    assert items[0]["sighting_datetime"].startswith("2024-06-02")
    assert items[1]["animal_id"] == str(data["animal"].id)
    assert items[1]["notes"] == "Early lion encounter"
    assert items[1]["sighting_datetime"].startswith("2024-05-01")


async def test_zoo_sightings_pagination_and_filtering(client, data):
    token, _user_id = await register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    times = [
        datetime(2024, 6, 10, 12, 0, tzinfo=UTC),
        datetime(2024, 6, 9, 14, 30, tzinfo=UTC),
        datetime(2024, 6, 8, 16, 45, tzinfo=UTC),
    ]

    for index, moment in enumerate(times):
        await client.post(
            "/sightings",
            json={
                "zoo_id": str(data["zoo"].id),
                "animal_id": str(
                    data["animal"].id if index % 2 == 0 else data["tiger"].id
                ),
                "sighting_datetime": moment.isoformat(),
                "notes": f"Note {index}",
            },
            headers=headers,
        )

    await client.post(
        "/sightings",
        json={
            "zoo_id": str(data["far_zoo"].id),
            "animal_id": str(data["animal"].id),
            "sighting_datetime": datetime(2024, 6, 11, 10, 0, tzinfo=UTC).isoformat(),
            "notes": "Other zoo",
        },
        headers=headers,
    )

    resp = await client.get(
        f"/zoos/{data['zoo'].slug}/sightings",
        headers=headers,
        params={"limit": 1, "offset": 1},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 3
    assert body["limit"] == 1
    assert body["offset"] == 1
    assert len(body["items"]) == 1
    second = body["items"][0]
    assert second["sighting_datetime"].startswith("2024-06-09")
    assert second["zoo_id"] == str(data["zoo"].id)
    assert second["notes"] == "Note 1"
    assert resp.headers["X-Total-Count"] == "3"


async def test_search_zoos_is_paginated_and_sorted_by_distance(client, data):
    """The search endpoint returns paginated results ordered by distance."""

    params = {
        "latitude": data["zoo"].latitude,
        "longitude": data["zoo"].longitude,
        "limit": 1,
        "offset": 0,
    }
    resp = await client.get("/zoos", params=params)
    assert resp.status_code == 200
    first_items, meta = _extract_items(resp.json())
    assert meta["offset"] == 0
    assert meta["limit"] == 1
    assert meta["total"] >= 2
    assert len(first_items) == 1
    first = first_items[0]
    assert first["slug"] == data["zoo"].slug
    assert "latitude" not in first
    assert "longitude" not in first
    assert first["distance_km"] == 0
    assert first["is_favorite"] is False

    params["offset"] = 1
    resp = await client.get("/zoos", params=params)
    assert resp.status_code == 200
    second_items, meta = _extract_items(resp.json())
    assert meta["offset"] == 1
    assert len(second_items) == 1
    assert second_items[0]["slug"] == data["far_zoo"].slug
    assert second_items[0]["is_favorite"] is False


async def test_search_zoos_without_coordinates_returns_by_name(client, data):
    """Name filters work without providing location information."""

    resp = await client.get("/zoos", params={"q": "Central"})
    assert resp.status_code == 200
    items, _ = _extract_items(resp.json())
    names = [z["name"] for z in items]
    assert "Central Zoo" in names

async def test_search_zoos_by_city(client, data):
    resp = await client.get("/zoos", params={"q": data["zoo"].city})
    assert resp.status_code == 200
    items, _ = _extract_items(resp.json())
    names = [z["name"] for z in items]
    assert "Central Zoo" in names


async def test_search_zoos_accepts_combined_terms(client, data):
    """Search queries should match across zoo name and city flexibly."""

    with SessionLocal() as db:
        duisburg = models.Zoo(
            name="Tierpark Duisburg",
            slug="tierpark-duisburg",
            address="M\u00fclheimer Str. 273",
            latitude=51.438,
            longitude=6.775,
            description_en="Zoo in Duisburg",
            description_de="Zoo in Duisburg",
            city="Duisburg",
            continent_id=data["zoo"].continent_id,
            country_id=data["zoo"].country_id,
        )
        mulheim = models.Zoo(
            name="Zoo M\u00fclheim",
            slug="zoo-muelheim",
            address="M\u00fclheim Street",
            latitude=51.43,
            longitude=6.85,
            description_en="City zoo",
            description_de="Stadtzoo",
            city="M\u00fclheim an der Ruhr",
            continent_id=data["zoo"].continent_id,
            country_id=data["zoo"].country_id,
        )
        db.add_all([duisburg, mulheim])
        db.commit()
        db.refresh(duisburg)
        db.refresh(mulheim)

    try:
        resp = await client.get("/zoos", params={"q": "Zoo Duisburg"})
        assert resp.status_code == 200
        items, _ = _extract_items(resp.json())
        assert any(z["slug"] == "tierpark-duisburg" for z in items)

        resp = await client.get("/zoos", params={"q": "Duisburger Zoo"})
        assert resp.status_code == 200
        items, _ = _extract_items(resp.json())
        assert any(z["slug"] == "tierpark-duisburg" for z in items)

        resp = await client.get("/zoos", params={"q": "Mulheim"})
        assert resp.status_code == 200
        items, _ = _extract_items(resp.json())
        assert any(z["slug"] == "zoo-muelheim" for z in items)

        resp = await client.get("/zoos", params={"q": "Mulheimer Zoo"})
        assert resp.status_code == 200
        items, _ = _extract_items(resp.json())
        assert any(z["slug"] == "zoo-muelheim" for z in items)

    finally:
        with SessionLocal() as db:
            db.query(models.Zoo).filter(
                models.Zoo.slug.in_(["tierpark-duisburg", "zoo-muelheim"])
            ).delete(synchronize_session=False)
            db.commit()


async def test_list_continents_and_countries(client):
    resp = await client.get("/zoos/continents")
    assert resp.status_code == 200
    continents = resp.json()
    assert any(c["name_en"] == "Europe" for c in continents)
    europe_id = next(c["id"] for c in continents if c["name_en"] == "Europe")

    resp = await client.get(f"/zoos/countries?continent_id={europe_id}")
    assert resp.status_code == 200
    countries = resp.json()
    assert any(c["name_en"] == "Germany" for c in countries)


async def test_search_zoos_by_country(client, data):
    resp = await client.get("/zoos", params={"country_id": 1, "limit": 10})
    assert resp.status_code == 200
    items, _ = _extract_items(resp.json())
    names = [z["name"] for z in items]
    assert "Central Zoo" in names
    assert "Far Zoo" not in names


async def test_map_endpoint_returns_coordinates(client, data):
    resp = await client.get("/zoos/map")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    ids = {z["id"] for z in body}
    assert str(data["zoo"].id) in ids
    assert str(data["far_zoo"].id) in ids
    assert any(z.get("latitude") is not None for z in body)


async def test_user_zoo_endpoints_require_auth(client, data):
    token, user_id = await register_and_login()
    assert token  # token returned but not used to ensure user exists

    resp = await client.get(f"/users/{user_id}/zoos/visited")
    assert resp.status_code == 401

    resp = await client.get(f"/users/{user_id}/zoos/visited/map")
    assert resp.status_code == 401


async def test_user_visited_zoo_endpoints_return_filtered_results(client, data):
    token, user_id = await register_and_login()
    db = SessionLocal()
    visit = models.ZooVisit(user_id=user_id, zoo_id=data["zoo"].id, visit_date=date.today())
    db.add(visit)
    db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "limit": 1,
        "offset": 0,
        "latitude": data["zoo"].latitude,
        "longitude": data["zoo"].longitude,
    }
    resp = await client.get(f"/users/{user_id}/zoos/visited", params=params, headers=headers)
    assert resp.status_code == 200
    items, meta = _extract_items(resp.json())
    assert meta["total"] == 1
    assert items[0]["id"] == str(data["zoo"].id)
    assert resp.headers.get("Cache-Control") == "private, no-store, max-age=0"
    assert "Authorization" in (resp.headers.get("Vary") or "")

    map_resp = await client.get(f"/users/{user_id}/zoos/visited/map", headers=headers)
    assert map_resp.status_code == 200
    map_ids = {z["id"] for z in map_resp.json()}
    assert str(data["zoo"].id) in map_ids
    assert map_resp.headers.get("Cache-Control") == "private, no-store, max-age=0"
    assert "Authorization" in (map_resp.headers.get("Vary") or "")


async def test_user_visited_zoos_include_favorite_flag(client, data):
    token, user_id = await register_and_login()
    db = SessionLocal()
    visit = models.ZooVisit(user_id=user_id, zoo_id=data["zoo"].id, visit_date=date.today())
    db.add(visit)
    db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {token}"}
    fav_resp = await client.put(f"/zoos/{data['zoo'].slug}/favorite", headers=headers)
    assert fav_resp.status_code == 200

    resp = await client.get(f"/users/{user_id}/zoos/visited", headers=headers)
    assert resp.status_code == 200
    items, _ = _extract_items(resp.json())
    target = next(item for item in items if item["id"] == str(data["zoo"].id))
    assert target["is_favorite"] is True


async def test_user_not_visited_endpoints_exclude_visited_zoos(client, data):
    token, user_id = await register_and_login()
    db = SessionLocal()
    visit = models.ZooVisit(user_id=user_id, zoo_id=data["zoo"].id, visit_date=date.today())
    db.add(visit)
    db.commit()
    db.close()

    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.get(
        f"/users/{user_id}/zoos/not-visited",
        params={"limit": 10, "offset": 0, "q": "Zoo"},
        headers=headers,
    )
    assert resp.status_code == 200
    items, meta = _extract_items(resp.json())
    assert meta["total"] >= 1
    ids = {item["id"] for item in items}
    assert str(data["far_zoo"].id) in ids
    assert str(data["zoo"].id) not in ids
    assert resp.headers.get("Cache-Control") == "private, no-store, max-age=0"
    assert "Authorization" in (resp.headers.get("Vary") or "")

    map_resp = await client.get(f"/users/{user_id}/zoos/not-visited/map", headers=headers)
    assert map_resp.status_code == 200
    map_ids = {z["id"] for z in map_resp.json()}
    assert str(data["far_zoo"].id) in map_ids
    assert str(data["zoo"].id) not in map_ids
    assert map_resp.headers.get("Cache-Control") == "private, no-store, max-age=0"
    assert "Authorization" in (map_resp.headers.get("Vary") or "")


async def test_zoo_favorites_flow(client, data):
    token, _ = await register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.put(f"/zoos/{data['zoo'].slug}/favorite", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"favorite": True}

    fav_resp = await client.get("/zoos", params={"favorites_only": "true"}, headers=headers)
    assert fav_resp.status_code == 200
    items, meta = _extract_items(fav_resp.json())
    assert meta["total"] == 1
    assert len(items) == 1
    assert items[0]["id"] == str(data["zoo"].id)
    assert items[0]["is_favorite"] is True

    general_resp = await client.get("/zoos", headers=headers)
    assert general_resp.status_code == 200
    general_items, _ = _extract_items(general_resp.json())
    target = next(item for item in general_items if item["id"] == str(data["zoo"].id))
    assert target["is_favorite"] is True

    detail_resp = await client.get(f"/zoos/{data['zoo'].slug}", headers=headers)
    assert detail_resp.status_code == 200
    assert detail_resp.json()["is_favorite"] is True

    resp = await client.delete(f"/zoos/{data['zoo'].slug}/favorite", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == {"favorite": False}

    cleared = await client.get("/zoos", params={"favorites_only": "true"}, headers=headers)
    assert cleared.status_code == 200
    items, meta = _extract_items(cleared.json())
    assert meta["total"] == 0
    assert items == []

    detail_after = await client.get(f"/zoos/{data['zoo'].slug}", headers=headers)
    assert detail_after.status_code == 200
    assert detail_after.json()["is_favorite"] is False


async def test_zoo_favorites_filter_requires_auth(client):
    resp = await client.get("/zoos", params={"favorites_only": "true"})
    assert resp.status_code == 401


async def test_zoos_personalized_responses_disable_caching(client, data):
    token, _ = await register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/zoos", headers=headers)
    assert resp.status_code == 200
    assert resp.headers["cache-control"] == "private, no-store, max-age=0"
    assert "Authorization" in resp.headers["vary"]

    detail = await client.get(f"/zoos/{data['zoo'].slug}", headers=headers)
    assert detail.status_code == 200
    assert detail.headers["cache-control"] == "private, no-store, max-age=0"
    assert "Authorization" in detail.headers["vary"]

