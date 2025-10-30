from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import exists, text
from sqlalchemy.orm import Session, joinedload, load_only

from .. import schemas, models
from ..database import get_db
from ..utils.geometry import query_zoos_with_distance
from ..utils.http import set_personalized_cache_headers
from ..auth import get_current_user, get_optional_user
from .deps import resolve_coords
from .common_filters import apply_zoo_filters, validate_region_filters
from .common_sightings import apply_recent_first_order, build_user_sightings_query

router = APIRouter()


@router.get("/zoos", response_model=schemas.ZooSearchPage)
def search_zoos(
    response: Response,
    q: str = "",
    continent_id: int | None = None,
    country_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=10000)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    coords: tuple[float | None, float | None] = Depends(resolve_coords),
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
    favorites_only: bool = False,
) -> schemas.ZooSearchPage:
    """Search for zoos by name, region and optional distance."""

    set_personalized_cache_headers(response)

    validate_region_filters(db, continent_id, country_id)

    query = db.query(models.Zoo).options(joinedload(models.Zoo.country))
    query = apply_zoo_filters(query, q, continent_id, country_id)

    if favorites_only:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to filter favorites",
            )
        query = query.join(
            models.UserFavoriteZoo,
            models.UserFavoriteZoo.zoo_id == models.Zoo.id,
        ).filter(models.UserFavoriteZoo.user_id == user.id)

    total = query.order_by(None).count()
    latitude, longitude = coords

    items: list[schemas.ZooSearchResult] = []
    favorite_ids: set = set()
    if user is not None:
        favorite_ids = {
            row[0]
            for row in (
                db.query(models.UserFavoriteZoo.zoo_id)
                .filter(models.UserFavoriteZoo.user_id == user.id)
                .all()
            )
        }
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
                distance_km=dist,
                country_name_en=z.country.name_en if z.country else None,
                country_name_de=z.country.name_de if z.country else None,
                is_favorite=z.id in favorite_ids,
            )
            for z, dist in results
        ]

    return schemas.ZooSearchPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/zoos/map", response_model=list[schemas.ZooMapPoint])
def list_zoos_for_map(
    response: Response,
    q: str = "",
    continent_id: int | None = None,
    country_id: int | None = None,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
    favorites_only: bool = False,
) -> list[schemas.ZooMapPoint]:
    """Return minimal data for plotting zoos on the world map."""

    set_personalized_cache_headers(response)

    validate_region_filters(db, continent_id, country_id)

    query = db.query(models.Zoo).options(
        load_only(
            models.Zoo.id,
            models.Zoo.slug,
            models.Zoo.name,
            models.Zoo.city,
            models.Zoo.latitude,
            models.Zoo.longitude,
        )
    )
    query = apply_zoo_filters(query, q, continent_id, country_id)

    if favorites_only:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to filter favorites",
            )
        query = query.join(
            models.UserFavoriteZoo,
            models.UserFavoriteZoo.zoo_id == models.Zoo.id,
        ).filter(models.UserFavoriteZoo.user_id == user.id)

    zoos = query.order_by(models.Zoo.name).all()
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


@router.get("/zoos/continents", response_model=list[schemas.TaxonName])
def list_continents(db: Session = Depends(get_db)) -> list[schemas.TaxonName]:
    """Return continents that have zoos."""

    continents = (
        db.query(models.ContinentName)
        .join(models.Zoo, models.Zoo.continent_id == models.ContinentName.id)
        .distinct()
        .order_by(models.ContinentName.name_en)
        .all()
    )
    return [
        schemas.TaxonName(id=c.id, name_de=c.name_de, name_en=c.name_en)
        for c in continents
    ]


@router.get("/zoos/countries", response_model=list[schemas.TaxonName])
def list_countries(
    continent_id: int, db: Session = Depends(get_db)
) -> list[schemas.TaxonName]:
    """Return countries for a given continent that have zoos."""

    countries = (
        db.query(models.CountryName)
        .join(models.Zoo, models.Zoo.country_id == models.CountryName.id)
        .filter(models.CountryName.continent_id == continent_id)
        .distinct()
        .order_by(models.CountryName.name_en)
        .all()
    )
    return [
        schemas.TaxonName(id=c.id, name_de=c.name_de, name_en=c.name_en)
        for c in countries
    ]


def _get_zoo_or_404(zoo_slug: str, db: Session) -> models.Zoo:
    """Return a zoo by slug or raise a 404 error."""

    result = db.query(models.Zoo).filter(models.Zoo.slug == zoo_slug).first()
    zoo = cast(models.Zoo | None, result)
    if zoo is None:
        raise HTTPException(status_code=404, detail="Zoo not found")
    return zoo


@router.get("/zoos/{zoo_slug}", response_model=schemas.ZooDetail)
def get_zoo(
    response: Response,
    zoo_slug: str,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
) -> models.Zoo:
    """Retrieve detailed information about a zoo."""

    set_personalized_cache_headers(response)

    zoo = _get_zoo_or_404(zoo_slug, db)
    if user is not None:
        is_favorite = (
            db.query(models.UserFavoriteZoo)
            .filter(
                models.UserFavoriteZoo.user_id == user.id,
                models.UserFavoriteZoo.zoo_id == zoo.id,
            )
            .first()
            is not None
        )
        setattr(zoo, "is_favorite", is_favorite)
    return zoo


@router.put(
    "/zoos/{zoo_slug}/favorite",
    response_model=schemas.FavoriteStatus,
    status_code=status.HTTP_200_OK,
)
def mark_zoo_favorite(
    zoo_slug: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.FavoriteStatus:
    """Mark a zoo as a favorite for the authenticated user."""

    zoo = _get_zoo_or_404(zoo_slug, db)
    db.execute(
        text(
            """
            INSERT INTO user_favorite_zoos (user_id, zoo_id)
            VALUES (:user_id, :zoo_id)
            ON CONFLICT DO NOTHING
            """
        ),
        {"user_id": user.id, "zoo_id": zoo.id},
    )
    db.commit()
    return schemas.FavoriteStatus(favorite=True)


@router.delete(
    "/zoos/{zoo_slug}/favorite",
    response_model=schemas.FavoriteStatus,
    status_code=status.HTTP_200_OK,
)
def unmark_zoo_favorite(
    zoo_slug: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.FavoriteStatus:
    """Remove a zoo from the authenticated user's favorites."""

    zoo = _get_zoo_or_404(zoo_slug, db)
    (
        db.query(models.UserFavoriteZoo)
        .filter(
            models.UserFavoriteZoo.user_id == user.id,
            models.UserFavoriteZoo.zoo_id == zoo.id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return schemas.FavoriteStatus(favorite=False)


@router.get("/zoos/{zoo_slug}/visited", response_model=schemas.Visited)
def has_visited_zoo(
    zoo_slug: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.Visited:
    """Return whether the authenticated user has visited a given zoo."""

    zoo = _get_zoo_or_404(zoo_slug, db)
    visited = db.query(
        exists().where(
            models.ZooVisit.user_id == user.id,
            models.ZooVisit.zoo_id == zoo.id,
        )
    ).scalar()
    if not visited:
        visited = db.query(
            exists().where(
                models.AnimalSighting.user_id == user.id,
                models.AnimalSighting.zoo_id == zoo.id,
            )
        ).scalar()
    return schemas.Visited(visited=bool(visited))


@router.get(
    "/zoos/{zoo_slug}/sightings",
    response_model=schemas.AnimalSightingPage,
)
def list_zoo_sightings(
    response: Response,
    zoo_slug: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> schemas.AnimalSightingPage:
    """Return the authenticated user's sightings for a specific zoo."""

    zoo = _get_zoo_or_404(zoo_slug, db)
    set_personalized_cache_headers(response)

    query = build_user_sightings_query(db, user.id).filter(
        models.AnimalSighting.zoo_id == zoo.id
    )

    total = query.order_by(None).count()
    items = apply_recent_first_order(query).limit(limit).offset(offset).all()

    response.headers["X-Total-Count"] = str(total)

    return schemas.AnimalSightingPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/zoos/{zoo_slug}/animals", response_model=list[schemas.AnimalRead])
def list_zoo_animals(
    response: Response,
    zoo_slug: str,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
) -> list[schemas.AnimalRead]:
    """Return animals that are associated with a specific zoo."""

    set_personalized_cache_headers(response)

    zoo = _get_zoo_or_404(zoo_slug, db)
    favorites: set = set()
    if user is not None:
        favorites = {
            row[0]
            for row in (
                db.query(models.UserFavoriteAnimal.animal_id)
                .filter(models.UserFavoriteAnimal.user_id == user.id)
                .all()
            )
        }
    animals = (
        db.query(models.Animal)
        .join(models.ZooAnimal, models.Animal.id == models.ZooAnimal.animal_id)
        .filter(models.ZooAnimal.zoo_id == zoo.id)
        .order_by(models.Animal.zoo_count.desc())
        .all()
    )
    return [
        schemas.AnimalRead(
            id=a.id,
            slug=a.slug,
            name_en=a.name_en,
            scientific_name=a.scientific_name,
            name_de=a.name_de,
            zoo_count=a.zoo_count,
            is_favorite=a.id in favorites,
            default_image_url=a.default_image_url,
        )
        for a in animals
    ]
