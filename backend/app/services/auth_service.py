import logging
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    generate_email_otp,
    generate_opaque_token,
    generate_refresh_token,
    hash_auth_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.user import User
from app.repositories.refresh_token_repository import (
    create_refresh_token_record,
    get_refresh_token_by_hash,
    revoke_refresh_token_record,
    rotate_refresh_token_record,
)
from app.repositories.auth_token_repository import (
    consume_auth_token,
    create_auth_token,
    get_active_auth_token_by_hash,
    get_latest_active_auth_token_by_email,
    increment_auth_token_attempts,
    invalidate_auth_tokens,
    revoke_all_refresh_tokens,
)
from app.repositories.user_repository import (
    create_user,
    get_role_by_name,
    get_user_by_email,
    get_user_by_id,
)
from app.schemas.auth import UserLogin, UserRegister
from app.services.auth_email_service import (
    send_password_reset_email,
    send_verification_otp_email,
)


logger = logging.getLogger(__name__)


class EmailAlreadyRegisteredError(Exception):
    """Raised when an email already belongs to another user."""


class RegistrationRoleNotFoundError(Exception):
    """Raised when the selected registration role does not exist."""


class InvalidCredentialsError(Exception):
    """Raised when login credentials are incorrect."""


class InactiveAccountError(Exception):
    """Raised when the account has been deactivated."""


class UnverifiedAccountError(Exception):
    """Raised when a password login is attempted before verification."""


class InvalidOrExpiredAuthTokenError(Exception):
    """Raised when an OTP or reset token cannot be accepted."""


class TooManyOtpAttemptsError(Exception):
    """Raised after the verification attempt budget is exhausted."""


class OtpResendCooldownError(Exception):
    """Raised when another OTP is requested too soon."""


class InvalidRefreshTokenError(Exception):
    """Raised when a refresh token is invalid or revoked."""


class ExpiredRefreshTokenError(Exception):
    """Raised when a refresh token has expired."""


def start_registration(
    database_session: Session,
    registration_data: UserRegister,
) -> tuple[str, int]:
    """Persist a pending signup and email its one-time code."""

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

    pending_registration = get_latest_active_auth_token_by_email(
        database_session,
        purpose="email_verification",
        email=normalized_email,
    )
    if pending_registration is not None:
        age_seconds = (
            datetime.now(timezone.utc) - pending_registration.created_at
        ).total_seconds()
        if age_seconds < settings.email_otp_resend_cooldown_seconds:
            raise OtpResendCooldownError

    invalidate_auth_tokens(
        database_session,
        purpose="email_verification",
        email=normalized_email,
    )

    otp = generate_email_otp()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.email_otp_expire_minutes
    )
    create_auth_token(
        database_session,
        purpose="email_verification",
        token_hash=hash_auth_token(f"{normalized_email}:{otp}"),
        email=normalized_email,
        expires_at=expires_at,
        payload={
            "full_name": registration_data.full_name,
            "password_hash": hash_password(registration_data.password),
            "account_type": selected_role.name,
        },
    )

    try:
        send_verification_otp_email(
            recipient=normalized_email,
            full_name=registration_data.full_name,
            otp=otp,
            expires_minutes=settings.email_otp_expire_minutes,
        )
    except Exception:
        invalidate_auth_tokens(
            database_session,
            purpose="email_verification",
            email=normalized_email,
        )
        raise

    return normalized_email, settings.email_otp_expire_minutes * 60


def verify_registration_otp(
    database_session: Session,
    *,
    email: str,
    otp: str,
) -> User:
    """Create a verified account after a valid OTP is supplied."""

    normalized_email = email.strip().lower()
    if get_user_by_email(database_session, normalized_email) is not None:
        raise EmailAlreadyRegisteredError

    record = get_latest_active_auth_token_by_email(
        database_session,
        purpose="email_verification",
        email=normalized_email,
    )
    if record is None:
        raise InvalidOrExpiredAuthTokenError

    if record.attempts >= settings.email_otp_max_attempts:
        consume_auth_token(database_session, record)
        raise TooManyOtpAttemptsError

    if not secrets.compare_digest(
        record.token_hash,
        hash_auth_token(f"{normalized_email}:{otp}"),
    ):
        attempts = increment_auth_token_attempts(database_session, record)
        if attempts >= settings.email_otp_max_attempts:
            consume_auth_token(database_session, record)
            raise TooManyOtpAttemptsError
        raise InvalidOrExpiredAuthTokenError

    role = get_role_by_name(
        database_session,
        str(record.payload["account_type"]),
    )
    if role is None:
        raise RegistrationRoleNotFoundError

    try:
        user = create_user(
            database_session,
            full_name=str(record.payload["full_name"]),
            email=normalized_email,
            password_hash=str(record.payload["password_hash"]),
            role=role,
            is_verified=True,
        )
    except IntegrityError as error:
        raise EmailAlreadyRegisteredError from error

    consume_auth_token(database_session, record)
    return user


def resend_registration_otp(
    database_session: Session,
    *,
    email: str,
) -> tuple[str, int]:
    """Replace the active verification code while preserving signup data."""

    normalized_email = email.strip().lower()
    if get_user_by_email(database_session, normalized_email) is not None:
        raise EmailAlreadyRegisteredError

    record = get_latest_active_auth_token_by_email(
        database_session,
        purpose="email_verification",
        email=normalized_email,
    )
    if record is None:
        raise InvalidOrExpiredAuthTokenError

    age_seconds = (
        datetime.now(timezone.utc) - record.created_at
    ).total_seconds()
    if age_seconds < settings.email_otp_resend_cooldown_seconds:
        raise OtpResendCooldownError

    otp = generate_email_otp()
    invalidate_auth_tokens(
        database_session,
        purpose="email_verification",
        email=normalized_email,
    )
    create_auth_token(
        database_session,
        purpose="email_verification",
        token_hash=hash_auth_token(f"{normalized_email}:{otp}"),
        email=normalized_email,
        expires_at=datetime.now(timezone.utc) + timedelta(
            minutes=settings.email_otp_expire_minutes
        ),
        payload=dict(record.payload),
    )
    try:
        send_verification_otp_email(
            recipient=normalized_email,
            full_name=str(record.payload["full_name"]),
            otp=otp,
            expires_minutes=settings.email_otp_expire_minutes,
        )
    except Exception:
        invalidate_auth_tokens(
            database_session,
            purpose="email_verification",
            email=normalized_email,
        )
        raise
    return normalized_email, settings.email_otp_expire_minutes * 60


def request_password_reset(
    database_session: Session,
    *,
    email: str,
) -> None:
    """Create and email a reset link without revealing account existence."""

    normalized_email = email.strip().lower()
    user = get_user_by_email(database_session, normalized_email)
    if user is None or not user.is_active:
        return

    raw_token = generate_opaque_token()
    invalidate_auth_tokens(
        database_session,
        purpose="password_reset",
        user_id=user.id,
    )
    create_auth_token(
        database_session,
        purpose="password_reset",
        token_hash=hash_auth_token(raw_token),
        email=user.email,
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(
            minutes=settings.password_reset_expire_minutes
        ),
    )
    reset_url = (
        f"{settings.frontend_base_url_normalized}/reset-password"
        f"?token={quote(raw_token)}"
    )
    try:
        send_password_reset_email(
            recipient=user.email,
            full_name=user.full_name,
            reset_url=reset_url,
            expires_minutes=settings.password_reset_expire_minutes,
        )
    except Exception as error:
        logger.error(
            "auth.password_reset_email_failed user_id=%s error=%s",
            user.id,
            type(error).__name__,
        )


def reset_password(
    database_session: Session,
    *,
    token: str,
    new_password: str,
) -> None:
    """Apply a new password using a valid single-use reset token."""

    record = get_active_auth_token_by_hash(
        database_session,
        purpose="password_reset",
        token_hash=hash_auth_token(token),
    )
    if record is None or record.user_id is None:
        raise InvalidOrExpiredAuthTokenError

    user = get_user_by_id(database_session, record.user_id)
    if user is None or not user.is_active:
        raise InvalidOrExpiredAuthTokenError

    user.password_hash = hash_password(new_password)
    database_session.add(user)
    database_session.commit()
    consume_auth_token(database_session, record)
    revoke_all_refresh_tokens(database_session, user_id=user.id)


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

    if user.password_hash is None or not verify_password(
        login_data.password,
        user.password_hash,
    ):
        raise InvalidCredentialsError

    if not user.is_active:
        raise InactiveAccountError

    if not user.is_verified:
        raise UnverifiedAccountError

    return user


def issue_refresh_token(
    database_session: Session,
    *,
    user_id: int,
) -> str:
    """Create a refresh-token session and return the raw token."""

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


def refresh_user_session(
    database_session: Session,
    *,
    raw_refresh_token: str,
) -> tuple[User, str]:
    """Rotate a valid refresh token and return a new session."""

    current_token = get_refresh_token_by_hash(
        database_session,
        hash_refresh_token(raw_refresh_token),
    )

    if current_token is None:
        database_session.rollback()
        raise InvalidRefreshTokenError

    if current_token.revoked_at is not None:
        database_session.rollback()
        raise InvalidRefreshTokenError

    current_time = datetime.now(timezone.utc)

    if current_token.expires_at <= current_time:
        database_session.rollback()
        raise ExpiredRefreshTokenError

    user = get_user_by_id(
        database_session,
        current_token.user_id,
    )

    if user is None:
        database_session.rollback()
        raise InvalidRefreshTokenError

    if not user.is_active:
        database_session.rollback()
        raise InactiveAccountError

    new_raw_refresh_token = generate_refresh_token()

    new_expires_at = current_time + timedelta(
        days=settings.refresh_token_expire_days
    )

    rotate_refresh_token_record(
        database_session,
        current_token=current_token,
        new_token_hash=hash_refresh_token(
            new_raw_refresh_token
        ),
        new_expires_at=new_expires_at,
    )

    return user, new_raw_refresh_token


def logout_user_session(
    database_session: Session,
    *,
    raw_refresh_token: str,
) -> None:
    """Revoke the supplied refresh-token session."""

    refresh_token_record = get_refresh_token_by_hash(
        database_session,
        hash_refresh_token(raw_refresh_token),
    )

    if refresh_token_record is None:
        database_session.rollback()
        return

    revoke_refresh_token_record(
        database_session,
        refresh_token_record,
    )
