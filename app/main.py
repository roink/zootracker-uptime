"""FastAPI application providing the Zoo Tracker API."""

import os
import uuid
import logging
import smtplib
from email.message import EmailMessage

from contextlib import asynccontextmanager

import bleach
from dotenv import load_dotenv

from fastapi import FastAPI, Depends, HTTPException, Request, status, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import cast, Date
from sqlalchemy.orm import Session, joinedload
from jose import jwt, JWTError

from . import models, schemas
from .database import get_db
from .auth import get_current_user
from .config import SECRET_KEY, ALGORITHM
from .rate_limit import rate_limit, enforce_contact_rate_limit
from .utils.network import get_client_ip

# load environment variables from .env if present
load_dotenv()

# configure application logging
LOG_FILE = os.getenv("LOG_FILE", "app.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
logger = logging.getLogger("zoo_tracker")


def _check_env_vars() -> None:
    """Fail fast if required environment variables are missing."""
    required = ["SMTP_HOST", "CONTACT_EMAIL"]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        missing_str = ", ".join(missing)
        raise RuntimeError(f"Missing required environment variables: {missing_str}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_env_vars()
    yield


app = FastAPI(title="Zoo Tracker API", lifespan=lifespan)

# allow all CORS origins/methods/headers for the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# register rate limiting middleware
app.middleware("http")(rate_limit)


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
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.get("/")
def read_root():
    """Health check endpoint for the API."""
    return {"message": "Zoo Tracker API"}

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
    sighting = (
        db.query(models.AnimalSighting)
        .options(
            joinedload(models.AnimalSighting.animal),
            joinedload(models.AnimalSighting.zoo),
        )
        .filter(models.AnimalSighting.id == sighting_id)
        .first()
    )
    if sighting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sighting not found",
        )
    if sighting.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to view this sighting",
        )
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
    if sighting.user_id != user.id:
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
    return (
        db.query(models.AnimalSighting)
        .options(
            joinedload(models.AnimalSighting.animal),
            joinedload(models.AnimalSighting.zoo),
        )
        .filter_by(user_id=user.id)
        .order_by(
            cast(models.AnimalSighting.sighting_datetime, Date).desc(),
            models.AnimalSighting.created_at.desc(),
        )
        .all()
    )


@app.delete("/sightings/{sighting_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_sighting(
    sighting_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
):
    """Delete an animal sighting if owned by the current user."""
    sighting = db.get(models.AnimalSighting, sighting_id)
    if sighting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sighting not found")

    if sighting.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete sighting")

    db.delete(sighting)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)




def _send_contact_email(host, port, use_ssl, user, password, from_addr, to_addr, reply_to, name, msg_text):
    """Send the contact email synchronously in a background task."""
    email_msg = EmailMessage()
    email_msg["Subject"] = f"Contact form – {name}"
    email_msg["From"] = from_addr
    email_msg["To"] = to_addr
    email_msg["Reply-To"] = reply_to
    email_msg.set_content(f"From: {name} <{reply_to}>\n\n{msg_text}")
    try:
        server_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
        with server_cls(host, port) as server:
            if not use_ssl:
                server.starttls()
            if user and password:
                server.login(user, password)
            server.send_message(email_msg)
    except Exception:
        logger.exception("Failed to send contact email")


@app.post(
    "/contact",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_json), Depends(enforce_contact_rate_limit)],
)
def send_contact(message: schemas.ContactMessage, request: Request, background_tasks: BackgroundTasks) -> Response:
    """Send a contact message via email and log the submission."""
    name = bleach.clean(message.name, tags=[], strip=True)
    msg_text = bleach.clean(message.message, tags=[], strip=True)
    ip = get_client_ip(request)
    ua = request.headers.get("User-Agent", "unknown")
    logger.info("Contact from %s <%s> ip=%s agent=%s: %s", name, message.email, ip, ua, msg_text)

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    use_ssl = os.getenv("SMTP_SSL", "").lower() in {"1", "true", "yes"}
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("SMTP_FROM", "contact@zootracker.app")
    to_addr = os.getenv("CONTACT_EMAIL", "contact@zootracker.app")
    if not host or not to_addr:
        logger.error("SMTP host or CONTACT_EMAIL missing")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email service misconfigured",
        )

    background_tasks.add_task(
        _send_contact_email,
        host,
        port,
        use_ssl,
        user,
        password,
        from_addr,
        to_addr,
        message.email,
        name,
        msg_text,
    )

    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    remaining = getattr(request.state, "rate_limit_remaining", None)
    if remaining is not None:
        response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response


from .api import (  # noqa: E402
    auth_router,
    users_router,
    zoos_router,
    animals_router,
    images_router,
    visits_router,
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(zoos_router)
app.include_router(animals_router)
app.include_router(images_router)
app.include_router(visits_router)
