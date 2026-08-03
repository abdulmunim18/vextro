from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.canonical_product import CanonicalProduct
from app.models.price_alert import PriceAlert
from app.models.product_listing import ProductListing


def get_active_product_target(
    database_session: Session,
    product_id: int,
) -> CanonicalProduct | None:
    """Return an active canonical product that may receive an alert."""

    query = select(CanonicalProduct).where(
        CanonicalProduct.id == product_id,
        CanonicalProduct.is_active.is_(True),
    )

    return database_session.scalar(query)


def get_listing_target(
    database_session: Session,
    listing_id: int,
) -> ProductListing | None:
    """Return a marketplace listing that may receive an alert."""

    query = select(ProductListing).where(
        ProductListing.id == listing_id,
    )

    return database_session.scalar(query)


def list_user_price_alerts(
    database_session: Session,
    user_id: int,
) -> list[PriceAlert]:
    """Return all price alerts owned by one user."""

    query = (
        select(PriceAlert)
        .where(
            PriceAlert.user_id == user_id,
        )
        .order_by(
            PriceAlert.created_at.desc(),
            PriceAlert.id.desc(),
        )
    )

    return list(
        database_session.scalars(query).all()
    )


def get_user_price_alert(
    database_session: Session,
    *,
    user_id: int,
    alert_id: int,
) -> PriceAlert | None:
    """Return an alert only when it belongs to the supplied user."""

    query = select(PriceAlert).where(
        PriceAlert.id == alert_id,
        PriceAlert.user_id == user_id,
    )

    return database_session.scalar(query)


def find_active_duplicate_alert(
    database_session: Session,
    *,
    user_id: int,
    canonical_product_id: int | None = None,
    listing_id: int | None = None,
    exclude_alert_id: int | None = None,
) -> PriceAlert | None:
    """Find an active alert for the same user and target."""

    query = select(PriceAlert).where(
        PriceAlert.user_id == user_id,
        PriceAlert.is_active.is_(True),
    )

    if canonical_product_id is not None:
        query = query.where(
            PriceAlert.canonical_product_id
            == canonical_product_id,
        )

    elif listing_id is not None:
        query = query.where(
            PriceAlert.listing_id == listing_id,
        )

    else:
        return None

    if exclude_alert_id is not None:
        query = query.where(
            PriceAlert.id != exclude_alert_id,
        )

    return database_session.scalar(query)


def create_price_alert(
    database_session: Session,
    *,
    user_id: int,
    canonical_product_id: int | None,
    listing_id: int | None,
    target_price: Decimal,
    currency: str,
) -> PriceAlert:
    """Create and flush a new price alert."""

    alert = PriceAlert(
        user_id=user_id,
        canonical_product_id=canonical_product_id,
        listing_id=listing_id,
        target_price=target_price,
        currency=currency,
    )

    database_session.add(alert)
    database_session.flush()

    return alert


def update_price_alert(
    database_session: Session,
    alert: PriceAlert,
    *,
    target_price: Decimal | None = None,
    currency: str | None = None,
    is_active: bool | None = None,
) -> PriceAlert:
    """Apply permitted changes to an existing price alert."""

    if target_price is not None:
        alert.target_price = target_price

    if currency is not None:
        alert.currency = currency

    if is_active is not None:
        alert.is_active = is_active

        if is_active:
            alert.is_triggered = False
            alert.triggered_at = None

    database_session.flush()

    return alert


def deactivate_price_alert(
    database_session: Session,
    alert: PriceAlert,
) -> PriceAlert:
    """Deactivate an alert without deleting its historical record."""

    alert.is_active = False

    database_session.flush()

    return alert