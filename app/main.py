"""FastAPI application providing the Zoo Tracker API."""

import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from .config import ALLOWED_ORIGINS
from .database import get_db
from .logging import configure_logging
from .middleware.logging import LoggingMiddleware
from .rate_limit import rate_limit

# load environment variables from .env if present
load_dotenv()
configure_logging()

logger = logging.getLogger("app.main")
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
    allow_headers=["Authorization", "Content-Type"],
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
