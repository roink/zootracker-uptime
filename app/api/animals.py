from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload, load_only

from .. import schemas, models
from ..database import get_db
from ..utils.geometry import query_zoos_with_distance
from .deps import resolve_coords


def to_zoodetail(z: models.Zoo, dist: float | None) -> schemas.ZooDetail:
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
    )

router = APIRouter()

@router.get("/animals", response_model=list[schemas.AnimalListItem])
def list_animals(
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    category: str | None = None,
    class_id: int | None = None,
    order_id: int | None = None,
    family_id: int | None = None,
    db: Session = Depends(get_db),
):
    """List animals filtered by search query, taxonomy and pagination."""

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
            .filter(models.Animal.ordnung == order_id, models.Animal.familie == family_id)
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
        query.order_by(models.Animal.name_en)
        .offset(offset)
        .limit(limit)
        .all()
    )

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
def combined_search(q: str = "", limit: int = 5, db: Session = Depends(get_db)):
    """Return top zoos and animals matching the query."""
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

    return {"zoos": zoos, "animals": animals}

@router.get("/animals/{animal_slug}", response_model=schemas.AnimalDetail)
def get_animal_detail(
    animal_slug: str,
    coords: tuple[float | None, float | None] = Depends(resolve_coords),
    db: Session = Depends(get_db),
):
    """Retrieve a single animal and the zoos where it can be found.

    When ``latitude`` and ``longitude`` are supplied the zoos are ordered by
    distance and include a ``distance_km`` field so the frontend only needs a
    single request.
    """
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found")

    animal_id = animal.id
    latitude, longitude = coords

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
        .join(models.ZooAnimal, models.Zoo.id == models.ZooAnimal.zoo_id)
        .filter(models.ZooAnimal.animal_id == animal_id)
    )

    results = query_zoos_with_distance(query, latitude, longitude, include_no_coords=True)

    zoos = [to_zoodetail(z, dist) for z, dist in results]

    images = []
    for i in animal.images:
        # Return thumbnail variants deduplicated by width so the frontend can
        # build concise ``srcset`` attributes.
        variants: list[schemas.ImageVariant] = []
        seen_widths: set[int] = set()
        for v in i.variants:
            if v.width in seen_widths:
                continue
            seen_widths.add(v.width)
            variants.append(
                schemas.ImageVariant(width=v.width, height=v.height, thumb_url=v.thumb_url)
            )
        images.append(
            schemas.ImageRead(
                mid=i.mid,
                original_url=i.original_url,
                variants=variants,
            )
        )

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
        class_name_de=animal.klasse_name.name_de if animal.klasse_name else None,
        class_name_en=animal.klasse_name.name_en if animal.klasse_name else None,
        order_name_de=animal.ordnung_name.name_de if animal.ordnung_name else None,
        order_name_en=animal.ordnung_name.name_en if animal.ordnung_name else None,
        family_name_de=animal.familie_name.name_de if animal.familie_name else None,
        family_name_en=animal.familie_name.name_en if animal.familie_name else None,
        default_image_url=animal.default_image_url,
        images=images,
        zoos=zoos,
    )

