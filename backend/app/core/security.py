from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash
import hashlib
import secrets
from app.core.config import settings


password_hasher = PasswordHash.recommended()
def validate_password_strength(password: str) -> str:
    """Validate the VEXTRO password policy."""

    if len(password) < 8:
        raise ValueError(
            "Password must contain at least 8 characters."
        )

    if len(password) > 128:
        raise ValueError(
            "Password cannot exceed 128 characters."
        )

    if not any(character.islower() for character in password):
        raise ValueError(
            "Password must contain at least one lowercase letter."
        )

    if not any(character.isupper() for character in password):
        raise ValueError(
            "Password must contain at least one uppercase letter."
        )

    if not any(character.isdigit() for character in password):
        raise ValueError(
            "Password must contain at least one number."
        )

    if not any(
        not character.isalnum()
        for character in password
    ):
        raise ValueError(
            "Password must contain at least one special character."
        )

    return password

def hash_password(plain_password: str) -> str:
    """Convert a plain password into a secure password hash."""

    return password_hasher.hash(plain_password)


def verify_password(
    plain_password: str,
    password_hash: str,
) -> bool:
    """Check whether a plain password matches the stored hash."""

    return password_hasher.verify(
        plain_password,
        password_hash,
    )


def create_access_token(
    *,
    user_id: int,
    roles: list[str],
) -> tuple[str, int]:
    """Create a signed JWT access token."""

    token_lifetime = timedelta(
        minutes=settings.access_token_expire_minutes
    )

    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + token_lifetime

    payload = {
        "sub": str(user_id),
        "roles": roles,
        "type": "access",
        "iat": issued_at,
        "exp": expires_at,
    }

    encoded_token = jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )

    return encoded_token, int(token_lifetime.total_seconds())
def generate_refresh_token() -> str:
    """Generate a cryptographically secure opaque refresh token."""

    return secrets.token_urlsafe(48)


def hash_refresh_token(refresh_token: str) -> str:
    """Create the database-safe SHA-256 hash of a refresh token."""

    return hashlib.sha256(
        refresh_token.encode("utf-8")
    ).hexdigest()