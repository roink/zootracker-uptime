"""Public endpoints that power the marketing landing page."""

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db

router = APIRouter()


@router.get("/site/summary", response_model=schemas.SiteSummary)
def get_site_summary(
    response: Response, db: Session = Depends(get_db)
) -> schemas.SiteSummary:
    """Return aggregate counts for species, zoos, countries and sightings."""

    species_count = db.query(func.count(models.Animal.id)).scalar() or 0
    zoo_count = db.query(func.count(models.Zoo.id)).scalar() or 0
    country_count = (
        db.query(func.count(func.distinct(models.Zoo.country_id)))
        .filter(models.Zoo.country_id.isnot(None))
        .scalar()
        or 0
    )
    sighting_count = db.query(func.count(models.AnimalSighting.id)).scalar() or 0

    response.headers[
        "Cache-Control"
    ] = "public, max-age=300, stale-while-revalidate=600"

    return schemas.SiteSummary(
        species=species_count,
        zoos=zoo_count,
        countries=country_count,
        sightings=sighting_count,
    )


@router.get("/site/popular-animals", response_model=list[schemas.PopularAnimal])
def get_popular_animals(
    limit: int = Query(8, ge=1, le=20), db: Session = Depends(get_db)
) -> list[schemas.PopularAnimal]:
    """Return the most represented animals based on zoo coverage."""

    animals = (
        db.query(models.Animal)
        .order_by(models.Animal.zoo_count.desc(), models.Animal.name_en)
        .limit(limit)
        .all()
    )

    return [
        schemas.PopularAnimal(
            id=a.id,
            slug=a.slug,
            name_en=a.name_en,
            name_de=a.name_de,
            scientific_name=a.scientific_name,
            zoo_count=a.zoo_count,
            iucn_conservation_status=a.conservation_state,
            default_image_url=a.default_image_url,
        )
        for a in animals
    ]
