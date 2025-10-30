"""Helpers for staging animal categories during imports."""

from __future__ import annotations

import uuid

from sqlalchemy import Table, exists, or_, select
from sqlalchemy.orm import Session

from app import models


def stage_categories(
    src: Session,
    dst: Session,
    animal_table: Table,
    link_table: Table,
) -> dict[int | None, uuid.UUID]:
    """Ensure a :class:`Category` exists for each distinct ``klasse`` value."""

    zoo_count_col = getattr(animal_table.c, "zoo_count", None)
    parent_art_col = getattr(animal_table.c, "parent_art", None)
    klasses_stmt = select(animal_table.c.klasse).where(
        animal_table.c.art.isnot(None),
        animal_table.c.art != "",
    )
    activity_checks = [
        exists(
            select(1)
            .select_from(link_table)
            .where(
                link_table.c.art == animal_table.c.art,
                link_table.c.art.isnot(None),
                link_table.c.art != "",
            )
        )
    ]
    if zoo_count_col is not None:
        activity_checks.append(zoo_count_col > 0)
    klasses_stmt = klasses_stmt.where(or_(*activity_checks)).distinct()
    klasses: list[int | None] = []
    seen = set()
    for row in src.execute(klasses_stmt).mappings():
        klasse = row["klasse"]
        if klasse not in seen:
            seen.add(klasse)
            klasses.append(klasse)

    if parent_art_col is not None:
        parent_alias = animal_table.alias("parent_animals")
        parent_klasses_stmt = (
            select(parent_alias.c.klasse)
            .select_from(
                animal_table.join(
                    parent_alias,
                    parent_alias.c.art == parent_art_col,
                )
            )
            .where(
                parent_art_col.isnot(None),
                parent_art_col != "",
            )
            .distinct()
        )
        if zoo_count_col is not None:
            parent_klasses_stmt = parent_klasses_stmt.where(zoo_count_col > 0)
        for row in src.execute(parent_klasses_stmt).mappings():
            klasse = row["klasse"]
            if klasse not in seen:
                seen.add(klasse)
                klasses.append(klasse)
    existing = {
        row.name: row.id
        for row in dst.execute(select(models.Category.id, models.Category.name)).mappings()
    }
    mapping: dict[int | None, uuid.UUID] = {}
    to_add = []
    for klasse in klasses:
        name = f"Klasse {klasse}" if klasse is not None else "Uncategorized"
        if name in existing:
            mapping[klasse] = existing[name]
            continue
        cat_id = uuid.uuid4()
        to_add.append(models.Category(id=cat_id, name=name))
        existing[name] = cat_id
        mapping[klasse] = cat_id
    if to_add:
        dst.bulk_save_objects(to_add)
    return mapping
