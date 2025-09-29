import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import schemas, models
from ..auth import hash_password, get_user, get_current_user
from ..database import get_db
from .deps import require_json

router = APIRouter()


def ensure_same_user(user_id: uuid.UUID, current_user: models.User) -> None:
    """Ensure the path user_id matches the authenticated user."""
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view animals for another user",
        )

@router.post("/users", response_model=schemas.UserRead, dependencies=[Depends(require_json)])
def create_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user with a hashed password."""
    if get_user(db, user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(user_in.password)
    user = models.User(
        name=user_in.name,
        email=user_in.email,
        password_hash=hashed,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@router.get("/users/{user_id}/animals", response_model=list[schemas.AnimalRead])
def list_seen_animals(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return all unique animals seen by the specified user."""
    ensure_same_user(user_id, user)
    animals = (
        db.query(models.Animal)
        .join(models.AnimalSighting, models.Animal.id == models.AnimalSighting.animal_id)
        .filter(models.AnimalSighting.user_id == user_id)
        .distinct()
        .all()
    )
    return animals


@router.get("/users/{user_id}/animals/ids", response_model=list[uuid.UUID])
def list_seen_animal_ids(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return IDs of unique animals seen by the specified user."""
    ensure_same_user(user_id, user)
    ids = (
        db.query(models.AnimalSighting.animal_id)
        .filter(models.AnimalSighting.user_id == user_id)
        .distinct()
        .all()
    )
    return [row[0] for row in ids]


@router.get("/users/{user_id}/animals/count", response_model=schemas.Count)
def count_seen_animals(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return the number of unique animals seen by the specified user."""
    ensure_same_user(user_id, user)
    count = (
        db.query(func.count(func.distinct(models.AnimalSighting.animal_id)))
        .filter(models.AnimalSighting.user_id == user_id)
        .scalar()
    ) or 0
    return {"count": count}
