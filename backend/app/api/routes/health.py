from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings
from app.core.database import engine


router = APIRouter(tags=["Health"])


@router.get("/health")
def application_health() -> dict[str, str]:
    """Check whether the FastAPI application is running."""

    return {
        "status": "healthy",
        "project": settings.app_name,
        "version": settings.app_version,
    }


@router.get("/database/health")
def database_health() -> dict[str, str]:
    """Check whether the application can connect to PostgreSQL."""

    query = text(
        """
        SELECT
            current_database() AS database_name,
            current_user AS connected_user,
            version() AS postgres_version
        """
    )

    try:
        with engine.connect() as connection:
            result = connection.execute(query).mappings().one()

        return {
            "status": "healthy",
            "database_name": result["database_name"],
            "connected_user": result["connected_user"],
            "postgres_version": result["postgres_version"],
        }

    except SQLAlchemyError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection is unavailable.",
        ) from error