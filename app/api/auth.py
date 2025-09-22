import logging
import time
from collections import defaultdict, deque
from typing import Deque

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..auth import get_user, verify_password, create_access_token
from ..logging_config import anonymize_ip
from ..middleware.logging import set_user_context
from ..utils.network import get_client_ip

router = APIRouter()


auth_logger = logging.getLogger("app.auth")
_FAILURE_WINDOW_SECONDS = 60
_FAILURE_LOG_LIMIT = 10
_failure_attempts: dict[str, Deque[float]] = defaultdict(deque)


def _should_log_failure(ip_key: str) -> bool:
    now = time.monotonic()
    history = _failure_attempts[ip_key]
    while history and now - history[0] > _FAILURE_WINDOW_SECONDS:
        history.popleft()
    history.append(now)
    return len(history) <= _FAILURE_LOG_LIMIT


@router.post("/auth/login", response_model=schemas.Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """Authenticate a user and return an access token."""
    if not form_data.username or not form_data.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing username or password",
        )
    client_ip = get_client_ip(request)
    safe_ip = anonymize_ip(client_ip)
    user = get_user(db, form_data.username)
    if not user or not verify_password(form_data.password, user.password_hash):
        if _should_log_failure(client_ip or "unknown"):
            auth_logger.warning(
                "Authentication failed",
                extra={
                    "event_dataset": "zoo-tracker-api.auth",
                    "event_action": "login_failed",
                    "client_ip": safe_ip,
                    "auth_method": "password",
                    "auth_failure_reason": "invalid_credentials",
                },
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    access_token = create_access_token({"sub": str(user.id)})
    set_user_context(str(user.id))
    auth_logger.info(
        "Authentication successful",
        extra={
            "event_dataset": "zoo-tracker-api.auth",
            "event_action": "login_success",
            "client_ip": safe_ip,
            "auth_method": "password",
        },
    )
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_id": str(user.id),
    }
