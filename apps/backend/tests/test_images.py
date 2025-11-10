


async def test_get_image_metadata(client, data):
    resp = await client.get("/images", params={"mid": "M1"})
    assert resp.status_code == 200
    assert resp.headers["cache-control"].startswith("public, max-age=")
    body = resp.json()
    assert body["mid"] == "M1"
    assert body["author"] == "Jane Smith"
    assert body["license"] == "CC BY-SA 4.0"
    assert body["license_url"].startswith("http://creativecommons.org/")
    assert body["commons_page_url"].startswith("http://commons.org/")
    assert body["credit_line"] == "Photo by Jane"
    assert body["attribution_required"] is True
    assert body["variants"][0]["width"] == 320
