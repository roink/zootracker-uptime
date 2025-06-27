from datetime import timedelta, datetime
import os

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from jose import jwt, JWTError
from passlib.context import CryptContext

from . import models, schemas
from .database import SessionLocal

SECRET_KEY = os.getenv("SECRET_KEY", "secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI(title="Zoo Tracker API")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


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
    user = db.query(models.User).get(user_id)
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
    hashed = get_password_hash(user_in.password)
    user = models.User(name=user_in.name, email=user_in.email, password_hash=hashed)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/token", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = get_user(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
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
    visit = models.ZooVisit(user_id=user.id, **visit_in.dict())
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
    sighting = models.AnimalSighting(user_id=user.id, **sighting_in.dict())
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
