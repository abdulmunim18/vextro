from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.category import Category
from app.models.platform import Platform
from sqlalchemy import func, select

def list_active_categories(
    database_session: Session,
) -> Sequence[Category]:
    """Return all active categories in alphabetical order."""

    statement = (
        select(Category)
        .where(Category.is_active.is_(True))
        .order_by(Category.name.asc())
    )

    return database_session.scalars(
        statement
    ).all()


def list_active_brands(
    database_session: Session,
) -> Sequence[Brand]:
    """Return all active brands in alphabetical order."""

    statement = (
        select(Brand)
        .where(Brand.is_active.is_(True))
        .order_by(
            func.lower(Brand.name).asc(),
            Brand.id.asc(),
    )
    )

    return database_session.scalars(
        statement
    ).all()


def list_active_platforms(
    database_session: Session,
) -> Sequence[Platform]:
    """Return all active marketplaces."""

    statement = (
        select(Platform)
        .where(Platform.is_active.is_(True))
        .order_by(Platform.id.asc())
    )

    return database_session.scalars(
        statement
    ).all()