"""Utilities for importing taxonomy-related reference data."""

from __future__ import annotations

from sqlalchemy import Table, select
from sqlalchemy.orm import Session

from app import models


def import_taxon_names(
    src: Session,
    dst: Session,
    klasse_table: Table | None,
    ordnung_table: Table | None,
    familie_table: Table | None,
) -> None:
    """Import class, order and family names if available."""

    if klasse_table is not None:
        rows = src.execute(select(klasse_table)).mappings()
        for row in rows:
            dst.merge(
                models.ClassName(
                    klasse=row.get("klasse"),
                    name_de=row.get("name_de"),
                    name_en=row.get("name_en"),
                )
            )
    if ordnung_table is not None:
        rows = src.execute(select(ordnung_table)).mappings()
        for row in rows:
            dst.merge(
                models.OrderName(
                    ordnung=row.get("ordnung"),
                    name_de=row.get("name_de"),
                    name_en=row.get("name_en"),
                )
            )
    if familie_table is not None:
        rows = src.execute(select(familie_table)).mappings()
        for row in rows:
            dst.merge(
                models.FamilyName(
                    familie=row.get("familie"),
                    name_de=row.get("name_de"),
                    name_en=row.get("name_en"),
                )
            )
    # Make sure inserted taxon names are written before dependent rows
    dst.flush()
