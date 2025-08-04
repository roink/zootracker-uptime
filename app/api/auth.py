from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import schemas
from ..models import User
from ..database import get_db
from ..auth import get_user, verify_password, create_access_token

router = APIRouter()

@router.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate a user and return an access token."""
    if not form_data.username or not form_data.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing username or password")
    user = get_user(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token = create_access_token({"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/auth/login", response_model=schemas.Token)
def login_alias(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Alternate login endpoint used by the front-end."""
    token_data = login(form_data, db)
    user = get_user(db, form_data.username)
    token_data["user_id"] = str(user.id)
    return token_data
