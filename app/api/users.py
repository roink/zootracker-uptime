from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
import uuid

from .. import schemas, models
from ..database import get_db
from ..main import require_json
from ..auth import hash_password, get_user, get_current_user

router = APIRouter()

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
    if user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot view animals for another user")
    animals = (
        db.query(models.Animal)
        .join(models.AnimalSighting, models.Animal.id == models.AnimalSighting.animal_id)
        .filter(models.AnimalSighting.user_id == user_id)
        .distinct()
        .all()
    )
    return animals
