"""Shared helpers for composing sighting history queries."""

from __future__ import annotations

import uuid

from sqlalchemy import Date, cast
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
    """Order sightings by most recent day, then timestamp, then creation time."""

    return query.order_by(
        cast(models.AnimalSighting.sighting_datetime, Date).desc(),
        models.AnimalSighting.sighting_datetime.desc(),
        models.AnimalSighting.created_at.desc(),
    )
