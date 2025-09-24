from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, exists
from sqlalchemy.orm import Session, joinedload

from .. import schemas, models
from ..database import get_db
from ..utils.geometry import query_zoos_with_distance
from ..auth import get_current_user
from .deps import resolve_coords

router = APIRouter()

@router.get("/zoos", response_model=list[schemas.ZooSearchResult])
def search_zoos(
    q: str = "",
    continent_id: int | None = None,
    country_id: int | None = None,
    coords: tuple[float | None, float | None] = Depends(resolve_coords),
    db: Session = Depends(get_db),
):
    """Search for zoos by name, region and optional distance."""

    if continent_id is not None and country_id is not None:
        exists_country = (
            db.query(models.CountryName)
            .filter(
                models.CountryName.id == country_id,
                models.CountryName.continent_id == continent_id,
            )
            .first()
        )
        if not exists_country:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="country_id does not belong to continent_id",
            )

    query = db.query(models.Zoo).options(joinedload(models.Zoo.country))
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(models.Zoo.name.ilike(pattern), models.Zoo.city.ilike(pattern))
        )
    if continent_id is not None:
        query = query.filter(models.Zoo.continent_id == continent_id)
    if country_id is not None:
        query = query.filter(models.Zoo.country_id == country_id)

    latitude, longitude = coords
    results = query_zoos_with_distance(query, latitude, longitude)
    return [
        schemas.ZooSearchResult(
            id=z.id,
            slug=z.slug,
            name=z.name,
            city=z.city,
            latitude=float(z.latitude) if z.latitude is not None else None,
            longitude=float(z.longitude) if z.longitude is not None else None,
            distance_km=dist,
            country_name_en=z.country.name_en if z.country else None,
            country_name_de=z.country.name_de if z.country else None,
        )
        for z, dist in results
    ]


@router.get("/zoos/continents", response_model=list[schemas.TaxonName])
def list_continents(db: Session = Depends(get_db)):
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
def list_countries(continent_id: int, db: Session = Depends(get_db)):
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

    zoo = db.query(models.Zoo).filter(models.Zoo.slug == zoo_slug).first()
    if zoo is None:
        raise HTTPException(status_code=404, detail="Zoo not found")
    return zoo


@router.get("/zoos/{zoo_slug}", response_model=schemas.ZooDetail)
def get_zoo(zoo_slug: str, db: Session = Depends(get_db)):
    """Retrieve detailed information about a zoo."""

    return _get_zoo_or_404(zoo_slug, db)


@router.get("/zoos/{zoo_slug}/visited", response_model=schemas.Visited)
def has_visited_zoo(
    zoo_slug: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
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
    return {"visited": bool(visited)}


@router.get("/zoos/{zoo_slug}/animals", response_model=list[schemas.AnimalRead])
def list_zoo_animals(zoo_slug: str, db: Session = Depends(get_db)):
    """Return animals that are associated with a specific zoo."""

    zoo = _get_zoo_or_404(zoo_slug, db)
    return (
        db.query(models.Animal)
        .join(models.ZooAnimal, models.Animal.id == models.ZooAnimal.animal_id)
        .filter(models.ZooAnimal.zoo_id == zoo.id)
        .order_by(models.Animal.zoo_count.desc())
        .all()
    )
