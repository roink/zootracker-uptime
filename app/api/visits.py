from typing import cast
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter()


@router.get("/visits", response_model=list[schemas.ZooVisitRead])
def list_visits(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[models.ZooVisit]:
    """List all visits for the authenticated user."""
    visits = db.query(models.ZooVisit).filter_by(user_id=user.id).all()
    return cast(list[models.ZooVisit], visits)


@router.get("/visits/ids", response_model=list[UUID])
def list_visited_zoo_ids(
    response: Response,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[UUID]:
    """Return unique zoo IDs where the user has a visit or sighting.

    A zoo is considered *visited* when there is a :class:`ZooVisit` row or at
    least one :class:`AnimalSighting` for the authenticated user.
    """
    q_visits = db.query(models.ZooVisit.zoo_id).filter_by(user_id=user.id)
    q_sightings = db.query(models.AnimalSighting.zoo_id).filter_by(user_id=user.id)
    rows = (
        q_visits.union(q_sightings)
        .order_by(models.ZooVisit.zoo_id)
        .all()
    )
    ids = [z for (z,) in rows]
    response.headers["Cache-Control"] = "private, max-age=60"
    return ids
