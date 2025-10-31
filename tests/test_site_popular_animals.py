


async def test_popular_animals_limit_and_shape(client, data):
    resp = await client.get("/site/popular-animals?limit=5")
    assert resp.status_code == 200
    arr = resp.json()
    assert len(arr) <= 5
    for item in arr:
        assert {"id", "slug", "name_en"}.issubset(item.keys())


async def test_popular_animals_limit_validation(client):
    assert await client.get("/site/popular-animals?limit=0").status_code == 422
    assert await client.get("/site/popular-animals?limit=50").status_code == 422
