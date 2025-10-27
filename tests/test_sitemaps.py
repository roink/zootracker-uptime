import xml.etree.ElementTree as ET

from app.config import SITE_BASE_URL

from .conftest import client


NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def test_sitemap_index_lists_submaps(data):
    resp = client.get("/sitemap.xml")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")

    root = ET.fromstring(resp.content)
    locs = [loc.text for loc in root.findall("sm:sitemap/sm:loc", NS)]

    assert f"{SITE_BASE_URL.rstrip('/')}/sitemaps/animals.xml" in locs
    assert f"{SITE_BASE_URL.rstrip('/')}/sitemaps/zoos.xml" in locs


def test_animals_sitemap_includes_animals(data):
    resp = client.get("/sitemaps/animals.xml")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")

    root = ET.fromstring(resp.content)
    locs = [loc.text for loc in root.findall("sm:url/sm:loc", NS)]

    assert f"{SITE_BASE_URL.rstrip('/')}/animals/lion" in locs
    assert f"{SITE_BASE_URL.rstrip('/')}/animals/tiger" in locs


def test_zoos_sitemap_includes_zoos(data):
    resp = client.get("/sitemaps/zoos.xml")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/xml")

    root = ET.fromstring(resp.content)
    locs = [loc.text for loc in root.findall("sm:url/sm:loc", NS)]

    assert f"{SITE_BASE_URL.rstrip('/')}/zoos/central-zoo" in locs
    assert f"{SITE_BASE_URL.rstrip('/')}/zoos/far-zoo" in locs


def test_robots_txt_references_sitemap(data):
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert f"Sitemap: {SITE_BASE_URL.rstrip('/')}/sitemap.xml" in resp.text


def test_sitemap_index_etag_304(data):
    first = client.get("/sitemap.xml")
    assert first.status_code == 200
    etag = first.headers.get("ETag")
    assert etag

    cached = client.get("/sitemap.xml", headers={"If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.headers.get("ETag") == etag
    assert "Cache-Control" in cached.headers


def test_robots_txt_etag_304(data):
    first = client.get("/robots.txt")
    assert first.status_code == 200
    etag = first.headers.get("ETag")
    assert etag

    cached = client.get("/robots.txt", headers={"If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.headers.get("ETag") == etag
    assert "Cache-Control" in cached.headers
