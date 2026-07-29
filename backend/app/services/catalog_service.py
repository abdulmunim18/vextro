from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.category import Category
from app.models.platform import Platform
from app.repositories.catalog_repository import (
    list_active_brands,
    list_active_categories,
    list_active_platforms,
)


def get_categories(
    database_session: Session,
) -> Sequence[Category]:
    """Return categories available to application users."""

    return list_active_categories(
        database_session
    )


def get_brands(
    database_session: Session,
) -> Sequence[Brand]:
    """Return brands available to application users."""

    return list_active_brands(
        database_session
    )


def get_platforms(
    database_session: Session,
) -> Sequence[Platform]:
    """Return marketplaces supported by VEXTRO."""

    return list_active_platforms(
        database_session
    )