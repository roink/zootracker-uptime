"""Shared query helpers for API endpoints that filter zoo data."""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from fastapi import HTTPException, status
from sqlalchemy import and_, func, literal, or_
from sqlalchemy.orm import Query as SQLAQuery, Session

from .. import models

# Generic words that should not be required to match individually when searching
# for zoos. Users frequently include these terms alongside the actual city or
# zoo name, so treating them as optional keeps the search lenient without
# discarding meaningful tokens.
GENERIC_ZOO_TERMS = {
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
_TRIMMABLE_SUFFIXES: tuple[str, ...] = ("er", "en", "s")


def _token_variants(token: str, suffixes: Iterable[str]) -> set[str]:
    """Return lenient matching variants for the provided token."""

    base = token.strip()
    if not base:
        return set()

    variants: set[str] = {base}
    lowered = base.lower()
    for suffix in suffixes:
        if lowered.endswith(suffix) and len(base) - len(suffix) >= 3:
            variants.add(base[: -len(suffix)])
    return variants


def _build_pattern(value: str) -> str:
    """Return an escaped ILIKE pattern for substring searches."""

    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _with_unaccent(expr, dialect: str):
    """Wrap the expression with the immutable f_unaccent helper when available."""

    if dialect == "postgresql":
        return func.f_unaccent(expr)
    return expr


def apply_tokenized_text_filter(
    query: SQLAQuery,
    q: str,
    columns: Sequence,
    *,
    ignored_terms: Iterable[str] | None = None,
    suffixes: Iterable[str] | None = None,
) -> SQLAQuery:
    """Filter ``query`` by requiring each meaningful token to match ``columns``."""

    if not q:
        return query

    normalized = " ".join(q.split())
    if not normalized:
        return query

    tokens = [
        token
        for token in re.split(r"[\s,;:/\\-_]+", normalized)
        if token
    ]
    if not tokens:
        return query

    ignored = {term.lower() for term in (ignored_terms or [])}
    suffix_choices = tuple(suffixes or ())

    bind = getattr(getattr(query, "session", None), "bind", None)
    dialect = bind.dialect.name if bind is not None else ""

    coalesced_columns = [func.coalesce(column, "") for column in columns]

    combined_expressions = []
    if coalesced_columns:
        combined_expressions.append(func.concat_ws(" ", *coalesced_columns))
        if len(coalesced_columns) == 2:
            combined_expressions.append(
                func.concat_ws(" ", coalesced_columns[1], coalesced_columns[0])
            )

    combined_pattern = _build_pattern(normalized)
    combined_condition_clauses = []
    for expression in (*coalesced_columns, *combined_expressions):
        left = _with_unaccent(expression, dialect)
        right = _with_unaccent(literal(combined_pattern), dialect)
        combined_condition_clauses.append(left.ilike(right, escape="\\"))

    combined_condition = or_(*combined_condition_clauses)

    token_clauses = []
    for token in tokens:
        if token.lower() in ignored:
            continue
        variants = _token_variants(token, suffix_choices or _TRIMMABLE_SUFFIXES)
        if not variants:
            continue
        variant_conditions = []
        for variant in variants:
            pattern = _build_pattern(variant)
            right = _with_unaccent(literal(pattern), dialect)
            for column in coalesced_columns:
                left = _with_unaccent(column, dialect)
                variant_conditions.append(left.ilike(right, escape="\\"))
        if variant_conditions:
            token_clauses.append(or_(*variant_conditions))

    if token_clauses:
        query = query.filter(or_(combined_condition, and_(*token_clauses)))
    else:
        query = query.filter(combined_condition)
    return query


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

    query = apply_tokenized_text_filter(
        query,
        q,
        columns=(models.Zoo.name, models.Zoo.city),
        ignored_terms=GENERIC_ZOO_TERMS,
        suffixes=_TRIMMABLE_SUFFIXES,
    )
    if continent_id is not None:
        query = query.filter(models.Zoo.continent_id == continent_id)
    if country_id is not None:
        query = query.filter(models.Zoo.country_id == country_id)
    return query

