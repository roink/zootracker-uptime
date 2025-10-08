import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, text
from sqlalchemy.orm import Session, joinedload, load_only

from .. import schemas, models
from ..database import get_db
from ..auth import get_current_user, get_optional_user
from ..utils.geometry import query_zoos_with_distance
from ..utils.images import build_unique_variants
from ..utils.http import set_personalized_cache_headers
from .deps import resolve_coords
from .common_sightings import (
    apply_recent_first_order,
    build_user_sightings_query,
    count_query_rows,
)


def to_zoodetail(
    z: models.Zoo, dist: float | None, *, is_favorite: bool = False
) -> schemas.ZooDetail:
    return schemas.ZooDetail(
        id=z.id,
        slug=z.slug,
        name=z.name,
        address=z.address,
        city=z.city,
        latitude=float(z.latitude) if z.latitude is not None else None,
        longitude=float(z.longitude) if z.longitude is not None else None,
        description_de=z.description_de,
        description_en=z.description_en,
        distance_km=dist,
        is_favorite=is_favorite,
    )


router = APIRouter()


def _get_animal_or_404(animal_slug: str, db: Session) -> models.Animal:
    """Return an animal by slug or raise a 404 error."""

    animal = (
        db.query(models.Animal)
        .options(load_only(models.Animal.id, models.Animal.slug))
        .filter(models.Animal.slug == animal_slug)
        .first()
    )
    if animal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found"
        )
    return animal


@router.get("/animals", response_model=list[schemas.AnimalListItem])
def list_animals(
    response: Response,
    q: str = "",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    category: str | None = None,
    class_id: int | None = None,
    order_id: int | None = None,
    family_id: int | None = None,
    favorites_only: bool = False,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
):
    """List animals filtered by search query, taxonomy and pagination."""

    set_personalized_cache_headers(response)

    # Ensure hierarchical taxonomy parameters are consistent
    if class_id is not None and order_id is not None:
        exists = (
            db.query(models.Animal)
            .filter(models.Animal.klasse == class_id, models.Animal.ordnung == order_id)
            .first()
        )
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="order_id does not belong to class_id",
            )
    if order_id is not None and family_id is not None:
        exists = (
            db.query(models.Animal)
            .filter(
                models.Animal.ordnung == order_id, models.Animal.familie == family_id
            )
            .first()
        )
        if not exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="family_id does not belong to order_id",
            )

    query = (
        db.query(models.Animal)
        .join(models.Category, isouter=True)
        .options(joinedload(models.Animal.category))
    )

    if favorites_only:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to filter favorites",
            )
        query = query.join(
            models.UserFavoriteAnimal,
            models.UserFavoriteAnimal.animal_id == models.Animal.id,
        ).filter(models.UserFavoriteAnimal.user_id == user.id)

    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                models.Animal.name_en.ilike(pattern),
                models.Animal.name_de.ilike(pattern),
            )
        )

    if category:
        query = query.filter(models.Category.name == category)
    if class_id is not None:
        query = query.filter(models.Animal.klasse == class_id)
    if order_id is not None:
        query = query.filter(models.Animal.ordnung == order_id)
    if family_id is not None:
        query = query.filter(models.Animal.familie == family_id)

    animals = (
        query.order_by(
            models.Animal.zoo_count.desc(),
            models.Animal.name_en.asc(),
            models.Animal.id.asc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )

    favorite_ids: set = set()
    if user is not None:
        favorite_ids = {
            row[0]
            for row in (
                db.query(models.UserFavoriteAnimal.animal_id)
                .filter(models.UserFavoriteAnimal.user_id == user.id)
                .all()
            )
        }

    return [
        schemas.AnimalListItem(
            id=a.id,
            slug=a.slug,
            name_en=a.name_en,
            scientific_name=a.scientific_name,
            name_de=a.name_de,
            category=a.category.name if a.category else None,
            description_de=a.description_de,
            iucn_conservation_status=a.conservation_state,
            default_image_url=a.default_image_url,
            zoo_count=a.zoo_count,
            is_favorite=a.id in favorite_ids,
        )
        for a in animals
    ]


@router.get("/animals/classes", response_model=list[schemas.TaxonName])
def list_classes(db: Session = Depends(get_db)):
    """Return all available classes that have animals."""

    classes = (
        db.query(models.ClassName)
        .join(models.Animal, models.Animal.klasse == models.ClassName.klasse)
        .distinct()
        .order_by(models.ClassName.name_en)
        .all()
    )
    return [
        schemas.TaxonName(id=c.klasse, name_de=c.name_de, name_en=c.name_en)
        for c in classes
    ]


@router.get("/animals/orders", response_model=list[schemas.TaxonName])
def list_orders(class_id: int, db: Session = Depends(get_db)):
    """Return orders available for a given class."""

    orders = (
        db.query(models.OrderName)
        .join(models.Animal, models.Animal.ordnung == models.OrderName.ordnung)
        .filter(models.Animal.klasse == class_id)
        .distinct()
        .order_by(models.OrderName.name_en)
        .all()
    )
    return [
        schemas.TaxonName(id=o.ordnung, name_de=o.name_de, name_en=o.name_en)
        for o in orders
    ]


@router.get("/animals/families", response_model=list[schemas.TaxonName])
def list_families(order_id: int, db: Session = Depends(get_db)):
    """Return families available for a given order."""

    families = (
        db.query(models.FamilyName)
        .join(models.Animal, models.Animal.familie == models.FamilyName.familie)
        .filter(models.Animal.ordnung == order_id)
        .distinct()
        .order_by(models.FamilyName.name_en)
        .all()
    )
    return [
        schemas.TaxonName(id=f.familie, name_de=f.name_de, name_en=f.name_en)
        for f in families
    ]


@router.get("/search", response_model=schemas.SearchResults)
def combined_search(
    response: Response,
    q: str = "",
    limit: int = 5,
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
):
    """Return top zoos and animals matching the query."""

    set_personalized_cache_headers(response)
    zoo_q = db.query(models.Zoo).options(
        load_only(models.Zoo.id, models.Zoo.slug, models.Zoo.name, models.Zoo.city)
    )
    if q:
        pattern = f"%{q}%"
        zoo_q = zoo_q.filter(
            or_(models.Zoo.name.ilike(pattern), models.Zoo.city.ilike(pattern))
        )
    zoos = zoo_q.limit(limit).all()

    animal_q = db.query(models.Animal)
    if q:
        pattern = f"%{q}%"
        animal_q = animal_q.filter(
            or_(
                models.Animal.name_en.ilike(pattern),
                models.Animal.name_de.ilike(pattern),
            )
        )
    animals = animal_q.limit(limit).all()

    if user is not None:
        favorite_zoo_ids = {
            row[0]
            for row in (
                db.query(models.UserFavoriteZoo.zoo_id)
                .filter(models.UserFavoriteZoo.user_id == user.id)
                .all()
            )
        }
        favorite_animal_ids = {
            row[0]
            for row in (
                db.query(models.UserFavoriteAnimal.animal_id)
                .filter(models.UserFavoriteAnimal.user_id == user.id)
                .all()
            )
        }
        for zoo in zoos:
            setattr(zoo, "is_favorite", zoo.id in favorite_zoo_ids)
        for animal in animals:
            setattr(animal, "is_favorite", animal.id in favorite_animal_ids)

    return {"zoos": zoos, "animals": animals}


@router.put(
    "/animals/{animal_slug}/favorite",
    response_model=schemas.FavoriteStatus,
    status_code=status.HTTP_200_OK,
)
def mark_animal_favorite(
    animal_slug: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Mark an animal as a favorite for the authenticated user."""

    animal = _get_animal_or_404(animal_slug, db)
    db.execute(
        text(
            """
            INSERT INTO user_favorite_animals (user_id, animal_id)
            VALUES (:user_id, :animal_id)
            ON CONFLICT DO NOTHING
            """
        ),
        {"user_id": user.id, "animal_id": animal.id},
    )
    db.commit()
    return schemas.FavoriteStatus(favorite=True)


@router.delete(
    "/animals/{animal_slug}/favorite",
    response_model=schemas.FavoriteStatus,
    status_code=status.HTTP_200_OK,
)
def unmark_animal_favorite(
    animal_slug: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Remove an animal from the authenticated user's favorites."""

    animal = _get_animal_or_404(animal_slug, db)
    (
        db.query(models.UserFavoriteAnimal)
        .filter(
            models.UserFavoriteAnimal.user_id == user.id,
            models.UserFavoriteAnimal.animal_id == animal.id,
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return schemas.FavoriteStatus(favorite=False)


@router.get("/animals/{animal_slug}", response_model=schemas.AnimalDetail)
def get_animal_detail(
    response: Response,
    animal_slug: str,
    coords: tuple[float | None, float | None] = Depends(resolve_coords),
    db: Session = Depends(get_db),
    user: models.User | None = Depends(get_optional_user),
):
    """Retrieve a single animal and the zoos where it can be found.

    When ``latitude`` and ``longitude`` are supplied the zoos are ordered by
    distance and include a ``distance_km`` field so the frontend only needs a
    single request.
    """
    set_personalized_cache_headers(response)
    animal = (
        db.query(models.Animal)
        .options(
            joinedload(models.Animal.images).joinedload(models.Image.variants),
            joinedload(models.Animal.category),
            joinedload(models.Animal.klasse_name),
            joinedload(models.Animal.ordnung_name),
            joinedload(models.Animal.familie_name),
        )
        .filter(models.Animal.slug == animal_slug)
        .first()
    )
    if animal is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found"
        )

    animal_id = animal.id
    is_favorite = False
    if user is not None:
        is_favorite = (
            db.query(models.UserFavoriteAnimal)
            .filter(
                models.UserFavoriteAnimal.user_id == user.id,
                models.UserFavoriteAnimal.animal_id == animal_id,
            )
            .first()
            is not None
        )
    latitude, longitude = coords

    target_animal_ids: set[uuid.UUID] = {animal_id}

    subspecies: list[schemas.AnimalRelation] = []
    child_ids: list[uuid.UUID] = []
    if animal.art is not None:
        children = (
            db.query(models.Animal)
            .options(
                load_only(
                    models.Animal.id,
                    models.Animal.slug,
                    models.Animal.name_en,
                    models.Animal.name_de,
                    models.Animal.scientific_name,
                )
            )
            .filter(models.Animal.parent_art == animal.art)
            .order_by(models.Animal.name_en.asc(), models.Animal.id.asc())
            .all()
        )
        subspecies = [
            schemas.AnimalRelation(
                slug=child.slug,
                name_en=child.name_en,
                name_de=child.name_de,
                scientific_name=child.scientific_name,
            )
            for child in children
        ]
        child_ids = [child.id for child in children]

    if animal.parent_art is None and child_ids:
        target_animal_ids.update(child_ids)

    target_animal_ids_list = list(target_animal_ids)

    zoo_ids_subquery = (
        db.query(models.ZooAnimal.zoo_id)
        .filter(models.ZooAnimal.animal_id.in_(target_animal_ids_list))
        .distinct()
        .subquery()
    )

    query = (
        db.query(models.Zoo)
        .options(
            load_only(
                models.Zoo.id,
                models.Zoo.slug,
                models.Zoo.name,
                models.Zoo.address,
                models.Zoo.city,
                models.Zoo.latitude,
                models.Zoo.longitude,
                models.Zoo.description_de,
                models.Zoo.description_en,
            )
        )
        .join(zoo_ids_subquery, zoo_ids_subquery.c.zoo_id == models.Zoo.id)
    )

    results = query_zoos_with_distance(
        query, latitude, longitude, include_no_coords=True
    )

    favorite_zoo_ids: set[uuid.UUID] = set()
    if user is not None:
        favorite_zoo_ids = {
            row[0]
            for row in (
                db.query(models.UserFavoriteZoo.zoo_id)
                .filter(models.UserFavoriteZoo.user_id == user.id)
                .all()
            )
        }

    zoos = [
        to_zoodetail(z, dist, is_favorite=z.id in favorite_zoo_ids)
        for z, dist in results
    ]

    parent_entry: schemas.AnimalRelation | None = None
    if animal.parent_art is not None:
        parent = (
            db.query(models.Animal)
            .options(
                load_only(
                    models.Animal.slug,
                    models.Animal.name_en,
                    models.Animal.name_de,
                    models.Animal.scientific_name,
                )
            )
            .filter(models.Animal.art == animal.parent_art)
            .first()
        )
        if parent is not None:
            parent_entry = schemas.AnimalRelation(
                slug=parent.slug,
                name_en=parent.name_en,
                name_de=parent.name_de,
                scientific_name=parent.scientific_name,
            )

    images = [
        schemas.ImageRead(
            mid=i.mid,
            original_url=i.original_url,
            variants=build_unique_variants(i.variants),
        )
        for i in animal.images
    ]

    return schemas.AnimalDetail(
        id=animal.id,
        slug=animal.slug,
        name_en=animal.name_en,
        scientific_name=animal.scientific_name,
        name_de=animal.name_de,
        category=animal.category.name if animal.category else None,
        description_de=animal.description_de,
        description_en=animal.description_en,
        iucn_conservation_status=animal.conservation_state,
        taxon_rank=animal.taxon_rank,
        class_id=animal.klasse,
        class_name_de=animal.klasse_name.name_de if animal.klasse_name else None,
        class_name_en=animal.klasse_name.name_en if animal.klasse_name else None,
        order_id=animal.ordnung,
        order_name_de=animal.ordnung_name.name_de if animal.ordnung_name else None,
        order_name_en=animal.ordnung_name.name_en if animal.ordnung_name else None,
        family_id=animal.familie,
        family_name_de=animal.familie_name.name_de if animal.familie_name else None,
        family_name_en=animal.familie_name.name_en if animal.familie_name else None,
        default_image_url=animal.default_image_url,
        images=images,
        zoos=zoos,
        is_favorite=is_favorite,
        parent=parent_entry,
        subspecies=subspecies,
    )


@router.get(
    "/animals/{animal_slug}/sightings",
    response_model=schemas.AnimalSightingPage,
)
def list_animal_sightings(
    response: Response,
    animal_slug: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return the authenticated user's sightings for a specific animal."""

    animal = _get_animal_or_404(animal_slug, db)
    set_personalized_cache_headers(response)

    query = build_user_sightings_query(db, user.id).filter(
        models.AnimalSighting.animal_id == animal.id
    )

    total = count_query_rows(query)
    items = apply_recent_first_order(query).limit(limit).offset(offset).all()

    response.headers["X-Total-Count"] = str(total)

    return schemas.AnimalSightingPage(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
