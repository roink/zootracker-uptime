"""Import helpers for geographical reference tables."""

from __future__ import annotations

from sqlalchemy import Table, select
from sqlalchemy.orm import Session

from app import models


def import_regions(
    src: Session,
    dst: Session,
    continent_table: Table | None,
    country_table: Table | None,
) -> None:
    """Import continent and country names."""

    if continent_table is not None:
        rows = src.execute(select(continent_table)).mappings()
        for row in rows:
            dst.merge(
                models.ContinentName(
                    id=row.get("id"),
                    name_de=row.get("name_de"),
                    name_en=row.get("name_en"),
                )
            )
    if country_table is not None:
        rows = src.execute(select(country_table)).mappings()
        for row in rows:
            dst.merge(
                models.CountryName(
                    id=row.get("id"),
                    name_de=row.get("name_de"),
                    name_en=row.get("name_en"),
                    continent_id=row.get("continent_id"),
                )
            )
    dst.flush()
