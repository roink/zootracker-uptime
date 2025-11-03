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
    class_filters: list[int] = Query(default_factory=list, alias="class"),
    order_filters: list[int] = Query(default_factory=list, alias="order"),
    family_filters: list[int] = Query(default_factory=list, alias="family"),
    seen: str | None = None,
    favorites: str | None = None,
    db: Session = _db_dependency,
    user: models.User | None = _optional_user_dependency,
) -> schemas.ZooAnimalListing:
    """Return animals that are associated with a specific zoo."""

    set_personalized_cache_headers(response)

    zoo = _get_zoo_or_404(zoo_slug, db)

    search_text = (q or "").strip().lower()
    selected_classes = {value for value in class_filters if value is not None}
    selected_orders = {value for value in order_filters if value is not None}
    selected_families = {value for value in family_filters if value is not None}

    def _as_bool(value: str | None) -> bool:
        if value is None:
            return False
        lowered = value.strip().lower()
        return lowered in {"1", "true", "yes", "on"}

    require_seen = _as_bool(seen)
    require_favorites = _as_bool(favorites)

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

    animals_query = (
        db.query(models.Animal)
        .join(models.ZooAnimal, models.Animal.id == models.ZooAnimal.animal_id)
        .filter(models.ZooAnimal.zoo_id == zoo.id)
        .options(
            joinedload(models.Animal.klasse_name),
            joinedload(models.Animal.ordnung_name),
            joinedload(models.Animal.familie_name),
        )
        .order_by(
            models.Animal.zoo_count.desc(),
            models.Animal.name_en.asc(),
            models.Animal.id.asc(),
        )
    )
    animals = animals_query.all()

    def _matches_search(animal: models.Animal) -> bool:
        if not search_text:
            return True
        candidates = (
            animal.name_en,
            animal.name_de,
            animal.scientific_name,
            animal.slug,
        )
        for candidate in candidates:
            if candidate and search_text in candidate.lower():
                return True
        return False

    def _matches_filters(animal: models.Animal) -> bool:
        if require_favorites and animal.id not in favorite_ids:
            return False
        if require_seen and animal.id not in seen_ids:
            return False
        if selected_classes and (animal.klasse not in selected_classes):
            return False
        if selected_orders and (animal.ordnung not in selected_orders):
            return False
        if selected_families and (animal.familie not in selected_families):
            return False
        return _matches_search(animal)

    def _passes_common_filters(animal: models.Animal) -> bool:
        if require_favorites and animal.id not in favorite_ids:
            return False
        if require_seen and animal.id not in seen_ids:
            return False
        return _matches_search(animal)

    filtered_animals = [animal for animal in animals if _matches_filters(animal)]

    def _collect_labels(animal: models.Animal) -> tuple[
        dict[int, tuple[str | None, str | None]],
        dict[int, tuple[str | None, str | None]],
        dict[int, tuple[str | None, str | None]],
    ]:
        return (
            {
                animal.klasse: (
                    getattr(animal.klasse_name, "name_de", None),
                    getattr(animal.klasse_name, "name_en", None),
                )
                for _ in [None]
                if animal.klasse is not None
            },
            {
                animal.ordnung: (
                    getattr(animal.ordnung_name, "name_de", None),
                    getattr(animal.ordnung_name, "name_en", None),
                )
                for _ in [None]
                if animal.ordnung is not None
            },
            {
                animal.familie: (
                    getattr(animal.familie_name, "name_de", None),
                    getattr(animal.familie_name, "name_en", None),
                )
                for _ in [None]
                if animal.familie is not None
            },
        )

    class_labels: dict[int, tuple[str | None, str | None]] = {}
    order_labels: dict[int, tuple[str | None, str | None]] = {}
    family_labels: dict[int, tuple[str | None, str | None]] = {}
    class_counts: dict[int, int] = {}
    order_counts: dict[int, int] = {}
    family_counts: dict[int, int] = {}

    for animal in animals:
        cls_label, ord_label, fam_label = _collect_labels(animal)
        class_labels.update(cls_label)
        order_labels.update(ord_label)
        family_labels.update(fam_label)

        if (
            _passes_common_filters(animal)
            and (not selected_orders or animal.ordnung in selected_orders)
            and (not selected_families or animal.familie in selected_families)
            and animal.klasse is not None
        ):
            class_counts[animal.klasse] = class_counts.get(animal.klasse, 0) + 1

        if (
            _passes_common_filters(animal)
            and (not selected_classes or animal.klasse in selected_classes)
            and (not selected_families or animal.familie in selected_families)
            and animal.ordnung is not None
        ):
            order_counts[animal.ordnung] = order_counts.get(animal.ordnung, 0) + 1

        if (
            _passes_common_filters(animal)
            and (not selected_classes or animal.klasse in selected_classes)
            and (not selected_orders or animal.ordnung in selected_orders)
            and animal.familie is not None
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

    inventory_items = [_serialize(animal) for animal in animals]
    filtered_items = [_serialize(animal) for animal in filtered_animals]

    return schemas.ZooAnimalListing(
        items=filtered_items,
        total=len(filtered_items),
        available_total=len(inventory_items),
        inventory=inventory_items,
        facets=schemas.ZooAnimalFacets(
            classes=class_facets,
            orders=order_facets,
            families=family_facets,
        ),
    )
