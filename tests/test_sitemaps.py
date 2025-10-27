import xml.etree.ElementTree as ET
from urllib.parse import quote

from app.config import SITE_BASE_URL, SITE_DEFAULT_LANGUAGE, SITE_LANGUAGES

from .conftest import client

NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
    "xhtml": "http://www.w3.org/1999/xhtml",
}


def _expected_entity_href(kind: str, slug: str, lang: str | None) -> str:
    slug_segment = quote(slug, safe="")
    base = SITE_BASE_URL.rstrip("/")
    if lang:
        lang_segment = quote(lang, safe="-")
        return f"{base}/{lang_segment}/{kind}/{slug_segment}"
    return f"{base}/{kind}/{slug_segment}"


def _find_url_entry(root: ET.Element, href: str) -> ET.Element:
    for url_el in root.findall("sm:url", NS):
        loc_el = url_el.find("sm:loc", NS)
        if loc_el is not None and loc_el.text == href:
            return url_el
    raise AssertionError(f"Sitemap entry with href={href!r} not found")


def test_sitemap_index_lists_submaps(data):
    resp = client.get("/sitemap.xml")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/xml; charset=utf-8"
    assert "stale-while-revalidate" in resp.headers["cache-control"]
    assert resp.headers["vary"] == "Accept-Encoding"

    root = ET.fromstring(resp.content)
    locs = [loc.text for loc in root.findall("sm:sitemap/sm:loc", NS)]

    assert f"{SITE_BASE_URL.rstrip('/')}/sitemaps/animals.xml" in locs
    assert f"{SITE_BASE_URL.rstrip('/')}/sitemaps/zoos.xml" in locs


def test_animals_sitemap_includes_animals(data):
    resp = client.get("/sitemaps/animals.xml")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/xml; charset=utf-8"
    assert "stale-while-revalidate" in resp.headers["cache-control"]
    assert resp.headers["vary"] == "Accept-Encoding"

    root = ET.fromstring(resp.content)
    locs = [loc.text for loc in root.findall("sm:url/sm:loc", NS)]

    canonical_lang = SITE_DEFAULT_LANGUAGE if SITE_LANGUAGES else None
    assert _expected_entity_href("animals", "lion", canonical_lang) in locs
    assert _expected_entity_href("animals", "tiger", canonical_lang) in locs

    lion_entry = _find_url_entry(
        root, _expected_entity_href("animals", "lion", canonical_lang)
    )
    hreflangs = {
        link.attrib["hreflang"]: link.attrib["href"]
        for link in lion_entry.findall("xhtml:link", NS)
    }
    for lang in SITE_LANGUAGES:
        assert hreflangs[lang] == _expected_entity_href("animals", "lion", lang)
    assert hreflangs["x-default"] == _expected_entity_href(
        "animals", "lion", canonical_lang
    )


def test_zoos_sitemap_includes_zoos(data):
    resp = client.get("/sitemaps/zoos.xml")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/xml; charset=utf-8"
    assert "stale-while-revalidate" in resp.headers["cache-control"]
    assert resp.headers["vary"] == "Accept-Encoding"

    root = ET.fromstring(resp.content)
    locs = [loc.text for loc in root.findall("sm:url/sm:loc", NS)]

    canonical_lang = SITE_DEFAULT_LANGUAGE if SITE_LANGUAGES else None
    assert _expected_entity_href("zoos", "central-zoo", canonical_lang) in locs
    assert _expected_entity_href("zoos", "far-zoo", canonical_lang) in locs

    central_entry = _find_url_entry(
        root, _expected_entity_href("zoos", "central-zoo", canonical_lang)
    )
    hreflangs = {
        link.attrib["hreflang"]: link.attrib["href"]
        for link in central_entry.findall("xhtml:link", NS)
    }
    for lang in SITE_LANGUAGES:
        assert hreflangs[lang] == _expected_entity_href("zoos", "central-zoo", lang)
    assert hreflangs["x-default"] == _expected_entity_href(
        "zoos", "central-zoo", canonical_lang
    )


def test_robots_txt_references_sitemap(data):
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert resp.headers["vary"] == "Accept-Encoding"
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
