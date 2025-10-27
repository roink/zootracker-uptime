import xml.etree.ElementTree as ET
from datetime import timezone
from urllib.parse import quote

from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

from app import models
from app.config import SITE_BASE_URL, SITE_DEFAULT_LANGUAGE, SITE_LANGUAGES
from app.database import SessionLocal
from app.main import app, get_db

from .conftest import client, override_get_db

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


def _format_lastmod(value):
    if value is None:
        raise AssertionError("Expected timestamp, got None")
    if value.tzinfo is None:
        aware = value.replace(tzinfo=timezone.utc)
    else:
        aware = value.astimezone(timezone.utc)
    trimmed = aware.replace(microsecond=0)
    return trimmed.isoformat().replace("+00:00", "Z")


def _animal_lastmod(slug: str) -> str:
    with SessionLocal() as db:
        value = (
            db.query(models.Animal.updated_at)
            .filter(models.Animal.slug == slug)
            .scalar()
        )
    return _format_lastmod(value)


def _zoo_lastmod(slug: str) -> str:
    with SessionLocal() as db:
        value = (
            db.query(models.Zoo.updated_at)
            .filter(models.Zoo.slug == slug)
            .scalar()
        )
    return _format_lastmod(value)


class BrokenSession:
    def __init__(self) -> None:
        self.rolled_back = False

    def query(self, *args, **kwargs):  # noqa: D401 - matches Session interface
        raise SQLAlchemyError("boom")

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        pass


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

    sitemap_entries = {
        entry.find("sm:loc", NS).text: entry for entry in root.findall("sm:sitemap", NS)
    }

    animals_entry = sitemap_entries[f"{SITE_BASE_URL.rstrip('/')}/sitemaps/animals.xml"]
    zoos_entry = sitemap_entries[f"{SITE_BASE_URL.rstrip('/')}/sitemaps/zoos.xml"]

    animals_lastmod = animals_entry.find("sm:lastmod", NS)
    zoos_lastmod = zoos_entry.find("sm:lastmod", NS)

    with SessionLocal() as db:
        expected_animals = _format_lastmod(
            db.query(func.max(models.Animal.updated_at)).scalar()
        )
        expected_zoos = _format_lastmod(
            db.query(func.max(models.Zoo.updated_at)).scalar()
        )

    assert animals_lastmod is not None
    assert animals_lastmod.text == expected_animals
    assert zoos_lastmod is not None
    assert zoos_lastmod.text == expected_zoos


def test_sitemap_index_head_matches_get(data):
    base = client.get("/sitemap.xml")
    assert base.status_code == 200

    head = client.head("/sitemap.xml")
    assert head.status_code == 200
    assert head.content == b""
    assert head.headers["ETag"] == base.headers["ETag"]
    assert head.headers["Cache-Control"] == base.headers["Cache-Control"]
    assert head.headers["vary"] == "Accept-Encoding"


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

    lastmod_el = lion_entry.find("sm:lastmod", NS)
    assert lastmod_el is not None
    assert lastmod_el.text == _animal_lastmod("lion")


def test_animals_sitemap_head_matches_get(data):
    base = client.get("/sitemaps/animals.xml")
    assert base.status_code == 200

    head = client.head("/sitemaps/animals.xml")
    assert head.status_code == 200
    assert head.content == b""
    assert head.headers["ETag"] == base.headers["ETag"]
    assert head.headers["Cache-Control"] == base.headers["Cache-Control"]
    assert head.headers["vary"] == "Accept-Encoding"


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

    lastmod_el = central_entry.find("sm:lastmod", NS)
    assert lastmod_el is not None
    assert lastmod_el.text == _zoo_lastmod("central-zoo")


def test_zoos_sitemap_head_matches_get(data):
    base = client.get("/sitemaps/zoos.xml")
    assert base.status_code == 200

    head = client.head("/sitemaps/zoos.xml")
    assert head.status_code == 200
    assert head.content == b""
    assert head.headers["ETag"] == base.headers["ETag"]
    assert head.headers["Cache-Control"] == base.headers["Cache-Control"]
    assert head.headers["vary"] == "Accept-Encoding"


def test_robots_txt_references_sitemap(data):
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert resp.headers["vary"] == "Accept-Encoding"
    assert f"Sitemap: {SITE_BASE_URL.rstrip('/')}/sitemap.xml" in resp.text


def test_robots_txt_head_matches_get(data):
    base = client.get("/robots.txt")
    assert base.status_code == 200

    head = client.head("/robots.txt")
    assert head.status_code == 200
    assert head.content == b""
    assert head.headers["ETag"] == base.headers["ETag"]
    assert head.headers["Cache-Control"] == base.headers["Cache-Control"]
    assert head.headers["vary"] == "Accept-Encoding"


def test_sitemap_index_etag_304(data):
    first = client.get("/sitemap.xml")
    assert first.status_code == 200
    etag = first.headers.get("ETag")
    assert etag

    cached = client.get("/sitemap.xml", headers={"If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.headers.get("ETag") == etag
    assert "Cache-Control" in cached.headers


def test_sitemap_index_head_etag_304(data):
    etag = client.get("/sitemap.xml").headers["ETag"]

    cached = client.head("/sitemap.xml", headers={"If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.content == b""


def test_robots_txt_etag_304(data):
    first = client.get("/robots.txt")
    assert first.status_code == 200
    etag = first.headers.get("ETag")
    assert etag

    cached = client.get("/robots.txt", headers={"If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.headers.get("ETag") == etag
    assert "Cache-Control" in cached.headers


def test_animals_sitemap_etag_304(data):
    first = client.get("/sitemaps/animals.xml")
    assert first.status_code == 200
    etag = first.headers.get("ETag")
    assert etag

    cached = client.get("/sitemaps/animals.xml", headers={"If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.headers.get("ETag") == etag
    assert cached.headers.get("Vary") == "Accept-Encoding"


def test_zoos_sitemap_etag_304(data):
    first = client.get("/sitemaps/zoos.xml")
    assert first.status_code == 200
    etag = first.headers.get("ETag")
    assert etag

    cached = client.get("/sitemaps/zoos.xml", headers={"If-None-Match": etag})
    assert cached.status_code == 304
    assert cached.headers.get("ETag") == etag
    assert cached.headers.get("Vary") == "Accept-Encoding"


def test_animals_sitemap_database_error():
    broken_session = BrokenSession()

    def broken_db():
        try:
            yield broken_session
        finally:
            broken_session.close()

    app.dependency_overrides[get_db] = broken_db
    try:
        resp = client.get("/sitemaps/animals.xml")
    finally:
        app.dependency_overrides[get_db] = override_get_db

    assert resp.status_code == 503
    assert resp.headers["Retry-After"] == "600"
    assert resp.headers["Cache-Control"] == "no-store"
    assert resp.headers["content-type"] == "application/xml; charset=utf-8"
    assert broken_session.rolled_back is True


def test_sitemap_index_database_error():
    broken_session = BrokenSession()

    def broken_db():
        try:
            yield broken_session
        finally:
            broken_session.close()

    app.dependency_overrides[get_db] = broken_db
    try:
        resp = client.get("/sitemap.xml")
    finally:
        app.dependency_overrides[get_db] = override_get_db

    assert resp.status_code == 503
    assert resp.headers["Retry-After"] == "600"
    assert resp.headers["Cache-Control"] == "no-store"
    assert resp.headers["content-type"] == "application/xml; charset=utf-8"
    assert broken_session.rolled_back is True
