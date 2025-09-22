import uuid
from datetime import datetime, timedelta, UTC

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
import bcrypt

from . import models
from .database import get_db
from .config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES
from .middleware.logging import set_user_context

# Ensure backward compatibility with passlib expecting bcrypt.__about__
if not hasattr(bcrypt, "__about__"):
    class _About:
        __version__ = getattr(bcrypt, "__version__", "")
    bcrypt.__about__ = _About

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Inform clients of token lifetime in the OpenAPI docs
# Import this dependency from ``app.auth`` when securing routes.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="auth/login",
    description=f"Access token expires in {ACCESS_TOKEN_EXPIRE_MINUTES} minutes",
)


# Internal; import from ``app.auth`` only.
def hash_password(password: str) -> str:
    """Return a hashed password for storage using bcrypt."""
    return pwd_context.hash(password)


# Internal; import from ``app.auth`` only.
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against the stored hash using bcrypt."""
    return pwd_context.verify(plain_password, hashed_password)


# Internal; import from ``app.auth`` only.
def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Generate a signed JWT token for authentication."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


# Internal; import from ``app.auth`` only.
def get_user(db: Session, email: str) -> models.User | None:
    """Retrieve a user by email or return ``None`` if not found."""
    return db.query(models.User).filter(models.User.email == email).first()


# Internal; import from ``app.auth`` only.
def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Return the authenticated user based on the provided JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    try:
        uuid_val = uuid.UUID(user_id)
    except ValueError:
        raise credentials_exception

    user = db.get(models.User, uuid_val)
    if user is None:
        raise credentials_exception
    set_user_context(str(user.id))
    return user
