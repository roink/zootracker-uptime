"""Import utilities for animal records."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Dict

from sqlalchemy import Table, exists, func, select, text
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

    def _normalize_art(value: str | None) -> str | None:
        if not isinstance(value, str):
            return None
        value = value.strip()
        return value or None

    existing = {
        art: row.id
        for row in dst.execute(select(models.Animal.id, models.Animal.art)).mappings()
        if (art := _normalize_art(row.art)) is not None
    }

    zoo_count_col = getattr(animal_table.c, "zoo_count", None)
    parent_art_col = getattr(animal_table.c, "parent_art", None)
    main_stmt = select(animal_table).where(
        animal_table.c.art.isnot(None),
        animal_table.c.art != "",
    )
    if zoo_count_col is not None:
        main_stmt = main_stmt.where(zoo_count_col > 0)
    else:
        main_stmt = main_stmt.where(
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
    main_rows = list(
        src.execute(main_stmt.order_by(animal_table.c.art)).mappings()
    )
    main_art_values = {
        art
        for row in main_rows
        if (art := _normalize_art(row.get("art"))) is not None
    }
    parent_targets = {
        parent
        for row in main_rows
        if parent_art_col is not None
        and (parent := _normalize_art(row.get("parent_art"))) is not None
    }
    parent_rows = []
    if parent_targets and parent_art_col is not None:
        parent_rows = list(
            src.execute(
                select(animal_table)
                .where(animal_table.c.art.in_(parent_targets))
                .order_by(animal_table.c.art)
            ).mappings()
        )
    n_total_animals_in_src = src.execute(
        select(func.count()).select_from(animal_table)
    ).scalar_one()
    n_zoo_animals = len(main_art_values)
    n_parent_animals = len(parent_targets)
    animals = []
    id_map: Dict[str, uuid.UUID] = {}
    n_inserted = 0
    n_updated = 0
    n_skipped = 0
    # Optional: if Postgres, defer the self-referencing FK until commit for robustness.
    try:
        bind = dst.get_bind()
        if bind.dialect.name == "postgresql":
            dst.execute(text("SET CONSTRAINTS fk_animals_parent_art DEFERRED"))
    except Exception:
        # Best effort – SQLite and older PostgreSQL releases may not support deferrable constraints.
        pass

    processed_arts: set[str] = set()
    # Insert parent taxa before main rows; duplicates are skipped via processed_arts.
    for row in parent_rows + main_rows:
        raw_art = row.get("art")
        art = _normalize_art(raw_art)
        if art is None:
            continue
        if art in processed_arts:
            continue
        processed_arts.add(art)
        desc_de = _clean_text(row.get("description_de"))
        desc_en = _clean_text(row.get("description_en"))
        status = normalize_status(row.get("iucn_conservation_status"))
        taxon_rank = row.get("taxon_rank")
        if taxon_rank:
            taxon_rank = taxon_rank.strip()
        parent_art = _normalize_art(row.get("parent_art"))
        slug = row.get("slug")
        if isinstance(slug, str):
            slug = slug.strip() or None
        if slug is None and art:
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
            if overwrite and animal.parent_art != parent_art:
                animal.parent_art = parent_art
                changed = True
            if changed:
                dst.add(animal)
                n_updated += 1
            else:
                n_skipped += 1
            id_map[art] = animal_id
            if isinstance(raw_art, str) and raw_art.strip() and raw_art != art:
                id_map[raw_art] = animal_id
            continue
        if not row.get("latin_name") or not row.get("name_de"):
            logger.warning("Animal %s missing latin or German name", art)
        name_en = row.get("name_en") or row.get("latin_name") or art
        if slug is None:
            logger.warning("Skipping animal %s due to missing slug", art)
            n_skipped += 1
            continue
        category_id = category_map.get(row.get("klasse"))
        if category_id is None:
            logger.warning(
                "Skipping animal %s due to missing category for klasse %s",
                art,
                row.get("klasse"),
            )
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
                parent_art=parent_art,
                klasse=row.get("klasse"),
                ordnung=row.get("ordnung"),
                familie=row.get("familie"),
                description_en=desc_en,
                description_de=desc_de,
                conservation_state=status,
                taxon_rank=taxon_rank,
                category_id=category_id,
            )
        )
        id_map[art] = animal_id
        if isinstance(raw_art, str) and raw_art.strip() and raw_art != art:
            id_map[raw_art] = animal_id
        n_inserted += 1
    if animals:
        dst.bulk_save_objects(animals)
    logger.info(
        "Animal import: total=%d parents=%d zoo_count=%d inserted=%d updated=%d skipped=%d",
        n_total_animals_in_src,
        n_parent_animals,
        n_zoo_animals,
        n_inserted,
        n_updated,
        n_skipped,
    )
    return id_map
