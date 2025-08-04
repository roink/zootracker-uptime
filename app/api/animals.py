from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid

from .. import schemas, models
from ..database import get_db
from ..utils.geometry import distance_km, distance_expr

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

    query = (
        db.query(models.Zoo)
        .join(models.ZooAnimal, models.Zoo.id == models.ZooAnimal.zoo_id)
        .filter(models.ZooAnimal.animal_id == animal_id)
    )

    if latitude is not None and longitude is not None:
        if db.bind.dialect.name == "postgresql":
            user_point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
            distance = distance_expr(user_point)
            rows = (
                query.filter(models.Zoo.location != None)
                .with_entities(models.Zoo, distance.label("distance_m"))
                .order_by(distance)
                .all()
            )
            return [
                schemas.ZooDetail(
                    id=z.id,
                    name=z.name,
                    address=z.address,
                    latitude=float(z.latitude) if z.latitude is not None else None,
                    longitude=float(z.longitude) if z.longitude is not None else None,
                    description=z.description,
                    distance_km=d / 1000 if d is not None else None,
                )
                for z, d in rows
            ]
        else:
            zoos = query.all()
            zoos_with_dist: list[schemas.ZooDetail] = []
            for z in zoos:
                if z.latitude is None or z.longitude is None:
                    dist = None
                else:
                    dist = distance_km(
                        float(latitude),
                        float(longitude),
                        float(z.latitude),
                        float(z.longitude),
                    )
                zoos_with_dist.append(
                    schemas.ZooDetail(
                        id=z.id,
                        name=z.name,
                        address=z.address,
                        latitude=float(z.latitude) if z.latitude is not None else None,
                        longitude=float(z.longitude) if z.longitude is not None else None,
                        description=z.description,
                        distance_km=dist,
                    )
                )
            zoos_with_dist.sort(
                key=lambda z: z.distance_km if z.distance_km is not None else float("inf")
            )
            return zoos_with_dist

    zoos = query.all()
    return [schemas.ZooDetail.from_orm(z) for z in zoos]
