"""FastAPI application providing the Zoo Tracker API."""

from datetime import timedelta, datetime, UTC
import os
import uuid
import logging

from fastapi import FastAPI, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from passlib.context import CryptContext
import bcrypt
import hashlib
import secrets
import hmac
from collections import defaultdict, deque
import time
import threading

from . import models, schemas
from .database import SessionLocal

SECRET_KEY = os.getenv("SECRET_KEY", "secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Ensure backward compatibility with passlib expecting bcrypt.__about__
if not hasattr(bcrypt, "__about__"):
    class _About:
        __version__ = getattr(bcrypt, "__version__", "")

    bcrypt.__about__ = _About

# bcrypt password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# configure application logging
LOG_FILE = os.getenv("LOG_FILE", "app.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("zoo_tracker")

app = FastAPI(title="Zoo Tracker API")

# allow all CORS origins/methods/headers for the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class RateLimiter:
    """Simple in-memory rate limiter for requests."""

    def __init__(self, limit: int, period: int) -> None:
        self.limit = limit
        self.period = period
        self.history: dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        cutoff = now - self.period
        with self.lock:
            q = self.history[key]
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= self.limit:
                return False
            q.append(now)
        return True


# rate limit settings can be overridden with environment variables
AUTH_RATE_LIMIT = int(os.getenv("AUTH_RATE_LIMIT", "100"))
GENERAL_RATE_LIMIT = int(os.getenv("GENERAL_RATE_LIMIT", "1000"))
RATE_PERIOD = int(os.getenv("RATE_PERIOD", "60"))

auth_limiter = RateLimiter(AUTH_RATE_LIMIT, RATE_PERIOD)
general_limiter = RateLimiter(GENERAL_RATE_LIMIT, RATE_PERIOD)


def _get_user_id_from_request(request: Request) -> str:
    """Return the user id from the auth token or ``anonymous``."""
    auth = request.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload.get("sub") or "unknown"
        except JWTError:
            return "unknown"
    return "anonymous"


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log incoming requests and their response status."""
    logger.info("%s %s", request.method, request.url.path)
    response = await call_next(request)
    logger.info(
        "%s %s -> %s", request.method, request.url.path, response.status_code
    )
    if response.status_code == status.HTTP_400_BAD_REQUEST:
        user_id = _get_user_id_from_request(request)
        logger.warning("400 response for %s by %s", request.url.path, user_id)
    return response


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    """Apply simple rate limiting per client IP."""
    ip = request.client.host or "unknown"
    path = request.url.path
    limiter = auth_limiter if path in {"/token", "/auth/login"} else general_limiter
    if not limiter.is_allowed(ip):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={"detail": "Too Many Requests"},
        )
    return await call_next(request)


def require_json(request: Request) -> None:
    """Ensure the request uses a JSON content-type."""
    if not request.headers.get("content-type", "").lower().startswith("application/json"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)


def get_db():
    """Provide a database session for a single request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    """Return a salt and hashed password for storage using bcrypt."""
    hashed = pwd_context.hash(password)
    # bcrypt embeds the salt in the hash; extract it for storage
    try:
        parts = hashed.split("$")
        salt_str = parts[3]
    except IndexError:
        salt_str = ""
    return salt_str, hashed


def verify_password(plain_password: str, salt_hex: str, hashed_password: str) -> bool:
    """Verify a password against the stored hash using bcrypt."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Generate a signed JWT token for authentication."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user(db: Session, email: str) -> models.User | None:
    """Retrieve a user by email or return ``None`` if not found."""
    return db.query(models.User).filter(models.User.email == email).first()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
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
    return user


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log validation errors and return the standard 422 response."""
    user_id = _get_user_id_from_request(request)
    logger.warning(
        "Validation error on %s by %s: %s",
        request.url.path,
        user_id,
        exc.errors(),
    )
    return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": exc.errors()})


@app.exception_handler(HTTPException)
async def http_exception_handler_logged(request: Request, exc: HTTPException):
    """Log HTTP exceptions with path and user information."""
    user_id = _get_user_id_from_request(request)
    logger.warning(
        "Request to %s rejected for %s with status %s",
        request.url.path,
        user_id,
        exc.status_code,
    )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/")
def read_root():
    """Health check endpoint for the API."""
    return {"message": "Zoo Tracker API"}














@app.get("/visits", response_model=list[schemas.ZooVisitRead])
def list_visits(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """List all visits for the authenticated user."""
    return db.query(models.ZooVisit).filter_by(user_id=user.id).all()




@app.post(
    "/sightings",
    response_model=schemas.AnimalSightingRead,
    dependencies=[Depends(require_json)],
)
def create_sighting(
    sighting_in: schemas.AnimalSightingCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Record an animal sighting for the authenticated user."""
    if sighting_in.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot log sighting for another user",
        )

    if db.get(models.Zoo, sighting_in.zoo_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Zoo not found")

    if db.get(models.Animal, sighting_in.animal_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Animal not found")

    data = sighting_in.model_dump()
    sighting = models.AnimalSighting(**data)
    db.add(sighting)
    db.commit()
    db.refresh(sighting)
    return sighting


@app.get("/sightings/{sighting_id}", response_model=schemas.AnimalSightingRead)
def read_sighting(
    sighting_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Retrieve a single sighting owned by the current user."""
    sighting = db.get(models.AnimalSighting, sighting_id)
    if sighting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Sighting not found")
    if sighting.user_id != user.id and not getattr(user, "is_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Not authorized to view this sighting")
    return sighting


@app.patch(
    "/sightings/{sighting_id}",
    response_model=schemas.AnimalSightingRead,
    dependencies=[Depends(require_json)],
)
def update_sighting(
    sighting_id: uuid.UUID,
    sighting_in: schemas.AnimalSightingUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Update fields of a sighting owned by the current user."""
    sighting = db.get(models.AnimalSighting, sighting_id)
    if sighting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sighting not found")
    if sighting.user_id != user.id and not getattr(user, "is_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this sighting")

    data = sighting_in.model_dump(exclude_unset=True)

    if "zoo_id" in data and db.get(models.Zoo, data["zoo_id"]) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Zoo not found")

    if "animal_id" in data and db.get(models.Animal, data["animal_id"]) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Animal not found")
    for key, value in data.items():
        setattr(sighting, key, value)

    db.add(sighting)
    db.commit()
    db.refresh(sighting)
    return sighting


@app.get("/sightings", response_model=list[schemas.AnimalSightingRead])
def list_sightings(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Retrieve all animal sightings recorded by the current user."""
    return db.query(models.AnimalSighting).filter_by(user_id=user.id).all()


@app.delete("/sightings/{sighting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sighting(
    sighting_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Delete an animal sighting if owned by the user or the user is admin."""
    sighting = db.get(models.AnimalSighting, sighting_id)
    if sighting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sighting not found")

    admin_email = os.getenv("ADMIN_EMAIL")
    is_admin = admin_email and user.email == admin_email
    if sighting.user_id != user.id and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete sighting")

    db.delete(sighting)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)




@app.post("/contact", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_json)])
def send_contact(message: schemas.ContactMessage, request: Request) -> Response:
    """Receive a contact message and log it for review."""
    logger.info("Contact from %s: %s", message.email, message.message)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


from .api import auth_router, users_router, zoos_router, animals_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(zoos_router)
app.include_router(animals_router)
