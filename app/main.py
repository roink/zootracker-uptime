"""FastAPI application providing the Zoo Tracker API."""

import hashlib
import hmac
import logging
import os
import smtplib
import uuid
from email.message import EmailMessage
import time

from contextlib import asynccontextmanager

import bleach
from dotenv import load_dotenv

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import Date, cast
from sqlalchemy.orm import Session, joinedload

from . import models, schemas
from .auth import get_current_user
from .config import ALLOWED_ORIGINS
from .database import get_db
from .logging_config import anonymize_ip, configure_logging
from .middleware.logging import LoggingMiddleware
from .rate_limit import enforce_contact_rate_limit, rate_limit
from .utils.network import get_client_ip

# load environment variables from .env if present
load_dotenv()
configure_logging()

logger = logging.getLogger("app.main")
audit_logger = logging.getLogger("app.audit")

CONTACT_TOKEN_SECRET = os.getenv("CONTACT_TOKEN_SECRET", "dev-contact-secret")
CONTACT_TOKEN_MIN_AGE_MS = int(os.getenv("CONTACT_TOKEN_MIN_AGE_MS", "3000"))


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

app.add_middleware(LoggingMiddleware)

# configure CORS using a controlled list of allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# register rate limiting middleware
app.middleware("http")(rate_limit)

def _set_request_id_header(response: Response, request: Request) -> None:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id


def require_json(request: Request) -> None:
    """Ensure the request uses a JSON content-type."""
    if not request.headers.get("content-type", "").lower().startswith("application/json"):
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)


def _sign_contact_payload(rendered_at: int, user_agent: str, client_nonce: str) -> str:
    """Create a deterministic signature for the contact form payload."""

    payload = f"{rendered_at}|{user_agent}|{client_nonce}".encode("utf-8")
    secret = CONTACT_TOKEN_SECRET.encode("utf-8")
    digest = hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return digest

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Log validation errors and return the standard 422 response."""

    errors = exc.errors()
    error_types = sorted({err.get("type", "unknown") for err in errors})
    logger.warning(
        "Request validation failed",
        extra={
            "event_dataset": "zoo-tracker-api.app",
            "event_action": "validation_failed",
            "http_status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "http_request_method": request.method,
            "url_path": request.url.path,
            "error_type": "RequestValidationError",
            "error_message": ",".join(error_types)[:128],
            "validation_error_count": len(errors),
        },
    )
    response = JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": errors}
    )
    _set_request_id_header(response, request)
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler_logged(request: Request, exc: HTTPException):
    """Log HTTP exceptions with path and user information."""

    level = logging.ERROR if exc.status_code >= 500 else logging.WARNING
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    logger.log(
        level,
        "HTTP exception raised",
        extra={
            "event_dataset": "zoo-tracker-api.app",
            "event_action": "http_exception",
            "http_status_code": exc.status_code,
            "http_request_method": request.method,
            "url_path": request.url.path,
            "error_type": type(exc).__name__,
            "error_message": detail[:256],
        },
    )
    response = JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )
    _set_request_id_header(response, request)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Ensure all responses include the request id header on failure."""

    response = JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"},
    )
    _set_request_id_header(response, request)
    return response


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
    audit_logger.info(
        "Sighting created",
        extra={
            "event_dataset": "zoo-tracker-api.audit",
            "event_action": "created",
            "event_kind": "audit",
            "sighting_id": str(sighting.id),
            "change_summary": ",".join(sorted(data.keys())),
        },
    )
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
    audit_logger.info(
        "Sighting updated",
        extra={
            "event_dataset": "zoo-tracker-api.audit",
            "event_action": "updated",
            "event_kind": "audit",
            "sighting_id": str(sighting.id),
            "change_summary": ",".join(sorted(data.keys()) or ["no_changes"]),
        },
    )
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
    audit_logger.info(
        "Sighting deleted",
        extra={
            "event_dataset": "zoo-tracker-api.audit",
            "event_action": "deleted",
            "event_kind": "audit",
            "sighting_id": str(sighting_id),
            "change_summary": "record_removed",
        },
    )
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
        logger.exception(
            "Failed to send contact email",
            extra={
                "event_dataset": "zoo-tracker-api.app",
                "event_action": "contact_email_failed",
            },
        )


@app.post(
    "/contact",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_json), Depends(enforce_contact_rate_limit)],
)
def send_contact(message: schemas.ContactMessage, request: Request, background_tasks: BackgroundTasks) -> Response:
    """Send a contact message via email and log the submission."""
    ua = request.headers.get("User-Agent", "unknown")
    expected_sig = _sign_contact_payload(message.rendered_at, ua, message.client_nonce)
    if not hmac.compare_digest(expected_sig, message.signature):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="invalid_signature",
        )

    now_ms = int(time.time() * 1000)
    if now_ms - message.rendered_at < CONTACT_TOKEN_MIN_AGE_MS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="too_fast",
        )

    name = bleach.clean(message.name, tags=[], strip=True)
    msg_text = bleach.clean(message.message, tags=[], strip=True)
    ip = get_client_ip(request)
    safe_ip = getattr(request.state, "client_ip_logged", anonymize_ip(ip))
    email_domain = message.email.split("@", 1)[1] if "@" in message.email else "unknown"
    logger.info(
        "Contact submission received",
        extra={
            "event_dataset": "zoo-tracker-api.app",
            "event_action": "contact_submitted",
            "client_ip": safe_ip,
            "user_agent": ua,
            "contact_email_domain": email_domain,
            "contact_message_length": len(msg_text),
        },
    )

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    use_ssl = os.getenv("SMTP_SSL", "").lower() in {"1", "true", "yes"}
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    from_addr = os.getenv("SMTP_FROM", "contact@zootracker.app")
    to_addr = os.getenv("CONTACT_EMAIL", "contact@zootracker.app")
    if not host or not to_addr:
        logger.error(
            "Email service misconfigured",
            extra={
                "event_dataset": "zoo-tracker-api.app",
                "event_action": "contact_email_missing_config",
                "http_status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        )
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
