"""Helpers for staging animal categories during imports."""

from __future__ import annotations

import uuid
from typing import Dict

from sqlalchemy import Table, exists, select
from sqlalchemy.orm import Session

from app import models


def stage_categories(
    src: Session,
    dst: Session,
    animal_table: Table,
    link_table: Table,
) -> Dict[int | None, uuid.UUID]:
    """Ensure a :class:`Category` exists for each distinct ``klasse`` value."""

    klasses_stmt = (
        select(animal_table.c.klasse)
        .where(
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
        .distinct()
    )
    klasses = [row["klasse"] for row in src.execute(klasses_stmt).mappings()]
    existing = {
        row.name: row.id
        for row in dst.execute(select(models.Category.id, models.Category.name)).mappings()
    }
    mapping: Dict[int | None, uuid.UUID] = {}
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
