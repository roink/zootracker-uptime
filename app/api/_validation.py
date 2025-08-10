from fastapi import HTTPException, status


def validate_coords(latitude: float | None, longitude: float | None) -> None:
    if (latitude is None) ^ (longitude is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide both latitude and longitude together."
        )
    if latitude is None:
        return
    if not (-90 <= latitude <= 90):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid latitude")
    if not (-180 <= longitude <= 180):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid longitude")
