"""Security dependency for internal acquisition requests."""

from hmac import compare_digest
from typing import Annotated

from fastapi import (
    Header,
    HTTPException,
    status,
)

from app.core.config import settings


def require_ingestion_key(
    ingestion_key: Annotated[
        str | None,
        Header(alias="X-Ingestion-Key"),
    ] = None,
) -> None:
    """Allow ingestion only when the configured secret key matches."""

    configured_key = settings.ingestion_api_key

    if not configured_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "The acquisition ingestion service "
                "is not configured."
            ),
        )

    if (
        ingestion_key is None
        or not compare_digest(
            ingestion_key,
            configured_key,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid ingestion key.",
        )