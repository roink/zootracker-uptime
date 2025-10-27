"""FastAPI application providing the Zoo Tracker API."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse, Response, JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from .config import ALLOWED_ORIGINS, SECURITY_HEADERS, CSRF_HEADER_NAME

from .database import get_db  # noqa: F401 - re-exported for tests and scripts
from .logging import configure_logging
from .middleware.logging import LoggingMiddleware
from .middleware.security import SecureHeadersMiddleware
from .rate_limit import rate_limit

configure_logging()

logger = logging.getLogger("app.main")

_DB_RETRY_AFTER_SECONDS = "600"


def _check_env_vars() -> None:
    """Fail fast if required environment variables are missing or invalid."""

    required = [
        "SECRET_KEY",  # JWT signing; refuse to boot without it
        "DATABASE_URL",  # SQLAlchemy target; avoids "implicit default" pitfalls
        "ALLOWED_ORIGINS",  # CORS must be explicit in your setup
        "SMTP_HOST",
        "CONTACT_EMAIL",
    ]
    missing = [
        name for name in required if not (os.getenv(name) and os.getenv(name).strip())
    ]
    if missing:
        missing_str = ", ".join(missing)
        raise RuntimeError(f"Missing required environment variables: {missing_str}")

    secret_key = (os.getenv("SECRET_KEY") or "").strip()
    if len(secret_key) < 32:
        raise RuntimeError("SECRET_KEY must be at least 32 characters long")

    contact_email = (os.getenv("CONTACT_EMAIL") or "").strip()
    if "@" not in contact_email:
        raise RuntimeError("CONTACT_EMAIL must be a valid email address")

    raw_origins = os.getenv("ALLOWED_ORIGINS", "")
    origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    if not origins:
        raise RuntimeError(
            "ALLOWED_ORIGINS must contain at least one comma-separated origin"
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _check_env_vars()
    yield


app = FastAPI(
    title="Zoo Tracker API",
    lifespan=lifespan,
    default_response_class=ORJSONResponse,
)
app.add_middleware(SecureHeadersMiddleware, headers=SECURITY_HEADERS)
app.add_middleware(LoggingMiddleware)

# configure CORS using a controlled list of allowed origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", CSRF_HEADER_NAME],
    allow_credentials=True,
)

# register rate limiting middleware
app.middleware("http")(rate_limit)

def _set_request_id_header(response: Response, request: Request) -> None:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        response.headers["X-Request-ID"] = request_id

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
    response = ORJSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content={"detail": errors}
    )
    _set_request_id_header(response, request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
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
    response = ORJSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )
    _set_request_id_header(response, request)
    return response


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Convert transient database errors into a cache-friendly 503 response."""

    logger.exception(
        "Database error while handling request",
        extra={
            "event_dataset": "zoo-tracker-api.app",
            "event_action": "database_error",
            "http_status_code": status.HTTP_503_SERVICE_UNAVAILABLE,
            "http_request_method": request.method,
            "url_path": request.url.path,
            "error_type": type(exc).__name__,
        },
    )

    response = JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "Temporary database issue. Please retry later."},
        headers={
            "Retry-After": _DB_RETRY_AFTER_SECONDS,
            "Cache-Control": "no-store",
        },
    )
    response.headers["Pragma"] = "no-cache"
    _set_request_id_header(response, request)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Ensure all responses include the request id header on failure."""

    response = ORJSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"},
    )
    _set_request_id_header(response, request)
    return response


@app.get("/")
def read_root():
    """Health check endpoint for the API."""
    return {"message": "Zoo Tracker API"}

from .api import (  # noqa: E402
    animals_router,
    auth_router,
    contact_router,
    images_router,
    location_router,
    sightings_router,
    site_router,
    users_router,
    visits_router,
    zoos_router,
)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(zoos_router)
app.include_router(animals_router)
app.include_router(images_router)
app.include_router(visits_router)
app.include_router(location_router)
app.include_router(site_router)
app.include_router(sightings_router)
app.include_router(contact_router)
