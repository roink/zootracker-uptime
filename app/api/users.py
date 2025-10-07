import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, load_only

from .. import schemas, models
from ..auth import hash_password, get_user, get_current_user
from ..database import get_db
from .deps import require_json, resolve_coords
from .common_filters import apply_zoo_filters, validate_region_filters
from ..utils.geometry import query_zoos_with_distance

router = APIRouter()


def ensure_same_user(user_id: uuid.UUID, current_user: models.User) -> None:
    """Ensure the path user_id matches the authenticated user."""
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access this resource for another user",
        )


def _visited_zoo_ids_subquery(db: Session, user_id: uuid.UUID):
    """Return a subquery selecting zoo IDs the user has visited."""

    visits = (
        db.query(models.ZooVisit.zoo_id.label("zoo_id"))
        .filter(models.ZooVisit.user_id == user_id)
        .filter(models.ZooVisit.zoo_id.isnot(None))
    )
    sightings = (
        db.query(models.AnimalSighting.zoo_id.label("zoo_id"))
        .filter(models.AnimalSighting.user_id == user_id)
        .filter(models.AnimalSighting.zoo_id.isnot(None))
    )
    return visits.union(sightings).subquery()


def _favorite_zoo_ids(db: Session, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Return the set of zoo IDs the user has favorited."""

    return {
        row[0]
        for row in (
            db.query(models.UserFavoriteZoo.zoo_id)
            .filter(models.UserFavoriteZoo.user_id == user_id)
            .all()
        )
    }


def _build_user_zoo_page(
    query,
    latitude: float | None,
    longitude: float | None,
    limit: int,
    offset: int,
    favorite_ids: set[uuid.UUID] | None = None,
):
    """Execute a paginated zoo query and serialize the response."""

    favorite_ids = favorite_ids or set()
    total = query.count()
    items: list[schemas.ZooSearchResult] = []
    if total and offset < total:
        results = query_zoos_with_distance(
            query,
            latitude,
            longitude,
            limit=limit,
            offset=offset,
        )
        items = [
            schemas.ZooSearchResult(
                id=z.id,
                slug=z.slug,
                name=z.name,
                city=z.city,
                distance_km=distance,
                country_name_en=z.country.name_en if z.country else None,
                country_name_de=z.country.name_de if z.country else None,
                is_favorite=z.id in favorite_ids,
            )
            for z, distance in results
        ]

    return schemas.ZooSearchPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


def _serialize_map_points(zoos: list[models.Zoo]):
    """Transform zoos into lightweight map points."""

    return [
        schemas.ZooMapPoint(
            id=z.id,
            slug=z.slug,
            name=z.name,
            city=z.city,
            latitude=float(z.latitude) if z.latitude is not None else None,
            longitude=float(z.longitude) if z.longitude is not None else None,
        )
        for z in zoos
    ]

@router.post("/users", response_model=schemas.UserRead, dependencies=[Depends(require_json)])
def create_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user with a hashed password."""
    if get_user(db, user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(user_in.password)
    user = models.User(
        name=user_in.name,
        email=user_in.email,
        password_hash=hashed,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get(
    "/users/{user_id}/zoos/visited",
    response_model=schemas.ZooSearchPage,
)
def list_user_visited_zoos(
    user_id: uuid.UUID,
    response: Response,
    q: str = "",
    continent_id: int | None = None,
    country_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
    coords: tuple[float | None, float | None] = Depends(resolve_coords),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return zoos visited by the authenticated user with pagination."""

    ensure_same_user(user_id, current_user)
    validate_region_filters(db, continent_id, country_id)

    visited_ids = _visited_zoo_ids_subquery(db, user_id)
    query = (
        db.query(models.Zoo)
        .options(joinedload(models.Zoo.country))
        .filter(models.Zoo.id.in_(select(visited_ids.c.zoo_id)))
    )
    query = apply_zoo_filters(query, q, continent_id, country_id)

    latitude, longitude = coords
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Vary"] = "Authorization"
    favorite_ids = _favorite_zoo_ids(db, user_id)
    return _build_user_zoo_page(
        query, latitude, longitude, limit, offset, favorite_ids=favorite_ids
    )


@router.get(
    "/users/{user_id}/zoos/not-visited",
    response_model=schemas.ZooSearchPage,
)
def list_user_not_visited_zoos(
    user_id: uuid.UUID,
    response: Response,
    q: str = "",
    continent_id: int | None = None,
    country_id: int | None = None,
    limit: int = Query(default=20, ge=1, le=10000),
    offset: int = Query(default=0, ge=0),
    coords: tuple[float | None, float | None] = Depends(resolve_coords),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return zoos the authenticated user has not yet visited."""

    ensure_same_user(user_id, current_user)
    validate_region_filters(db, continent_id, country_id)

    visited_ids = _visited_zoo_ids_subquery(db, user_id)
    query = db.query(models.Zoo).options(joinedload(models.Zoo.country))
    query = query.filter(~models.Zoo.id.in_(select(visited_ids.c.zoo_id)))
    query = apply_zoo_filters(query, q, continent_id, country_id)

    latitude, longitude = coords
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Vary"] = "Authorization"
    favorite_ids = _favorite_zoo_ids(db, user_id)
    return _build_user_zoo_page(
        query, latitude, longitude, limit, offset, favorite_ids=favorite_ids
    )


@router.get(
    "/users/{user_id}/zoos/visited/map",
    response_model=list[schemas.ZooMapPoint],
)
def list_user_visited_zoos_for_map(
    user_id: uuid.UUID,
    response: Response,
    q: str = "",
    continent_id: int | None = None,
    country_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return lightweight map data for zoos visited by the user."""

    ensure_same_user(user_id, current_user)
    validate_region_filters(db, continent_id, country_id)

    visited_ids = _visited_zoo_ids_subquery(db, user_id)
    query = (
        db.query(models.Zoo)
        .options(
            load_only(
                models.Zoo.id,
                models.Zoo.slug,
                models.Zoo.name,
                models.Zoo.city,
                models.Zoo.latitude,
                models.Zoo.longitude,
            )
        )
        .filter(models.Zoo.id.in_(select(visited_ids.c.zoo_id)))
    )
    query = apply_zoo_filters(query, q, continent_id, country_id)
    zoos = query.order_by(models.Zoo.name).all()
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Vary"] = "Authorization"
    return _serialize_map_points(zoos)


@router.get(
    "/users/{user_id}/zoos/not-visited/map",
    response_model=list[schemas.ZooMapPoint],
)
def list_user_not_visited_zoos_for_map(
    user_id: uuid.UUID,
    response: Response,
    q: str = "",
    continent_id: int | None = None,
    country_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Return map data for zoos the user has not visited."""

    ensure_same_user(user_id, current_user)
    validate_region_filters(db, continent_id, country_id)

    visited_ids = _visited_zoo_ids_subquery(db, user_id)
    query = (
        db.query(models.Zoo)
        .options(
            load_only(
                models.Zoo.id,
                models.Zoo.slug,
                models.Zoo.name,
                models.Zoo.city,
                models.Zoo.latitude,
                models.Zoo.longitude,
            )
        )
        .filter(~models.Zoo.id.in_(select(visited_ids.c.zoo_id)))
    )
    query = apply_zoo_filters(query, q, continent_id, country_id)
    zoos = query.order_by(models.Zoo.name).all()
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Vary"] = "Authorization"
    return _serialize_map_points(zoos)

@router.get("/users/{user_id}/animals", response_model=list[schemas.AnimalRead])
def list_seen_animals(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return all unique animals seen by the specified user."""
    ensure_same_user(user_id, user)
    animals = (
        db.query(models.Animal)
        .join(models.AnimalSighting, models.Animal.id == models.AnimalSighting.animal_id)
        .filter(models.AnimalSighting.user_id == user_id)
        .distinct()
        .all()
    )
    return animals


@router.get("/users/{user_id}/animals/ids", response_model=list[uuid.UUID])
def list_seen_animal_ids(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return IDs of unique animals seen by the specified user."""
    ensure_same_user(user_id, user)
    ids = (
        db.query(models.AnimalSighting.animal_id)
        .filter(models.AnimalSighting.user_id == user_id)
        .distinct()
        .all()
    )
    return [row[0] for row in ids]


@router.get("/users/{user_id}/animals/count", response_model=schemas.Count)
def count_seen_animals(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return the number of unique animals seen by the specified user."""
    ensure_same_user(user_id, user)
    count = (
        db.query(func.count(func.distinct(models.AnimalSighting.animal_id)))
        .filter(models.AnimalSighting.user_id == user_id)
        .scalar()
    ) or 0
    return {"count": count}
