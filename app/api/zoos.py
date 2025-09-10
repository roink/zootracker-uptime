from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, exists
from sqlalchemy.orm import Session
import uuid

from .. import schemas, models
from ..database import get_db
from ..utils.geometry import query_zoos_with_distance
from ..auth import get_current_user
from .deps import resolve_coords

router = APIRouter()

@router.get("/zoos", response_model=list[schemas.ZooSearchResult])
def search_zoos(
    q: str = "",
    coords: tuple[float | None, float | None] = Depends(resolve_coords),
    db: Session = Depends(get_db),
):
    """Search for zoos by name and optional distance from a point."""
    query = db.query(models.Zoo)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(models.Zoo.name.ilike(pattern), models.Zoo.city.ilike(pattern))
        )
    latitude, longitude = coords
    # Always return all zoos, ordering by distance when coordinates are provided
    results = query_zoos_with_distance(query, latitude, longitude)
    return [
        schemas.ZooSearchResult(
            id=z.id,
            name=z.name,
            address=z.address,
            city=z.city,
            distance_km=dist,
        )
        for z, dist in results
    ]

@router.get("/zoos/{zoo_id}", response_model=schemas.ZooDetail)
def get_zoo(zoo_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve detailed information about a zoo."""
    zoo = db.get(models.Zoo, zoo_id)
    if zoo is None:
        raise HTTPException(status_code=404, detail="Zoo not found")
    return zoo


@router.get("/zoos/{zoo_id}/visited", response_model=schemas.Visited)
def has_visited_zoo(
    zoo_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return whether the authenticated user has visited a given zoo."""
    visited = db.query(
        exists().where(
            models.ZooVisit.user_id == user.id,
            models.ZooVisit.zoo_id == zoo_id,
        )
    ).scalar()
    if not visited:
        visited = db.query(
            exists().where(
                models.AnimalSighting.user_id == user.id,
                models.AnimalSighting.zoo_id == zoo_id,
            )
        ).scalar()
    return {"visited": bool(visited)}

@router.get("/zoos/{zoo_id}/animals", response_model=list[schemas.AnimalRead])
def list_zoo_animals(zoo_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return animals that are associated with a specific zoo."""
    return (
        db.query(models.Animal)
        .join(models.ZooAnimal, models.Animal.id == models.ZooAnimal.animal_id)
        .filter(models.ZooAnimal.zoo_id == zoo_id)
        .order_by(models.Animal.zoo_count.desc())
        .all()
    )
