from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from uuid import UUID

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter()


@router.get("/visits", response_model=list[schemas.ZooVisitRead])
def list_visits(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """List all visits for the authenticated user."""
    return db.query(models.ZooVisit).filter_by(user_id=user.id).all()


@router.get("/visits/ids", response_model=list[UUID])
def list_visited_zoo_ids(
    response: Response,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return unique zoo IDs visited by the authenticated user."""
    q_visits = db.query(models.ZooVisit.zoo_id).filter_by(user_id=user.id)
    q_sightings = db.query(models.AnimalSighting.zoo_id).filter_by(user_id=user.id)
    rows = q_visits.union(q_sightings).all()
    ids = [z for (z,) in rows]
    response.headers["Cache-Control"] = "private, max-age=60"
    return ids
