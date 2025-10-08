"""Shared query helpers for API endpoints that filter zoo data."""

import re
from typing import Iterable

from fastapi import HTTPException, status
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Query as SQLAQuery, Session

from .. import models

# Generic words that should not be required to match individually when searching
# for zoos. Users frequently include these terms alongside the actual city or
# zoo name, so treating them as optional keeps the search lenient without
# discarding meaningful tokens.
_GENERIC_ZOO_TERMS = {
    "zoo",
    "tierpark",
    "tiergarten",
    "zoological",
    "park",
}

# Common suffixes in German and English location names that should be ignored
# when attempting to match search tokens. Trimming these suffixes makes
# "Duisburger" match a stored "Duisburg" entry while keeping shorter tokens
# intact.
_TRIMMABLE_SUFFIXES: tuple[str, ...] = ("ern", "ers", "er", "en", "es", "e", "s")


def _token_variants(token: str) -> Iterable[str]:
    """Return lenient matching variants for the provided token."""

    base = token.strip()
    if not base:
        return []

    variants: set[str] = {base}
    lowered = base.lower()
    for suffix in _TRIMMABLE_SUFFIXES:
        if lowered.endswith(suffix) and len(base) - len(suffix) >= 3:
            variants.add(base[: -len(suffix)])
    return variants


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
        normalized = " ".join(q.split())
        if normalized:
            tokens = [
                token
                for token in re.split(r"[\s,;:/\\-_]+", normalized)
                if token
            ]
            name_column = func.coalesce(models.Zoo.name, "")
            city_column = func.coalesce(models.Zoo.city, "")
            combined_columns = [
                func.concat(name_column, " ", city_column),
                func.concat(city_column, " ", name_column),
            ]
            combined_pattern = f"%{normalized}%"
            combined_condition = or_(
                name_column.ilike(combined_pattern),
                city_column.ilike(combined_pattern),
                *[column.ilike(combined_pattern) for column in combined_columns],
            )

            token_clauses = []
            for token in tokens:
                if token.lower() in _GENERIC_ZOO_TERMS:
                    continue
                variants = _token_variants(token)
                variant_clauses = [
                    or_(
                        name_column.ilike(f"%{variant}%"),
                        city_column.ilike(f"%{variant}%"),
                    )
                    for variant in variants
                    if variant
                ]
                if variant_clauses:
                    token_clauses.append(or_(*variant_clauses))

            if token_clauses:
                token_condition = and_(*token_clauses)
                query = query.filter(or_(combined_condition, token_condition))
            else:
                query = query.filter(combined_condition)
    if continent_id is not None:
        query = query.filter(models.Zoo.continent_id == continent_id)
    if country_id is not None:
        query = query.filter(models.Zoo.country_id == country_id)
    return query

