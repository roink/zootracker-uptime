from typing import Annotated, cast

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import exists, text
from sqlalchemy.orm import Session, joinedload, load_only

from .. import models, schemas
from ..auth import get_current_user, get_optional_user
from ..database import get_db
from ..utils.geometry import query_zoos_with_distance
from ..utils.http import set_personalized_cache_headers
from .common_filters import apply_zoo_filters, validate_region_filters
from .common_sightings import apply_recent_first_order, build_user_sightings_query
from .deps import resolve_coords

router = APIRouter()

_coords_dependency = Depends(resolve_coords)
_db_dependency = Depends(get_db)
_optional_user_dependency = Depends(get_optional_user)
_current_user_dependency = Depends(get_current_user)


@router.get("/zoos", response_model=schemas.ZooSearchPage)
def search_zoos(
    response: Response,
    q: str = "",
    continent_id: int | None = None,
    country_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=10000)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    coords: tuple[float | None, float | None] = _coords_dependency,
    db: Session = _db_dependency,
    user: models.User | None = _optional_user_dependency,
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
    db: Session = _db_dependency,
    user: models.User | None = _optional_user_dependency,
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
def list_continents(db: Session = _db_dependency) -> list[schemas.TaxonName]:
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
    continent_id: int, db: Session = _db_dependency
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
    db: Session = _db_dependency,
    user: models.User | None = _optional_user_dependency,
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
        zoo.is_favorite = is_favorite
    return zoo


@router.put(
    "/zoos/{zoo_slug}/favorite",
    response_model=schemas.FavoriteStatus,
    status_code=status.HTTP_200_OK,
)
def mark_zoo_favorite(
    zoo_slug: str,
    db: Session = _db_dependency,
    user: models.User = _current_user_dependency,
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
    db: Session = _db_dependency,
    user: models.User = _current_user_dependency,
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
    db: Session = _db_dependency,
    user: models.User = _current_user_dependency,
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
    db: Session = _db_dependency,
    user: models.User = _current_user_dependency,
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


@router.get("/zoos/{zoo_slug}/animals", response_model=schemas.ZooAnimalListing)
def list_zoo_animals(
    response: Response,
    zoo_slug: str,
    q: str | None = None,
    class_id: int | None = Query(None, alias="class"),
    order_id: int | None = Query(None, alias="order"),
    family_id: int | None = Query(None, alias="family"),
    seen: bool | None = None,
    favorites: bool | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = _db_dependency,
    user: models.User | None = _optional_user_dependency,
) -> schemas.ZooAnimalListing:
    """Return animals that are associated with a specific zoo."""

    zoo = _get_zoo_or_404(zoo_slug, db)

    # Anonymous users get cacheable responses
    if user is None:
        response.headers["Cache-Control"] = "public, max-age=3600"
    else:
        set_personalized_cache_headers(response)

    search_text = (q or "").strip().lower()
    require_seen = seen if seen is not None else False
    require_favorites = favorites if favorites is not None else False

    # Require authentication for personalized filters
    if require_favorites and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to filter favorites",
        )
    if require_seen and user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required to filter seen animals",
        )

    # Build base query for animals at this zoo
    base_query = (
        db.query(models.Animal)
        .join(models.ZooAnimal, models.Animal.id == models.ZooAnimal.animal_id)
        .filter(models.ZooAnimal.zoo_id == zoo.id)
    )

    # Apply taxonomy filters
    if class_id is not None:
        base_query = base_query.filter(models.Animal.klasse == class_id)
    if order_id is not None:
        base_query = base_query.filter(models.Animal.ordnung == order_id)
    if family_id is not None:
        base_query = base_query.filter(models.Animal.familie == family_id)

    # Apply text search
    if search_text:
        search_pattern = f"%{search_text}%"
        base_query = base_query.filter(
            (models.Animal.name_en.ilike(search_pattern))
            | (models.Animal.name_de.ilike(search_pattern))
            | (models.Animal.scientific_name.ilike(search_pattern))
            | (models.Animal.slug.ilike(search_pattern))
        )

    # Apply personalized filters
    favorite_ids: set = set()
    seen_ids: set = set()
    if user is not None:
        favorite_ids = {
            row[0]
            for row in (
                db.query(models.UserFavoriteAnimal.animal_id)
                .filter(models.UserFavoriteAnimal.user_id == user.id)
                .all()
            )
        }
        seen_ids = {
            row[0]
            for row in (
                db.query(models.AnimalSighting.animal_id)
                .filter(models.AnimalSighting.user_id == user.id)
                .distinct()
                .all()
            )
        }

        if require_favorites:
            base_query = base_query.filter(models.Animal.id.in_(favorite_ids))
        if require_seen:
            base_query = base_query.filter(models.Animal.id.in_(seen_ids))

    # Get total count before pagination
    total = base_query.order_by(None).count()

    # Apply ordering and pagination
    filtered_query = (
        base_query.options(
            joinedload(models.Animal.klasse_name),
            joinedload(models.Animal.ordnung_name),
            joinedload(models.Animal.familie_name),
        )
        .order_by(
            models.Animal.zoo_count.desc(),
            models.Animal.name_en.asc(),
            models.Animal.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    )

    animals = filtered_query.all()

    # Compute facets based on all animals at the zoo (respecting search/personal filters)
    facet_query = (
        db.query(models.Animal)
        .join(models.ZooAnimal, models.Animal.id == models.ZooAnimal.animal_id)
        .filter(models.ZooAnimal.zoo_id == zoo.id)
        .options(
            joinedload(models.Animal.klasse_name),
            joinedload(models.Animal.ordnung_name),
            joinedload(models.Animal.familie_name),
        )
    )

    # Apply text search to facets
    if search_text:
        search_pattern = f"%{search_text}%"
        facet_query = facet_query.filter(
            (models.Animal.name_en.ilike(search_pattern))
            | (models.Animal.name_de.ilike(search_pattern))
            | (models.Animal.scientific_name.ilike(search_pattern))
            | (models.Animal.slug.ilike(search_pattern))
        )

    # Apply personalized filters to facets
    if user is not None:
        if require_favorites:
            facet_query = facet_query.filter(models.Animal.id.in_(favorite_ids))
        if require_seen:
            facet_query = facet_query.filter(models.Animal.id.in_(seen_ids))

    facet_animals = facet_query.all()

    class_labels: dict[int, tuple[str | None, str | None]] = {}
    order_labels: dict[int, tuple[str | None, str | None]] = {}
    family_labels: dict[int, tuple[str | None, str | None]] = {}
    class_counts: dict[int, int] = {}
    order_counts: dict[int, int] = {}
    family_counts: dict[int, int] = {}

    for animal in facet_animals:
        # Collect labels
        if animal.klasse is not None:
            class_labels[animal.klasse] = (
                getattr(animal.klasse_name, "name_de", None),
                getattr(animal.klasse_name, "name_en", None),
            )
        if animal.ordnung is not None:
            order_labels[animal.ordnung] = (
                getattr(animal.ordnung_name, "name_de", None),
                getattr(animal.ordnung_name, "name_en", None),
            )
        if animal.familie is not None:
            family_labels[animal.familie] = (
                getattr(animal.familie_name, "name_de", None),
                getattr(animal.familie_name, "name_en", None),
            )

        # Count for class facets (exclude selected orders and families)
        if (
            animal.klasse is not None
            and (order_id is None or animal.ordnung == order_id)
            and (family_id is None or animal.familie == family_id)
        ):
            class_counts[animal.klasse] = class_counts.get(animal.klasse, 0) + 1

        # Count for order facets (exclude selected families)
        if (
            animal.ordnung is not None
            and (class_id is None or animal.klasse == class_id)
            and (family_id is None or animal.familie == family_id)
        ):
            order_counts[animal.ordnung] = order_counts.get(animal.ordnung, 0) + 1

        # Count for family facets
        if (
            animal.familie is not None
            and (class_id is None or animal.klasse == class_id)
            and (order_id is None or animal.ordnung == order_id)
        ):
            family_counts[animal.familie] = family_counts.get(animal.familie, 0) + 1

    def _sort_key(
        labels: dict[int, tuple[str | None, str | None]],
        identifier: int,
    ) -> tuple[str, int]:
        name_en = labels.get(identifier, (None, None))[1] or ""
        return (name_en.lower(), identifier)

    class_facets = [
        schemas.ZooAnimalFacetOption(
            id=klass,
            name_de=class_labels.get(klass, (None, None))[0],
            name_en=class_labels.get(klass, (None, None))[1],
            count=count,
        )
        for klass, count in sorted(
            class_counts.items(), key=lambda item: _sort_key(class_labels, item[0])
        )
    ]
    order_facets = [
        schemas.ZooAnimalFacetOption(
            id=ordnung,
            name_de=order_labels.get(ordnung, (None, None))[0],
            name_en=order_labels.get(ordnung, (None, None))[1],
            count=count,
        )
        for ordnung, count in sorted(
            order_counts.items(), key=lambda item: _sort_key(order_labels, item[0])
        )
    ]
    family_facets = [
        schemas.ZooAnimalFacetOption(
            id=familie,
            name_de=family_labels.get(familie, (None, None))[0],
            name_en=family_labels.get(familie, (None, None))[1],
            count=count,
        )
        for familie, count in sorted(
            family_counts.items(), key=lambda item: _sort_key(family_labels, item[0])
        )
    ]

    def _serialize(animal: models.Animal) -> schemas.ZooAnimalListItem:
        return schemas.ZooAnimalListItem(
            id=animal.id,
            slug=animal.slug,
            name_en=animal.name_en,
            scientific_name=animal.scientific_name,
            name_de=animal.name_de,
            zoo_count=animal.zoo_count or 0,
            is_favorite=animal.id in favorite_ids,
            default_image_url=animal.default_image_url,
            seen=animal.id in seen_ids,
            klasse=animal.klasse,
            ordnung=animal.ordnung,
            familie=animal.familie,
        )

    items = [_serialize(animal) for animal in animals]

    response.headers["X-Total-Count"] = str(total)

    return schemas.ZooAnimalListing(
        items=items,
        total=total,
        available_total=total,
        inventory=[],
        facets=schemas.ZooAnimalFacets(
            classes=class_facets,
            orders=order_facets,
            families=family_facets,
        ),
    )
