from datetime import datetime

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