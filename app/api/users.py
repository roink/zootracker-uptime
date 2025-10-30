import uuid
from datetime import datetime, timezone
from typing import Annotated, cast

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Query as SAQuery, Session, joinedload, load_only
from sqlalchemy.sql.selectable import Subquery

from .. import schemas, models
from ..auth import get_current_user, get_user, hash_password
from ..utils.account_notifications import enqueue_existing_signup_notice
from ..utils.email_verification import enqueue_verification_email, issue_verification_token
from ..database import get_db
from ..logging import anonymize_ip
from .deps import require_json, resolve_coords
from .common_filters import apply_zoo_filters, validate_region_filters
from ..utils.geometry import query_zoos_with_distance
from ..utils.http import set_personalized_cache_headers

router = APIRouter()


GENERIC_SIGNUP_MESSAGE = (
    "If the address can be used, you'll receive an email shortly."
)


def ensure_same_user(user_id: uuid.UUID, current_user: models.User) -> None:
    """Ensure the path user_id matches the authenticated user."""
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot access this resource for another user",
        )


def _visited_zoo_ids_subquery(db: Session, user_id: uuid.UUID) -> Subquery:
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
    query: SAQuery[models.Zoo],
    latitude: float | None,
    longitude: float | None,
    limit: int,
    offset: int,
    favorite_ids: set[uuid.UUID] | None = None,
) -> schemas.ZooSearchPage:
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


def _serialize_map_points(zoos: list[models.Zoo]) -> list[schemas.ZooMapPoint]:
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

@router.post(
    "/users",
    response_model=schemas.Message,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(require_json)],
)
def create_user(
    user_in: schemas.UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> schemas.Message:
    """Register a new user with a hashed password."""
    existing_user = get_user(db, user_in.email)
    if existing_user:
        enqueue_existing_signup_notice(background_tasks, existing_user)
        return schemas.Message(detail=GENERIC_SIGNUP_MESSAGE)
    hashed = hash_password(user_in.password)
    consent_at = datetime.now(timezone.utc)
    anonymized_ip = getattr(request.state, "client_ip_anonymized", None)
    raw_ip = getattr(request.state, "client_ip", None)
    if anonymized_ip is None:
        client_host = raw_ip
        if client_host is None and request.client is not None:
            client_host = request.client.host
        anonymized_ip = anonymize_ip(client_host, mode="anonymized")
    user = models.User(
        name=user_in.name,
        email=user_in.email,
        password_hash=hashed,
        privacy_consent_version=user_in.privacy_consent_version,
        privacy_consent_at=consent_at,
        privacy_consent_ip=anonymized_ip,
    )
    db.add(user)
    token, code, _ = issue_verification_token(db, user)
    db.flush()
    enqueue_verification_email(background_tasks, user, token=token, code=code)
    db.commit()
    return schemas.Message(detail=GENERIC_SIGNUP_MESSAGE)


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
    limit: Annotated[int, Query(ge=1, le=10000)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    coords: tuple[float | None, float | None] = Depends(resolve_coords),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ZooSearchPage:
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
    set_personalized_cache_headers(response)
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
    limit: Annotated[int, Query(ge=1, le=10000)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    coords: tuple[float | None, float | None] = Depends(resolve_coords),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.ZooSearchPage:
    """Return zoos the authenticated user has not yet visited."""

    ensure_same_user(user_id, current_user)
    validate_region_filters(db, continent_id, country_id)

    visited_ids = _visited_zoo_ids_subquery(db, user_id)
    query = db.query(models.Zoo).options(joinedload(models.Zoo.country))
    query = query.filter(~models.Zoo.id.in_(select(visited_ids.c.zoo_id)))
    query = apply_zoo_filters(query, q, continent_id, country_id)

    latitude, longitude = coords
    set_personalized_cache_headers(response)
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
) -> list[schemas.ZooMapPoint]:
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
    set_personalized_cache_headers(response)
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
) -> list[schemas.ZooMapPoint]:
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
    set_personalized_cache_headers(response)
    return _serialize_map_points(zoos)

@router.get("/users/{user_id}/animals", response_model=list[schemas.AnimalRead])
def list_seen_animals(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[models.Animal]:
    """Return all unique animals seen by the specified user."""
    ensure_same_user(user_id, user)
    animals = (
        db.query(models.Animal)
        .join(models.AnimalSighting, models.Animal.id == models.AnimalSighting.animal_id)
        .filter(models.AnimalSighting.user_id == user_id)
        .distinct()
        .all()
    )
    return cast(list[models.Animal], animals)


@router.get("/users/{user_id}/animals/ids", response_model=list[uuid.UUID])
def list_seen_animal_ids(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> list[uuid.UUID]:
    """Return IDs of unique animals seen by the specified user."""
    ensure_same_user(user_id, user)
    raw_ids = (
        db.query(models.AnimalSighting.animal_id)
        .filter(models.AnimalSighting.user_id == user_id)
        .distinct()
        .all()
    )
    rows = cast(list[tuple[uuid.UUID]], raw_ids)
    return [row[0] for row in rows]


@router.get("/users/{user_id}/animals/count", response_model=schemas.Count)
def count_seen_animals(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.Count:
    """Return the number of unique animals seen by the specified user."""
    ensure_same_user(user_id, user)
    count_value = (
        db.query(func.count(func.distinct(models.AnimalSighting.animal_id)))
        .filter(models.AnimalSighting.user_id == user_id)
        .scalar()
    )
    total = cast(int | None, count_value) or 0
    return schemas.Count(count=total)
