from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from .. import schemas, models
from ..database import get_db

router = APIRouter()

@router.get("/animals", response_model=list[schemas.AnimalRead])
def list_animals(q: str = "", db: Session = Depends(get_db)):
    """List animals optionally filtered by a search query."""
    query = db.query(models.Animal)
    if q:
        pattern = f"%{q}%"
        query = query.filter(models.Animal.common_name.ilike(pattern))
    return query.all()

@router.get("/search", response_model=schemas.SearchResults)
def combined_search(q: str = "", limit: int = 5, db: Session = Depends(get_db)):
    """Return top zoos and animals matching the query."""
    zoo_q = db.query(models.Zoo)
    if q:
        pattern = f"%{q}%"
        zoo_q = zoo_q.filter(models.Zoo.name.ilike(pattern))
    zoos = zoo_q.limit(limit).all()

    animal_q = db.query(models.Animal)
    if q:
        pattern = f"%{q}%"
        animal_q = animal_q.filter(models.Animal.common_name.ilike(pattern))
    animals = animal_q.limit(limit).all()

    return {"zoos": zoos, "animals": animals}

@router.get("/animals/{animal_id}", response_model=schemas.AnimalDetail)
def get_animal_detail(animal_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve a single animal and the zoos where it can be found."""
    animal = db.get(models.Animal, animal_id)
    if animal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found")

    zoos = (
        db.query(models.Zoo)
        .join(models.ZooAnimal, models.Zoo.id == models.ZooAnimal.zoo_id)
        .filter(models.ZooAnimal.animal_id == animal_id)
        .all()
    )

    return schemas.AnimalDetail(
        id=animal.id,
        common_name=animal.common_name,
        scientific_name=animal.scientific_name,
        category=animal.category.name if animal.category else None,
        description=animal.description,
        zoos=zoos,
    )

@router.get(
    "/animals/{animal_id}/zoos",
    response_model=list[schemas.ZooDetail],
)
def list_zoos_for_animal(
    animal_id: uuid.UUID,
    latitude: float | None = None,
    longitude: float | None = None,
    db: Session = Depends(get_db),
):
    """Return zoos that house the given animal ordered by distance if provided."""
    animal = db.get(models.Animal, animal_id)
    if animal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found")

    if latitude is not None and not -90 <= latitude <= 90:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid latitude")
    if longitude is not None and not -180 <= longitude <= 180:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid longitude")

    zoos = (
        db.query(models.Zoo)
        .join(models.ZooAnimal, models.Zoo.id == models.ZooAnimal.zoo_id)
        .filter(models.ZooAnimal.animal_id == animal_id)
        .all()
    )

    if latitude is not None and longitude is not None:
        from math import radians, cos, sin, asin, sqrt

        def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            c = 2 * asin(sqrt(a))
            return 6371 * c

        zoos.sort(
            key=lambda z: haversine(
                float(latitude),
                float(longitude),
                float(z.latitude) if z.latitude is not None else 0.0,
                float(z.longitude) if z.longitude is not None else 0.0,
            )
            if z.latitude is not None and z.longitude is not None
            else float("inf")
        )

    return zoos
