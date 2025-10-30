"""Import helpers for zoo metadata."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Dict

from sqlalchemy import Table, select
from sqlalchemy.orm import Session

from app import models
from app.import_utils import _clean_text

logger = logging.getLogger(__name__)


def import_zoos(src: Session, dst: Session, zoo_table: Table) -> Dict[int, uuid.UUID]:
    """Insert zoos and build id mapping."""

    existing_rows = list(
        dst.execute(
            select(
                models.Zoo.id,
                models.Zoo.name,
                models.Zoo.city,
                models.Zoo.country_id,
                models.Zoo.slug,
            )
        ).mappings()
    )
    existing_by_key: Dict[tuple[str, str, int | None], uuid.UUID] = {}
    existing_by_slug: Dict[str, uuid.UUID] = {}
    seen_slugs: set[str] = set()
    for row in existing_rows:
        existing_key = (row["name"], row["city"], row["country_id"])
        existing_by_key[existing_key] = row["id"]
        slug = row.get("slug")
        if slug:
            existing_by_slug[slug] = row["id"]
            seen_slugs.add(slug)

    def ensure_unique_slug(candidate: str) -> str:
        """Ensure ``candidate`` slug is unique by appending a numeric suffix."""

        base = candidate or "zoo"
        slug = base
        suffix = 2
        while slug in seen_slugs:
            slug = f"{base}-{suffix}"
            suffix += 1
        seen_slugs.add(slug)
        return slug

    rows = list(src.execute(select(zoo_table)).mappings())
    zoos = []
    mapping: Dict[int, uuid.UUID] = {}
    for row in rows:
        zoo_key: tuple[str, str, int | None] = (
            row.get("name"),
            row.get("city"),
            row.get("country"),
        )
        slug = row.get("slug")
        if isinstance(slug, str):
            slug = slug.strip() or None
        if not slug:
            base_name = row.get("name") or ""
            city = row.get("city") or ""
            base = f"{base_name}-{city}" if city else base_name
            if not base:
                base = f"zoo-{row.get('zoo_id')}"
            slug = re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")
            if not slug:
                slug = f"zoo-{row.get('zoo_id')}"
        slug = slug[:255]
        desc_en = _clean_text(row.get("description_en"))
        desc_de = _clean_text(row.get("description_de"))
        zoo_id = existing_by_slug.get(slug)
        if zoo_id is not None:
            if desc_en or desc_de:
                zoo_obj = dst.get(models.Zoo, zoo_id)
                changed = False
                if desc_en and zoo_obj.description_en != desc_en:
                    zoo_obj.description_en = desc_en
                    changed = True
                if desc_de and zoo_obj.description_de != desc_de:
                    zoo_obj.description_de = desc_de
                    changed = True
                if changed:
                    dst.add(zoo_obj)
            mapping[row["zoo_id"]] = zoo_id
            seen_slugs.add(slug)
            existing_by_key[zoo_key] = zoo_id
            continue
        if zoo_key in existing_by_key:
            zoo_id = existing_by_key[zoo_key]
            zoo_obj = dst.get(models.Zoo, zoo_id)
            changed = False
            if desc_en or desc_de:
                if desc_en and zoo_obj.description_en != desc_en:
                    zoo_obj.description_en = desc_en
                    changed = True
                if desc_de and zoo_obj.description_de != desc_de:
                    zoo_obj.description_de = desc_de
                    changed = True
            current_slug = zoo_obj.slug
            if current_slug and existing_by_slug.get(current_slug) == zoo_id:
                existing_by_slug.pop(current_slug, None)
            if slug in seen_slugs:
                new_slug = ensure_unique_slug(slug)
            else:
                new_slug = slug
                seen_slugs.add(new_slug)
            if zoo_obj.slug != new_slug:
                zoo_obj.slug = new_slug
                changed = True
            existing_by_slug[new_slug] = zoo_id
            if changed:
                dst.add(zoo_obj)
            mapping[row["zoo_id"]] = zoo_id
            continue
        lat_google = row.get("latitude_google")
        lon_google = row.get("longitude_google")
        if lat_google is not None and lon_google is not None:
            lat = lat_google
            lon = lon_google
        else:
            lat = row.get("latitude")
            lon = row.get("longitude")
        if lat is not None and not (-90 <= lat <= 90):
            logger.warning("Zoo %s has invalid latitude %s", row.get("name"), lat)
            lat = None
        if lon is not None and not (-180 <= lon <= 180):
            logger.warning("Zoo %s has invalid longitude %s", row.get("name"), lon)
            lon = None
        zoo_id = uuid.uuid4()
        if slug in seen_slugs:
            unique_slug = ensure_unique_slug(slug)
        else:
            unique_slug = slug
            seen_slugs.add(unique_slug)
        existing_by_slug[unique_slug] = zoo_id
        zoos.append(
            models.Zoo(
                id=zoo_id,
                name=row.get("name"),
                slug=unique_slug,
                continent_id=row.get("continent"),
                country_id=row.get("country"),
                city=row.get("city"),
                description_en=desc_en,
                description_de=desc_de,
                latitude=lat,
                longitude=lon,
            )
        )
        mapping[row["zoo_id"]] = zoo_id
        existing_by_key[zoo_key] = zoo_id
    if zoos:
        dst.bulk_save_objects(zoos)
    return mapping
