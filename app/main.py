"""FastAPI application providing the Zoo Tracker API."""

from datetime import timedelta, datetime
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
import hashlib
import secrets
import hmac

from . import models, schemas
from .database import SessionLocal

SECRET_KEY = os.getenv("SECRET_KEY", "secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

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
    """Return a salt and hashed password for storage."""
    if salt is None:
        salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return salt.hex(), hashed.hex()


def verify_password(plain_password: str, salt_hex: str, hashed_password: str) -> bool:
    """Verify a password against the stored salt and hash."""
    salt = bytes.fromhex(salt_hex)
    new_hash = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt, 100000)
    return hmac.compare_digest(new_hash.hex(), hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Generate a signed JWT token for authentication."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
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


@app.post("/users", response_model=schemas.UserRead, dependencies=[Depends(require_json)])
def create_user(
    user_in: schemas.UserCreate,
    db: Session = Depends(get_db),
):
    """Register a new user with a hashed password."""
    if get_user(db, user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    salt, hashed = hash_password(user_in.password)
    user = models.User(
        name=user_in.name,
        email=user_in.email,
        password_salt=salt,
        password_hash=hashed,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate a user and return an access token."""
    if not form_data.username or not form_data.password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing username or password")
    user = get_user(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password_salt, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token = create_access_token({"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/auth/login", response_model=schemas.Token)
# alias used by the planned front-end
def login_alias(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Alternate login endpoint used by the front-end."""
    token_data = login(form_data, db)
    user = get_user(db, form_data.username)
    token_data["user_id"] = str(user.id)
    return token_data


@app.get("/zoos", response_model=list[schemas.ZooRead])
def search_zoos(
    q: str = "",
    latitude: float | None = None,
    longitude: float | None = None,
    radius_km: float = 50.0,
    db: Session = Depends(get_db),
):
    """Search for zoos by name and optional distance from a point."""
    query = db.query(models.Zoo)
    if q:
        pattern = f"%{q}%"
        query = query.filter(models.Zoo.name.ilike(pattern))

    zoos = query.all()

    if latitude is not None and longitude is not None:
        def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            """Return distance in kilometers between two lat/lon points."""
            from math import radians, cos, sin, asin, sqrt

            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            c = 2 * asin(sqrt(a))
            return 6371 * c

        results = []
        for zoo in zoos:
            if zoo.latitude is None or zoo.longitude is None:
                continue
            dist = haversine(
                float(latitude), float(longitude), float(zoo.latitude), float(zoo.longitude)
            )
            if dist <= radius_km:
                results.append(zoo)
        return results

    return zoos


@app.get("/zoos/{zoo_id}", response_model=schemas.ZooDetail)
def get_zoo(zoo_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve detailed information about a zoo."""
    zoo = db.get(models.Zoo, zoo_id)
    if zoo is None:
        raise HTTPException(status_code=404, detail="Zoo not found")
    return zoo


@app.get("/animals", response_model=list[schemas.AnimalRead])
def list_animals(q: str = "", db: Session = Depends(get_db)):
    """List animals optionally filtered by a search query."""
    query = db.query(models.Animal)
    if q:
        pattern = f"%{q}%"
        query = query.filter(models.Animal.common_name.ilike(pattern))
    return query.all()


@app.get("/search", response_model=schemas.SearchResults)
def combined_search(q: str = "", limit: int = 5, db: Session = Depends(get_db)):
    """Return top zoos and animals matching the query."""
    zoo_q = db.query(models.Zoo)
    if q:
        pattern = f"%{q}%"
        zoo_q = zoo_q.filter(models.Zoo.name.ilike(pattern))
    zoos = zoo_q.limit(limit).all()

    animal_q = db.query(models.Animal)
    if q:
        pattern = f"%{q}%"
        animal_q = animal_q.filter(models.Animal.common_name.ilike(pattern))
    animals = animal_q.limit(limit).all()

    return {"zoos": zoos, "animals": animals}


# list animals available at a specific zoo
@app.get("/zoos/{zoo_id}/animals", response_model=list[schemas.AnimalRead])
def list_zoo_animals(zoo_id: uuid.UUID, db: Session = Depends(get_db)):
    """Return animals that are associated with a specific zoo."""
    return (
        db.query(models.Animal)
        .join(models.ZooAnimal, models.Animal.id == models.ZooAnimal.animal_id)
        .filter(models.ZooAnimal.zoo_id == zoo_id)
        .all()
    )


@app.get("/animals/{animal_id}", response_model=schemas.AnimalDetail)
def get_animal_detail(animal_id: uuid.UUID, db: Session = Depends(get_db)):
    """Retrieve a single animal and the zoos where it can be found."""
    animal = db.get(models.Animal, animal_id)
    if animal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Animal not found")

    zoos = (
        db.query(models.Zoo)
        .join(models.ZooAnimal, models.Zoo.id == models.ZooAnimal.zoo_id)
        .filter(models.ZooAnimal.animal_id == animal_id)
        .all()
    )

    return schemas.AnimalDetail(
        id=animal.id,
        common_name=animal.common_name,
        scientific_name=animal.scientific_name,
        category=animal.category.name if animal.category else None,
        description=animal.description,
        zoos=zoos,
    )


@app.get(
    "/animals/{animal_id}/zoos",
    response_model=list[schemas.ZooDetail],
)
def list_zoos_for_animal(
    animal_id: uuid.UUID,
    latitude: float | None = None,
    longitude: float | None = None,
    db: Session = Depends(get_db),
):
    """Return zoos that house the given animal ordered by distance if provided."""
    animal = db.get(models.Animal, animal_id)
    if animal is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Animal not found")

    if latitude is not None and not -90 <= latitude <= 90:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid latitude")
    if longitude is not None and not -180 <= longitude <= 180:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid longitude")

    zoos = (
        db.query(models.Zoo)
        .join(models.ZooAnimal, models.Zoo.id == models.ZooAnimal.zoo_id)
        .filter(models.ZooAnimal.animal_id == animal_id)
        .all()
    )

    if latitude is not None and longitude is not None:
        from math import radians, cos, sin, asin, sqrt

        def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
            lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
            dlat = lat2 - lat1
            dlon = lon2 - lon1
            a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
            c = 2 * asin(sqrt(a))
            return 6371 * c

        zoos.sort(
            key=lambda z: haversine(
                float(latitude),
                float(longitude),
                float(z.latitude) if z.latitude is not None else 0.0,
                float(z.longitude) if z.longitude is not None else 0.0,
            )
            if z.latitude is not None and z.longitude is not None
            else float("inf")
        )

    return zoos


@app.post(
    "/visits",
    response_model=schemas.ZooVisitRead,
    dependencies=[Depends(require_json)],
)
def create_visit(
    visit_in: schemas.ZooVisitCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Create a visit record for the authenticated user."""
    if db.get(models.Zoo, visit_in.zoo_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Zoo not found")
    visit = models.ZooVisit(user_id=user.id, **visit_in.model_dump())
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


# new endpoints to explicitly log a visit for a user
@app.post(
    "/users/{user_id}/visits",
    response_model=schemas.ZooVisitRead,
    dependencies=[Depends(require_json)],
)
def create_visit_for_user(
    user_id: uuid.UUID,
    visit_in: schemas.ZooVisitCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Create a visit for a specific user. Users may only log their own visits."""
    if user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot log visit for another user")
    if db.get(models.Zoo, visit_in.zoo_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Zoo not found")
    visit = models.ZooVisit(user_id=user.id, **visit_in.model_dump())
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


@app.get("/visits", response_model=list[schemas.ZooVisitRead])
def list_visits(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """List all visits for the authenticated user."""
    return db.query(models.ZooVisit).filter_by(user_id=user.id).all()


@app.patch(
    "/visits/{visit_id}",
    response_model=schemas.ZooVisitRead,
    dependencies=[Depends(require_json)],
)
def update_visit(
    visit_id: uuid.UUID,
    visit_in: schemas.ZooVisitUpdate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Update a visit's date or notes."""
    visit = db.get(models.ZooVisit, visit_id)
    if visit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")
    if visit.user_id != user.id and not getattr(user, "is_admin", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update this visit")

    data = visit_in.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(visit, key, value)

    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit

@app.delete("/visits/{visit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_visit(
    visit_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Delete a visit if owned by the user or the user is admin."""
    visit = db.get(models.ZooVisit, visit_id)
    if visit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Visit not found")

    admin_email = os.getenv("ADMIN_EMAIL")
    is_admin = admin_email and user.email == admin_email
    if visit.user_id != user.id and not is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete visit")

    db.delete(visit)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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


@app.get("/users/{user_id}/animals", response_model=list[schemas.AnimalRead])
def list_seen_animals(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Return all unique animals seen by the specified user."""
    if user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Cannot view animals for another user")
    animals = (
        db.query(models.Animal)
        .join(models.AnimalSighting,
              models.Animal.id == models.AnimalSighting.animal_id)
        .filter(models.AnimalSighting.user_id == user_id)
        .distinct()
        .all()
    )
    return animals
