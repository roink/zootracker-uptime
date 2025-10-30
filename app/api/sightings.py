"""API routes for managing animal sightings."""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..auth import get_current_user
from ..database import get_db
from .deps import require_json
from .common_sightings import apply_recent_first_order, build_user_sightings_query


audit_logger = logging.getLogger("app.audit")


router = APIRouter()


@router.post(
    "/sightings",
    response_model=schemas.AnimalSightingRead,
    dependencies=[Depends(require_json)],
)
def create_sighting(
    sighting_in: schemas.AnimalSightingCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.AnimalSighting:
    """Record an animal sighting for the authenticated user."""

    if db.get(models.Zoo, sighting_in.zoo_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zoo not found"
        )

    if db.get(models.Animal, sighting_in.animal_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found"
        )

    data = sighting_in.model_dump(exclude_unset=True)
    data["user_id"] = user.id
    sighting = models.AnimalSighting(**data)
    db.add(sighting)
    db.commit()
    db.refresh(sighting)
    audit_logger.info(
        "Sighting created",
        extra={
            "event_dataset": "zoo-tracker-api.audit",
            "event_action": "created",
            "event_kind": "audit",
            "sighting_id": str(sighting.id),
            "change_summary": ",".join(sorted(data.keys())),
        },
    )
    return sighting


@router.get("/sightings/{sighting_id}", response_model=schemas.AnimalSightingRead)
def read_sighting(
    sighting_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.AnimalSighting:
    """Retrieve a single sighting owned by the current user."""

    sighting = (
        db.query(models.AnimalSighting)
        .options(
            joinedload(models.AnimalSighting.animal),
            joinedload(models.AnimalSighting.zoo),
        )
        .filter(models.AnimalSighting.id == sighting_id)
        .first()
    )
    if sighting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sighting not found",
        )
    if sighting.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this sighting",
        )
    return sighting


@router.patch(
    "/sightings/{sighting_id}",
    response_model=schemas.AnimalSightingRead,
    dependencies=[Depends(require_json)],
)
def update_sighting(
    sighting_id: uuid.UUID,
    sighting_in: schemas.AnimalSightingUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> models.AnimalSighting:
    """Update fields of a sighting owned by the current user."""

    sighting = db.get(models.AnimalSighting, sighting_id)
    if sighting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sighting not found"
        )
    if sighting.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this sighting",
        )

    data = sighting_in.model_dump(exclude_unset=True)

    if "zoo_id" in data and db.get(models.Zoo, data["zoo_id"]) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zoo not found"
        )

    if "animal_id" in data and db.get(models.Animal, data["animal_id"]) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found"
        )

    for key, value in data.items():
        setattr(sighting, key, value)

    db.add(sighting)
    db.commit()
    db.refresh(sighting)
    audit_logger.info(
        "Sighting updated",
        extra={
            "event_dataset": "zoo-tracker-api.audit",
            "event_action": "updated",
            "event_kind": "audit",
            "sighting_id": str(sighting.id),
            "change_summary": ",".join(sorted(data.keys()) or ["no_changes"]),
        },
    )
    return sighting


@router.get("/sightings", response_model=list[schemas.AnimalSightingRead])
def list_sightings(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[models.AnimalSighting]:
    """Retrieve all animal sightings recorded by the current user."""

    query = build_user_sightings_query(db, user.id)
    return apply_recent_first_order(query).all()


@router.delete("/sightings/{sighting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sighting(
    sighting_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> Response:
    """Delete an animal sighting if owned by the current user."""

    sighting = db.get(models.AnimalSighting, sighting_id)
    if sighting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Sighting not found"
        )

    if sighting.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete sighting",
        )

    db.delete(sighting)
    db.commit()
    audit_logger.info(
        "Sighting deleted",
        extra={
            "event_dataset": "zoo-tracker-api.audit",
            "event_action": "deleted",
            "event_kind": "audit",
            "sighting_id": str(sighting_id),
            "change_summary": "record_removed",
        },
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
