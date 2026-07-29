from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.user import User
from app.repositories.refresh_token_repository import (
    create_refresh_token_record,
)
from app.repositories.user_repository import (
    create_user,
    get_role_by_name,
    get_user_by_email,
)
from app.schemas.auth import UserLogin, UserRegister


class EmailAlreadyRegisteredError(Exception):
    """Raised when an email already belongs to another user."""


class RegistrationRoleNotFoundError(Exception):
    """Raised when the selected registration role does not exist."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials are incorrect."""


class InactiveAccountError(Exception):
    """Raised when the account has been deactivated."""


def register_user(
    database_session: Session,
    registration_data: UserRegister,
) -> User:
    """Validate and create a new VEXTRO user account."""

    normalized_email = str(
        registration_data.email
    ).strip().lower()

    existing_user = get_user_by_email(
        database_session,
        normalized_email,
    )

    if existing_user is not None:
        raise EmailAlreadyRegisteredError

    selected_role = get_role_by_name(
        database_session,
        registration_data.account_type,
    )

    if selected_role is None:
        raise RegistrationRoleNotFoundError

    secure_password_hash = hash_password(
        registration_data.password
    )

    try:
        return create_user(
            database_session,
            full_name=registration_data.full_name,
            email=normalized_email,
            password_hash=secure_password_hash,
            role=selected_role,
        )
    except IntegrityError as error:
        raise EmailAlreadyRegisteredError from error


def authenticate_user(
    database_session: Session,
    login_data: UserLogin,
) -> User:
    """Validate credentials and return an authenticated user."""

    normalized_email = str(
        login_data.email
    ).strip().lower()

    user = get_user_by_email(
        database_session,
        normalized_email,
    )

    if user is None:
        raise InvalidCredentialsError

    if not verify_password(
        login_data.password,
        user.password_hash,
    ):
        raise InvalidCredentialsError

    if not user.is_active:
        raise InactiveAccountError

    return user


def issue_refresh_token(
    database_session: Session,
    *,
    user_id: int,
) -> str:
    """Create a refresh-token session and return its raw token."""

    raw_refresh_token = generate_refresh_token()

    expires_at = datetime.now(
        timezone.utc
    ) + timedelta(
        days=settings.refresh_token_expire_days
    )

    create_refresh_token_record(
        database_session,
        user_id=user_id,
        token_hash=hash_refresh_token(
            raw_refresh_token
        ),
        expires_at=expires_at,
    )

    return raw_refresh_token