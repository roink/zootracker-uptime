from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
import uuid

from .. import schemas, models
from ..database import get_db
from ..config import RADIUS_KM_DEFAULT
from ..utils.geometry import distance_km, distance_expr

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

    if latitude is not None and longitude is not None:
        if db.bind.dialect.name == "postgresql":
            user_point = func.ST_SetSRID(func.ST_MakePoint(longitude, latitude), 4326)
            distance = distance_expr(user_point)
            rows = (
                query.filter(models.Zoo.location != None)
                .filter(func.ST_DWithin(models.Zoo.location, user_point, radius_km * 1000))
                .with_entities(models.Zoo, distance.label("distance_m"))
                .order_by(distance)
                .all()
            )
            return [
                schemas.ZooSearchResult(
                    id=z.id,
                    name=z.name,
                    address=z.address,
                    distance_km=d / 1000 if d is not None else None,
                )
                for z, d in rows
            ]
        else:
            zoos = query.all()
            results: list[schemas.ZooSearchResult] = []
            for zoo in zoos:
                if zoo.latitude is None or zoo.longitude is None:
                    continue
                dist = distance_km(
                    float(latitude),
                    float(longitude),
                    float(zoo.latitude),
                    float(zoo.longitude),
                )
                if dist <= radius_km:
                    results.append(
                        schemas.ZooSearchResult(
                            id=zoo.id,
                            name=zoo.name,
                            address=zoo.address,
                            distance_km=dist,
                        )
                    )
            results.sort(key=lambda z: z.distance_km if z.distance_km is not None else 0)
            return results

    zoos = query.all()
    return [
        schemas.ZooSearchResult(id=z.id, name=z.name, address=z.address)
        for z in zoos
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
