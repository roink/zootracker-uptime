"""Helpers for linking animals and zoos during imports."""

from __future__ import annotations

import logging
import uuid
from typing import Dict

from sqlalchemy import Table, bindparam, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app import models

logger = logging.getLogger(__name__)


def import_links(
    src: Session,
    dst: Session,
    link_table: Table,
    zoo_map: Dict[int, uuid.UUID],
    animal_map: Dict[str, uuid.UUID],
) -> None:
    rows = src.execute(select(link_table)).mappings()
    stmt = pg_insert(models.ZooAnimal.__table__).on_conflict_do_nothing()
    batch: list[dict] = []
    batch_size = 1000
    processed = 0
    for row in rows:
        zoo_id = zoo_map.get(row["zoo_id"])
        animal_id = animal_map.get(row["art"])
        if zoo_id and animal_id:
            batch.append({"zoo_id": zoo_id, "animal_id": animal_id})
            if len(batch) >= batch_size:
                processed = _flush_batch(dst, stmt, batch, processed)
    if batch:
        _flush_batch(dst, stmt, batch, processed)
    _update_counts(dst)


def _flush_batch(dst: Session, stmt, batch: list[dict], processed: int) -> int:
    try:
        dst.execute(stmt, batch)
    except Exception as exc:  # pragma: no cover - defensive
        err = getattr(exc, "orig", exc)
        logger.error(
            "Failed inserting link batch %d-%d: %s",
            processed,
            processed + len(batch),
            err,
        )
        raise
    processed += len(batch)
    batch.clear()
    return processed


def _update_counts(dst: Session) -> None:
    zoo_counts = dst.execute(
        select(models.ZooAnimal.zoo_id, func.count().label("cnt")).group_by(models.ZooAnimal.zoo_id)
    ).all()
    if zoo_counts:
        dst.execute(
            models.Zoo.__table__.update().where(models.Zoo.id == bindparam("z_id")),
            [{"z_id": zoo_id, "animal_count": count} for zoo_id, count in zoo_counts],
        )
    animal_counts = dst.execute(
        select(models.ZooAnimal.animal_id, func.count().label("cnt")).group_by(models.ZooAnimal.animal_id)
    ).all()
    if animal_counts:
        dst.execute(
            models.Animal.__table__.update().where(models.Animal.id == bindparam("a_id")),
            [{"a_id": animal_id, "zoo_count": count} for animal_id, count in animal_counts],
        )
