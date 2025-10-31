


async def test_site_summary_counts(client, data):
    resp = await client.get("/site/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body.keys()) == {"species", "zoos", "countries", "sightings"}
    assert all(isinstance(body[k], int) for k in body)
