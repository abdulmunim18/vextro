from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken


def create_refresh_token_record(
    database_session: Session,
    *,
    user_id: int,
    token_hash: str,
    expires_at: datetime,
) -> RefreshToken:
    """Store a hashed refresh-token session."""

    refresh_token_record = RefreshToken(
        user_id=user_id,
        token_hash=token_hash,
        expires_at=expires_at,
    )

    database_session.add(refresh_token_record)

    try:
        database_session.commit()
    except IntegrityError:
        database_session.rollback()
        raise

    database_session.refresh(refresh_token_record)

    return refresh_token_record


def get_refresh_token_by_hash(
    database_session: Session,
    token_hash: str,
) -> RefreshToken | None:
    """Return a refresh-token record and lock it for rotation."""

    statement = (
        select(RefreshToken)
        .where(RefreshToken.token_hash == token_hash)
        .with_for_update()
    )

    return database_session.scalar(statement)


def rotate_refresh_token_record(
    database_session: Session,
    *,
    current_token: RefreshToken,
    new_token_hash: str,
    new_expires_at: datetime,
) -> RefreshToken:
    """Revoke the old token and create a replacement atomically."""

    current_token.revoked_at = datetime.now(timezone.utc)

    new_token = RefreshToken(
        user_id=current_token.user_id,
        token_hash=new_token_hash,
        expires_at=new_expires_at,
    )

    database_session.add(new_token)

    try:
        database_session.commit()
    except IntegrityError:
        database_session.rollback()
        raise

    database_session.refresh(new_token)

    return new_token


def revoke_refresh_token_record(
    database_session: Session,
    refresh_token_record: RefreshToken,
) -> None:
    """Revoke an active refresh-token session."""

    if refresh_token_record.revoked_at is None:
        refresh_token_record.revoked_at = datetime.now(timezone.utc)
        database_session.commit()