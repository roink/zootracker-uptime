from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from .. import schemas, models
from ..database import get_db
from ..config import RADIUS_KM_DEFAULT
from ..utils.geometry import query_zoos_with_distance

router = APIRouter()

@router.get("/zoos", response_model=list[schemas.ZooSearchResult])
def search_zoos(
    q: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float = RADIUS_KM_DEFAULT,
    db: Session = Depends(get_db),
):
    """Search for zoos by name and optional distance from a point."""
    query = db.query(models.Zoo)
    if q:
        pattern = f"%{q}%"
        query = query.filter(models.Zoo.name.ilike(pattern))

    results = query_zoos_with_distance(query, latitude, longitude, radius_km)
    return [
        schemas.ZooSearchResult(
            id=z.id,
            name=z.name,
            address=z.address,
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

@router.get("/zoos/{zoo_id}/animals", response_model=list[schemas.AnimalRead])
def list_zoo_animals(zoo_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return animals that are associated with a specific zoo."""
    return (
        db.query(models.Animal)
        .join(models.ZooAnimal, models.Animal.id == models.ZooAnimal.animal_id)
        .filter(models.ZooAnimal.zoo_id == zoo_id)
        .all()
    )
