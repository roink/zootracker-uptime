"""Public endpoints that power the marketing landing page."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import logging
import xml.etree.ElementTree as ET
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from .. import models, schemas
from ..database import get_db
from ..config import SITE_DEFAULT_LANGUAGE, SITE_LANGUAGES
from ..utils.urls import build_absolute_url

router = APIRouter()

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
XHTML_NS = "http://www.w3.org/1999/xhtml"
_RETRY_AFTER_SECONDS = "600"

ET.register_namespace("", SITEMAP_NS)
ET.register_namespace("xhtml", XHTML_NS)

logger = logging.getLogger(__name__)


@router.get("/site/summary", response_model=schemas.SiteSummary)
def get_site_summary(
    response: Response, db: Session = Depends(get_db)
) -> schemas.SiteSummary:
    """Return aggregate counts for species, zoos, countries and sightings."""

    species_count = db.query(func.count(models.Animal.id)).scalar() or 0
    zoo_count = db.query(func.count(models.Zoo.id)).scalar() or 0
    country_count = (
        db.query(func.count(func.distinct(models.Zoo.country_id)))
        .filter(models.Zoo.country_id.isnot(None))
        .scalar()
        or 0
    )
    sighting_count = db.query(func.count(models.AnimalSighting.id)).scalar() or 0

    response.headers[
        "Cache-Control"
    ] = "public, max-age=300, stale-while-revalidate=600"

    return schemas.SiteSummary(
        species=species_count,
        zoos=zoo_count,
        countries=country_count,
        sightings=sighting_count,
    )


@router.get("/site/popular-animals", response_model=list[schemas.PopularAnimal])
def get_popular_animals(
    limit: int = Query(8, ge=1, le=20), db: Session = Depends(get_db)
) -> list[schemas.PopularAnimal]:
    """Return the most represented animals based on zoo coverage."""

    animals = (
        db.query(models.Animal)
        .order_by(models.Animal.zoo_count.desc(), models.Animal.name_en)
        .limit(limit)
        .all()
    )

    return [
        schemas.PopularAnimal(
            id=a.id,
            slug=a.slug,
            name_en=a.name_en,
            name_de=a.name_de,
            scientific_name=a.scientific_name,
            zoo_count=a.zoo_count,
            iucn_conservation_status=a.conservation_state,
            default_image_url=a.default_image_url,
        )
        for a in animals
    ]


def _format_lastmod(value: datetime | None) -> str | None:
    """Render timestamps in the ISO 8601 format required by sitemaps."""

    if value is None:
        return None
    if value.tzinfo is None:
        aware = value.replace(tzinfo=timezone.utc)
    else:
        aware = value.astimezone(timezone.utc)
    trimmed = aware.replace(microsecond=0)
    return trimmed.isoformat().replace("+00:00", "Z")


def _etag_for_bytes(data: bytes) -> str:
    """Compute a strong ETag for cached sitemap payloads."""

    return '"' + hashlib.sha256(data).hexdigest() + '"'


def _indent_xml(element: ET.Element) -> None:
    """Add indentation and line breaks to XML output for readability."""

    if hasattr(ET, "indent"):
        # Python 3.9+ offers xml.etree.ElementTree.indent for pretty printing.
        ET.indent(element, space="  ")  # type: ignore[attr-defined]
        return

    def _indent_fallback(node: ET.Element, level: int = 0) -> None:
        indent = "\n" + ("  " * level)
        children = list(node)
        if children:
            if not node.text or not node.text.strip():
                node.text = indent + "  "
            for child in children:
                _indent_fallback(child, level + 1)
            if not children[-1].tail or not children[-1].tail.strip():
                children[-1].tail = indent
        elif level and (not node.tail or not node.tail.strip()):
            node.tail = indent

    _indent_fallback(element)


def _xml_response(element: ET.Element, request: Request, *, max_age: int) -> Response:
    """Serialize an XML element tree, attach cache headers, and honor ETags."""

    cache_control = f"public, max-age={max_age}, stale-while-revalidate={max_age * 2}"
    _indent_xml(element)
    xml_bytes = ET.tostring(element, encoding="utf-8", xml_declaration=True)
    etag = _etag_for_bytes(xml_bytes)

    common_headers = {
        "ETag": etag,
        "Cache-Control": cache_control,
        "Vary": "Accept-Encoding",
    }

    inm = request.headers.get("if-none-match")
    if inm:
        presented = [value.strip() for value in inm.split(",")]
        if etag in presented:
            return Response(status_code=304, headers=common_headers)

    response = Response(
        content=xml_bytes,
        media_type="application/xml",
        headers=common_headers,
    )
    response.headers["content-type"] = "application/xml; charset=utf-8"
    return response


def _sitemap_service_unavailable() -> Response:
    """Return a 503 response with XML content-type for crawlers."""

    response = Response(
        content=b"",
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        media_type="application/xml",
        headers={
            "Retry-After": _RETRY_AFTER_SECONDS,
            "Cache-Control": "no-store",
            "Vary": "Accept-Encoding",
        },
    )
    response.headers["content-type"] = "application/xml; charset=utf-8"
    return response


def _head_response(response: Response) -> Response:
    """Trim the body for HEAD requests while preserving headers and status."""

    if response.status_code == status.HTTP_304_NOT_MODIFIED:
        return response

    if response.body == b"":
        return response

    response.body = b""
    response.headers["content-length"] = "0"
    return response


def _build_entity_href(kind: str, slug: str, *, lang: str | None) -> str:
    slug_segment = quote(slug, safe="")
    if lang:
        lang_segment = quote(lang, safe="-")
        path = f"/{lang_segment}/{kind}/{slug_segment}"
    else:
        path = f"/{kind}/{slug_segment}"
    return build_absolute_url(path)


def _append_alternate_links(
    url_el: ET.Element, kind: str, slug: str, canonical_href: str
) -> None:
    if not SITE_LANGUAGES:
        return

    for lang in SITE_LANGUAGES:
        href = _build_entity_href(kind, slug, lang=lang)
        link_el = ET.SubElement(url_el, f"{{{XHTML_NS}}}link")
        link_el.set("rel", "alternate")
        link_el.set("hreflang", lang)
        link_el.set("href", href)

    default_link = ET.SubElement(url_el, f"{{{XHTML_NS}}}link")
    default_link.set("rel", "alternate")
    default_link.set("hreflang", "x-default")
    default_link.set("href", canonical_href)


@router.get("/sitemap.xml", include_in_schema=False)
def get_sitemap_index(request: Request, db: Session = Depends(get_db)) -> Response:
    """Expose the sitemap index pointing to sub-sitemaps for animals and zoos."""
    try:
        animals_lastmod = db.query(func.max(models.Animal.updated_at)).scalar()
        zoos_lastmod = db.query(func.max(models.Zoo.updated_at)).scalar()
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to build sitemap index due to database error")
        return _sitemap_service_unavailable()

    root = ET.Element(f"{{{SITEMAP_NS}}}sitemapindex")

    def _add_entry(path: str, lastmod: datetime | None) -> None:
        sitemap_el = ET.SubElement(root, f"{{{SITEMAP_NS}}}sitemap")
        loc_el = ET.SubElement(sitemap_el, f"{{{SITEMAP_NS}}}loc")
        loc_el.text = build_absolute_url(path)
        lastmod_str = _format_lastmod(lastmod)
        if lastmod_str:
            lastmod_el = ET.SubElement(sitemap_el, f"{{{SITEMAP_NS}}}lastmod")
            lastmod_el.text = lastmod_str

    _add_entry("/sitemaps/animals.xml", animals_lastmod)
    _add_entry("/sitemaps/zoos.xml", zoos_lastmod)

    return _xml_response(root, request, max_age=900)


@router.head("/sitemap.xml", include_in_schema=False)
def head_sitemap_index(request: Request, db: Session = Depends(get_db)) -> Response:
    """Serve HEAD responses for the sitemap index."""

    response = get_sitemap_index(request, db)
    return _head_response(response)


@router.get("/sitemaps/animals.xml", include_in_schema=False)
def get_animals_sitemap(request: Request, db: Session = Depends(get_db)) -> Response:
    """Return the sitemap entries for all public animal pages."""
    try:
        animals = (
            db.query(models.Animal.slug, models.Animal.updated_at)
            .order_by(models.Animal.updated_at.desc(), models.Animal.slug)
            .all()
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to build animals sitemap due to database error")
        return _sitemap_service_unavailable()

    root = ET.Element(f"{{{SITEMAP_NS}}}urlset")

    for slug, updated_at in animals:
        url_el = ET.SubElement(root, f"{{{SITEMAP_NS}}}url")
        loc_el = ET.SubElement(url_el, f"{{{SITEMAP_NS}}}loc")
        canonical_href = _build_entity_href(
            "animals", slug, lang=SITE_DEFAULT_LANGUAGE
        )
        loc_el.text = canonical_href
        _append_alternate_links(url_el, "animals", slug, canonical_href)
        lastmod_str = _format_lastmod(updated_at)
        if lastmod_str:
            lastmod_el = ET.SubElement(url_el, f"{{{SITEMAP_NS}}}lastmod")
            lastmod_el.text = lastmod_str

    return _xml_response(root, request, max_age=900)


@router.head("/sitemaps/animals.xml", include_in_schema=False)
def head_animals_sitemap(request: Request, db: Session = Depends(get_db)) -> Response:
    """Serve HEAD responses for the animals sitemap."""

    response = get_animals_sitemap(request, db)
    return _head_response(response)


@router.get("/sitemaps/zoos.xml", include_in_schema=False)
def get_zoos_sitemap(request: Request, db: Session = Depends(get_db)) -> Response:
    """Return the sitemap entries for all public zoo pages."""
    try:
        zoos = (
            db.query(models.Zoo.slug, models.Zoo.updated_at)
            .order_by(models.Zoo.updated_at.desc(), models.Zoo.slug)
            .all()
        )
    except SQLAlchemyError:
        db.rollback()
        logger.exception("Failed to build zoos sitemap due to database error")
        return _sitemap_service_unavailable()

    root = ET.Element(f"{{{SITEMAP_NS}}}urlset")

    for slug, updated_at in zoos:
        url_el = ET.SubElement(root, f"{{{SITEMAP_NS}}}url")
        loc_el = ET.SubElement(url_el, f"{{{SITEMAP_NS}}}loc")
        canonical_href = _build_entity_href(
            "zoos", slug, lang=SITE_DEFAULT_LANGUAGE
        )
        loc_el.text = canonical_href
        _append_alternate_links(url_el, "zoos", slug, canonical_href)
        lastmod_str = _format_lastmod(updated_at)
        if lastmod_str:
            lastmod_el = ET.SubElement(url_el, f"{{{SITEMAP_NS}}}lastmod")
            lastmod_el.text = lastmod_str

    return _xml_response(root, request, max_age=900)


@router.head("/sitemaps/zoos.xml", include_in_schema=False)
def head_zoos_sitemap(request: Request, db: Session = Depends(get_db)) -> Response:
    """Serve HEAD responses for the zoos sitemap."""

    response = get_zoos_sitemap(request, db)
    return _head_response(response)


@router.get(
    "/robots.txt",
    include_in_schema=False,
    response_class=PlainTextResponse,
)
def get_robots(request: Request) -> Response:
    """Expose a robots.txt file that advertises the sitemap index."""

    cache_control = "public, max-age=86400, stale-while-revalidate=172800"
    sitemap_url = build_absolute_url("/sitemap.xml")
    body = f"User-agent: *\nAllow: /\n\nSitemap: {sitemap_url}\n"
    etag = _etag_for_bytes(body.encode("utf-8"))

    common_headers = {
        "ETag": etag,
        "Cache-Control": cache_control,
        "Vary": "Accept-Encoding",
    }

    inm = request.headers.get("if-none-match")
    if inm:
        presented = [value.strip() for value in inm.split(",")]
        if etag in presented:
            return Response(status_code=304, headers=common_headers)

    return PlainTextResponse(content=body, headers=common_headers)


@router.head(
    "/robots.txt",
    include_in_schema=False,
    response_class=PlainTextResponse,
)
def head_robots(request: Request) -> Response:
    """Serve HEAD responses for robots.txt."""

    response = get_robots(request)
    return _head_response(response)
