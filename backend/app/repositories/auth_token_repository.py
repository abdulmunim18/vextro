from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.auth_token import AuthToken
from app.models.refresh_token import RefreshToken


def create_auth_token(
    database_session: Session,
    *,
    purpose: str,
    token_hash: str,
    expires_at: datetime,
    email: str | None = None,
    user_id: int | None = None,
    payload: dict | None = None,
) -> AuthToken:
    record = AuthToken(
        purpose=purpose,
        token_hash=token_hash,
        email=email,
        user_id=user_id,
        payload=payload or {},
        expires_at=expires_at,
    )
    database_session.add(record)
    database_session.commit()
    database_session.refresh(record)
    return record


def get_active_auth_token_by_hash(
    database_session: Session,
    *,
    purpose: str,
    token_hash: str,
) -> AuthToken | None:
    now = datetime.now(timezone.utc)
    return database_session.scalar(
        select(AuthToken).where(
            AuthToken.purpose == purpose,
            AuthToken.token_hash == token_hash,
            AuthToken.consumed_at.is_(None),
            AuthToken.expires_at > now,
        )
    )


def get_latest_active_auth_token_by_email(
    database_session: Session,
    *,
    purpose: str,
    email: str,
) -> AuthToken | None:
    now = datetime.now(timezone.utc)
    return database_session.scalar(
        select(AuthToken)
        .where(
            AuthToken.purpose == purpose,
            AuthToken.email == email,
            AuthToken.consumed_at.is_(None),
            AuthToken.expires_at > now,
        )
        .order_by(AuthToken.created_at.desc(), AuthToken.id.desc())
        .limit(1)
    )


def invalidate_auth_tokens(
    database_session: Session,
    *,
    purpose: str,
    email: str | None = None,
    user_id: int | None = None,
) -> None:
    conditions = [
        AuthToken.purpose == purpose,
        AuthToken.consumed_at.is_(None),
    ]
    if email is not None:
        conditions.append(AuthToken.email == email)
    if user_id is not None:
        conditions.append(AuthToken.user_id == user_id)

    database_session.execute(
        update(AuthToken)
        .where(*conditions)
        .values(consumed_at=datetime.now(timezone.utc))
    )
    database_session.commit()


def consume_auth_token(
    database_session: Session,
    record: AuthToken,
) -> None:
    record.consumed_at = datetime.now(timezone.utc)
    database_session.add(record)
    database_session.commit()


def increment_auth_token_attempts(
    database_session: Session,
    record: AuthToken,
) -> int:
    record.attempts += 1
    database_session.add(record)
    database_session.commit()
    return record.attempts


def revoke_all_refresh_tokens(
    database_session: Session,
    *,
    user_id: int,
) -> None:
    database_session.execute(
        update(RefreshToken)
        .where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    database_session.commit()
