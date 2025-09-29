"""Import helpers for image metadata and variants."""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Dict

from sqlalchemy import Table, bindparam, select
from sqlalchemy.orm import Session

from app import models
from app.import_utils import _clean_text, _parse_datetime

logger = logging.getLogger(__name__)

BANNED_MIDS = {"M31984332", "M1723980", "M117776631", "M55041643"}


def import_images(
    src: Session,
    dst: Session,
    image_table: Table,
    variant_table: Table,
    animal_map: Dict[str, uuid.UUID],
    *,
    overwrite: bool = False,
) -> None:
    """Insert images and thumbnail variants."""

    img_rows = list(src.execute(select(image_table)).mappings())
    images: list[models.Image] = []
    mid_to_animal: Dict[str, uuid.UUID] = {}
    existing = {img.mid: img for img in dst.execute(select(models.Image)).scalars()}
    for row in img_rows:
        mid = row.get("mid")
        if mid in BANNED_MIDS:
            continue
        animal_id = animal_map.get(row.get("animal_art"))
        if not animal_id:
            continue

        width = row.get("width")
        height = row.get("height")
        size_bytes = row.get("size_bytes")
        mime = row.get("mime")
        sha1 = row.get("sha1")
        original_url = row.get("original_url")
        source = row.get("source")
        if (
            width is None
            or width <= 0
            or height is None
            or height <= 0
            or size_bytes is None
            or size_bytes < 0
            or not mime
            or not mime.startswith("image/")
            or not sha1
            or not re.fullmatch(r"[0-9a-f]{40}", sha1)
            or not original_url
            or source not in {"WIKIDATA_P18", "WIKI_LEAD_DE", "WIKI_LEAD_EN"}
        ):
            logger.warning("Skipping image %s due to invalid metadata", mid)
            continue

        uploaded_at = _parse_datetime(row.get("uploaded_at"))
        retrieved_at = _parse_datetime(row.get("retrieved_at")) or datetime.now(timezone.utc)
        attr_req = row.get("attribution_required")
        attr_bool = None
        if attr_req is not None:
            try:
                attr_bool = bool(int(attr_req))
            except (TypeError, ValueError):
                attr_bool = None

        data = {
            "mid": mid,
            "animal_id": animal_id,
            "commons_title": row.get("commons_title"),
            "commons_page_url": row.get("commons_page_url"),
            "original_url": original_url,
            "width": width,
            "height": height,
            "size_bytes": size_bytes,
            "sha1": sha1,
            "mime": mime,
            "uploaded_at": uploaded_at,
            "uploader": _clean_text(row.get("uploader")),
            "title": _clean_text(row.get("title")),
            "artist_raw": _clean_text(row.get("artist_raw")),
            "artist_plain": _clean_text(row.get("artist_plain")),
            "license": _clean_text(row.get("license")),
            "license_short": _clean_text(row.get("license_short")),
            "license_url": _clean_text(row.get("license_url")),
            "attribution_required": attr_bool,
            "usage_terms": _clean_text(row.get("usage_terms")),
            "credit_line": _clean_text(row.get("credit_line")),
            "source": source,
            "retrieved_at": retrieved_at,
        }

        if mid in existing:
            mid_to_animal[mid] = animal_id or existing[mid].animal_id
            if overwrite:
                for key, value in data.items():
                    setattr(existing[mid], key, value)
                dst.add(existing[mid])
            continue

        images.append(models.Image(**data))
        mid_to_animal[mid] = animal_id
    if images:
        dst.bulk_save_objects(images)

    var_rows = list(src.execute(select(variant_table)).mappings())
    variants: list[models.ImageVariant] = []
    best_variant: Dict[uuid.UUID, tuple[int, str]] = {}
    existing_vars = set(
        dst.execute(select(models.ImageVariant.mid, models.ImageVariant.width)).all()
    )
    for row in var_rows:
        mid = row.get("mid")
        if mid in BANNED_MIDS or mid not in mid_to_animal:
            continue
        key = (mid, row.get("width"))
        if key in existing_vars:
            continue
        variants.append(
            models.ImageVariant(
                mid=mid,
                width=row.get("width"),
                height=row.get("height"),
                thumb_url=row.get("thumb_url"),
            )
        )
        animal_id = mid_to_animal.get(mid)
        if animal_id:
            width = row.get("width")
            url = row.get("thumb_url")
            current = best_variant.get(animal_id)
            if current is None or (
                current[0] != 640 and (width == 640 or width > current[0])
            ):
                best_variant[animal_id] = (width, url)
    if variants:
        dst.bulk_save_objects(variants)

    if best_variant:
        dst.execute(
            models.Animal.__table__
            .update()
            .where(
                models.Animal.id == bindparam("aid"),
                models.Animal.default_image_url.is_(None),
            ),
            [
                {"aid": animal_id, "default_image_url": url}
                for animal_id, (_, url) in best_variant.items()
            ],
        )
