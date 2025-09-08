from fastapi import APIRouter, Depends, HTTPException, Response, status, Query
from sqlalchemy.orm import Session, joinedload

from .. import schemas, models
from ..database import get_db

router = APIRouter()


@router.get(
    "/images",
    response_model=schemas.ImageAttribution,
    tags=["images"],
    summary="Fetch image attribution by media ID",
)
def get_image_metadata(
    *,
    mid: str = Query(..., description="Wikimedia Commons media ID"),
    response: Response,
    db: Session = Depends(get_db),
):
    """Return image attribution metadata for the given media id."""
    image = (
        db.query(models.Image)
        .options(joinedload(models.Image.variants))
        .filter(models.Image.mid == mid)
        .first()
    )
    if image is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        )

    author = image.artist_plain or image.artist_raw or image.uploader
    license_name = image.license or image.license_short

    variants: list[schemas.ImageVariant] = []
    seen_widths: set[int] = set()
    for v in sorted(image.variants, key=lambda v: v.width):
        if v.width in seen_widths:
            continue
        seen_widths.add(v.width)
        variants.append(
            schemas.ImageVariant(width=v.width, height=v.height, thumb_url=v.thumb_url)
        )

    response.headers["Cache-Control"] = "public, max-age=86400"
    return schemas.ImageAttribution(
        mid=image.mid,
        original_url=image.original_url,
        commons_page_url=image.commons_page_url,
        commons_title=image.commons_title,
        author=author,
        license=license_name,
        license_url=image.license_url,
        credit_line=image.credit_line,
        attribution_required=image.attribution_required,
        variants=variants,
    )
