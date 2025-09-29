"""Import utilities for animal records."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Dict

from sqlalchemy import Table, exists, func, select
from sqlalchemy.orm import Session

from app import models
from app.import_utils import _clean_text
from app.utils.iucn import normalize_status

logger = logging.getLogger(__name__)


def import_animals(
    src: Session,
    dst: Session,
    animal_table: Table,
    link_table: Table,
    category_map: Dict[int | None, uuid.UUID],
    *,
    overwrite: bool = False,
) -> Dict[str, uuid.UUID]:
    """Insert animals and build id mapping keyed by ``art``."""

    existing = {
        row.art: row.id
        for row in dst.execute(select(models.Animal.id, models.Animal.art)).mappings()
        if row.art is not None
    }
    rows_stmt = select(animal_table).where(
        exists(
            select(1)
            .select_from(link_table)
            .where(
                link_table.c.art == animal_table.c.art,
                link_table.c.art.isnot(None),
                link_table.c.art != "",
            )
        )
    )
    n_total_animals_in_src = src.execute(
        select(func.count()).select_from(animal_table)
    ).scalar_one()
    n_linked_animals = src.execute(
        rows_stmt.with_only_columns(func.count())
    ).scalar_one()
    rows = src.execute(rows_stmt).mappings()
    animals = []
    id_map: Dict[str, uuid.UUID] = {}
    n_inserted = 0
    n_updated = 0
    n_skipped = 0
    for row in rows:
        art = row.get("art")
        desc_de = _clean_text(row.get("description_de"))
        desc_en = _clean_text(row.get("description_en"))
        status = normalize_status(row.get("iucn_conservation_status"))
        taxon_rank = row.get("taxon_rank")
        if taxon_rank:
            taxon_rank = taxon_rank.strip()
        slug = row.get("slug")
        if isinstance(slug, str):
            slug = slug.strip() or None
        if slug is None and isinstance(art, str):
            fallback = re.sub(r"[^a-z0-9]+", "-", art.lower()).strip("-")
            slug = fallback or None
        if art in existing:
            animal_id = existing[art]
            animal = dst.get(models.Animal, animal_id)
            changed = False

            def assign(attr: str, value: str | None) -> None:
                nonlocal changed
                current = getattr(animal, attr)
                if overwrite:
                    if current != value:
                        setattr(animal, attr, value)
                        changed = True
                else:
                    if current in (None, "") and value:
                        setattr(animal, attr, value)
                        changed = True

            assign("description_de", desc_de)
            assign("description_en", desc_en)
            assign("conservation_state", status)
            assign("taxon_rank", taxon_rank)
            if slug is not None:
                assign("slug", slug)
            if changed:
                dst.add(animal)
                n_updated += 1
            else:
                n_skipped += 1
            id_map[art] = animal_id
            continue
        if not row.get("latin_name") or not row.get("name_de"):
            logger.warning("Animal %s missing latin or German name", art)
        name_en = row.get("name_en") or row.get("latin_name") or art
        if slug is None:
            logger.warning("Skipping animal %s due to missing slug", art)
            n_skipped += 1
            continue
        animal_id = uuid.uuid4()
        animals.append(
            models.Animal(
                id=animal_id,
                scientific_name=row.get("latin_name"),
                slug=slug,
                name_de=row.get("name_de"),
                name_en=name_en,
                latin_name=row.get("latin_name"),
                art=art,
                klasse=row.get("klasse"),
                ordnung=row.get("ordnung"),
                familie=row.get("familie"),
                description_en=desc_en,
                description_de=desc_de,
                conservation_state=status,
                taxon_rank=taxon_rank,
                category_id=category_map.get(row.get("klasse")),
            )
        )
        id_map[art] = animal_id
        n_inserted += 1
    if animals:
        dst.bulk_save_objects(animals)
    n_skipped = n_linked_animals - n_inserted - n_updated
    logger.info(
        "Animal import: total=%d linked=%d inserted=%d updated=%d skipped=%d",
        n_total_animals_in_src,
        n_linked_animals,
        n_inserted,
        n_updated,
        n_skipped,
    )
    return id_map
