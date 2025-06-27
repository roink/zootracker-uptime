from datetime import timedelta, datetime
import os
import uuid

from fastapi import FastAPI, Depends, HTTPException, status
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

app = FastAPI(title="Zoo Tracker API")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str, salt: bytes | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_bytes(16)
    hashed = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100000)
    return salt.hex(), hashed.hex()


def verify_password(plain_password: str, salt_hex: str, hashed_password: str) -> bool:
    salt = bytes.fromhex(salt_hex)
    new_hash = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt, 100000)
    return hmac.compare_digest(new_hash.hex(), hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_user(db: Session, email: str) -> models.User | None:
    return db.query(models.User).filter(models.User.email == email).first()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
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


@app.get("/")
def read_root():
    return {"message": "Zoo Tracker API"}


@app.post("/users", response_model=schemas.UserRead)
def create_user(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
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
    user = get_user(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password_salt, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token = create_access_token({"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/zoos", response_model=list[schemas.ZooRead])
def search_zoos(q: str = "", db: Session = Depends(get_db)):
    query = db.query(models.Zoo)
    if q:
        pattern = f"%{q}%"
        query = query.filter(models.Zoo.name.ilike(pattern))
    return query.all()


@app.get("/animals", response_model=list[schemas.AnimalRead])
def list_animals(q: str = "", db: Session = Depends(get_db)):
    query = db.query(models.Animal)
    if q:
        pattern = f"%{q}%"
        query = query.filter(models.Animal.common_name.ilike(pattern))
    return query.all()


@app.post("/visits", response_model=schemas.ZooVisitRead)
def create_visit(
    visit_in: schemas.ZooVisitCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    visit = models.ZooVisit(user_id=user.id, **visit_in.model_dump())
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return visit


# new endpoints to explicitly log a visit for a user
@app.post("/users/{user_id}/visits", response_model=schemas.ZooVisitRead)
def create_visit_for_user(
    user_id: uuid.UUID,
    visit_in: schemas.ZooVisitCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot log visit for another user")
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
    return db.query(models.ZooVisit).filter_by(user_id=user.id).all()


@app.post("/sightings", response_model=schemas.AnimalSightingRead)
def create_sighting(
    sighting_in: schemas.AnimalSightingCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    if sighting_in.user_id is not None and sighting_in.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Cannot log sighting for another user")

    if db.get(models.Zoo, sighting_in.zoo_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Zoo not found")

    if db.get(models.Animal, sighting_in.animal_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Animal not found")

    data = sighting_in.model_dump(exclude={"user_id"})
    sighting = models.AnimalSighting(user_id=user.id, **data)
    db.add(sighting)
    db.commit()
    db.refresh(sighting)
    return sighting


@app.get("/sightings", response_model=list[schemas.AnimalSightingRead])
def list_sightings(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    return db.query(models.AnimalSighting).filter_by(user_id=user.id).all()
