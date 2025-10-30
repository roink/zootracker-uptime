"""Shared helpers for composing sighting history queries."""

from __future__ import annotations

import uuid

from typing import cast

from sqlalchemy import func, select
from sqlalchemy.orm import Query, Session, joinedload

from .. import models


def build_user_sightings_query(db: Session, user_id: uuid.UUID) -> Query:
    """Return a query selecting sightings for the given user with eager loads."""

    return (
        db.query(models.AnimalSighting)
        .options(
            joinedload(models.AnimalSighting.animal),
            joinedload(models.AnimalSighting.zoo),
        )
        .filter(models.AnimalSighting.user_id == user_id)
    )


def apply_recent_first_order(query: Query) -> Query:
    """Order sightings by most recent timestamp, then creation time."""

    return query.order_by(
        models.AnimalSighting.sighting_datetime.desc(),
        models.AnimalSighting.created_at.desc(),
    )


def count_query_rows(query: Query) -> int:
    """Return the number of rows a SQLAlchemy 1.x Query would emit."""

    subquery = query.order_by(None).subquery()
    result = query.session.execute(
        select(func.count()).select_from(subquery)
    ).scalar_one()
    return cast(int, result)
