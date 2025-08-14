from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload, load_only
import uuid

from .. import schemas, models
from ..database import get_db
from ..utils.geometry import query_zoos_with_distance
from .deps import resolve_coords


def to_zoodetail(z: models.Zoo, dist: float | None) -> schemas.ZooDetail:
    return schemas.ZooDetail(
        id=z.id,
        name=z.name,
        address=z.address,
        latitude=float(z.latitude) if z.latitude is not None else None,
        longitude=float(z.longitude) if z.longitude is not None else None,
        description=z.description,
        distance_km=dist,
    )

router = APIRouter()

@router.get("/animals", response_model=list[schemas.AnimalListItem])
def list_animals(
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    category: str | None = None,
    db: Session = Depends(get_db),
):
    """List animals filtered by search query, category and pagination."""

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="limit must be between 1 and 100",
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="offset must be >= 0",
        )

    query = (
        db.query(models.Animal)
        .join(models.Category, isouter=True)
        .options(joinedload(models.Animal.category))
    )

    if q:
        pattern = f"%{q}%"
        query = query.filter(models.Animal.common_name.ilike(pattern))

    if category:
        query = query.filter(models.Category.name == category)

    animals = (
        query.order_by(models.Animal.common_name)
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        schemas.AnimalListItem(
            id=a.id,
            common_name=a.common_name,
            scientific_name=a.scientific_name,
            category=a.category.name if a.category else None,
            description=a.description,
            default_image_url=a.default_image_url,
        )
        for a in animals
    ]

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
def get_animal_detail(
    animal_id: uuid.UUID,
    coords: tuple[float | None, float | None] = Depends(resolve_coords),
    db: Session = Depends(get_db),
):
    """Retrieve a single animal and the zoos where it can be found.

    When ``latitude`` and ``longitude`` are supplied the zoos are ordered by
    distance and include a ``distance_km`` field so the frontend only needs a
    single request.
    """
    animal = db.get(models.Animal, animal_id)
    if animal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found")

    latitude, longitude = coords

    query = (
        db.query(models.Zoo)
        .options(
            load_only(
                models.Zoo.id,
                models.Zoo.name,
                models.Zoo.address,
                models.Zoo.latitude,
                models.Zoo.longitude,
                models.Zoo.description,
            )
        )
        .join(models.ZooAnimal, models.Zoo.id == models.ZooAnimal.zoo_id)
        .filter(models.ZooAnimal.animal_id == animal_id)
    )

    results = query_zoos_with_distance(query, latitude, longitude, include_no_coords=True)

    zoos = [to_zoodetail(z, dist) for z, dist in results]

    return schemas.AnimalDetail(
        id=animal.id,
        common_name=animal.common_name,
        scientific_name=animal.scientific_name,
        category=animal.category.name if animal.category else None,
        description=animal.description,
        default_image_url=animal.default_image_url,
        zoos=zoos,
    )

@router.get(
    "/animals/{animal_id}/zoos",
    response_model=list[schemas.ZooDetail],
)
def list_zoos_for_animal(
    animal_id: uuid.UUID,
    coords: tuple[float | None, float | None] = Depends(resolve_coords),
    db: Session = Depends(get_db),
):
    """Return zoos that house the given animal ordered by distance if provided."""
    animal = db.get(models.Animal, animal_id)
    if animal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found")

    latitude, longitude = coords

    query = (
        db.query(models.Zoo)
        .options(
            load_only(
                models.Zoo.id,
                models.Zoo.name,
                models.Zoo.address,
                models.Zoo.latitude,
                models.Zoo.longitude,
                models.Zoo.description,
            )
        )
        .join(models.ZooAnimal, models.Zoo.id == models.ZooAnimal.zoo_id)
        .filter(models.ZooAnimal.animal_id == animal_id)
    )

    results = query_zoos_with_distance(query, latitude, longitude, include_no_coords=True)
    return [to_zoodetail(z, dist) for z, dist in results]
