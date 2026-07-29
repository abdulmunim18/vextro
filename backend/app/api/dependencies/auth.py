import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.repositories.user_repository import get_user_by_id


bearer_scheme = HTTPBearer(auto_error=False)


def authentication_error(
    message: str = "Authentication credentials are invalid.",
) -> HTTPException:
    """Create a standard authentication error response."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "INVALID_ACCESS_TOKEN",
            "message": message,
        },
        headers={
            "WWW-Authenticate": "Bearer",
        },
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
    database_session: Session = Depends(get_db),
) -> User:
    """Validate the access token and return the current user."""

    if credentials is None:
        raise authentication_error(
            "Authentication is required."
        )

    if credentials.scheme.lower() != "bearer":
        raise authentication_error(
            "Bearer authentication is required."
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError as error:
        raise authentication_error(
            "The access token has expired."
        ) from error
    except jwt.InvalidTokenError as error:
        raise authentication_error() from error

    if payload.get("type") != "access":
        raise authentication_error()

    subject = payload.get("sub")

    if subject is None:
        raise authentication_error()

    try:
        user_id = int(subject)
    except (TypeError, ValueError) as error:
        raise authentication_error() from error

    user = get_user_by_id(
        database_session,
        user_id,
    )

    if user is None:
        raise authentication_error(
            "The user associated with this token does not exist."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ACCOUNT_INACTIVE",
                "message": "This account has been deactivated.",
            },
        )

    return user