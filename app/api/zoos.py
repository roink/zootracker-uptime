from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from .. import schemas, models
from ..main import get_db

router = APIRouter()

@router.get("/zoos", response_model=list[schemas.ZooRead])
def search_zoos(
    q: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float = 50.0,
    db: Session = Depends(get_db),
):
    """Search for zoos by name and optional distance from a point."""
    query = db.query(models.Zoo)
    if q:
        pattern = f"%{q}%"
        query = query.filter(models.Zoo.name.ilike(pattern))

    zoos = query.all()

    if latitude is not None and longitude is not None:
        def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            """Return distance in kilometers between two lat/lon points."""
            from math import radians, cos, sin, asin, sqrt

            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            c = 2 * asin(sqrt(a))
            return 6371 * c

        results = []
        for zoo in zoos:
            if zoo.latitude is None or zoo.longitude is None:
                continue
            dist = haversine(float(latitude), float(longitude), float(zoo.latitude), float(zoo.longitude))
            if dist <= radius_km:
                results.append(zoo)
        return results

    return zoos

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
