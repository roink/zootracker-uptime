"""Shared query helpers for API endpoints that filter zoo data."""

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Query as SQLAQuery, Session

from .. import models


def validate_region_filters(
    db: Session, continent_id: int | None, country_id: int | None
) -> None:
    """Ensure provided region filters are consistent."""

    if continent_id is None or country_id is None:
        return

    exists_country = (
        db.query(models.CountryName)
        .filter(
            models.CountryName.id == country_id,
            models.CountryName.continent_id == continent_id,
        )
        .first()
    )
    if exists_country is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="country_id does not belong to continent_id",
        )


def apply_zoo_filters(
    query: SQLAQuery, q: str, continent_id: int | None, country_id: int | None
):
    """Apply textual and region filters to a base zoo query."""

    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(models.Zoo.name.ilike(pattern), models.Zoo.city.ilike(pattern))
        )
    if continent_id is not None:
        query = query.filter(models.Zoo.continent_id == continent_id)
    if country_id is not None:
        query = query.filter(models.Zoo.country_id == country_id)
    return query

