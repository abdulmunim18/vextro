"""Evaluate SME competitor risks when a listing price is captured."""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business_product import BusinessProduct
from app.models.competitor_watchlist import CompetitorWatchlist
from app.models.notification_event import EVENT_TYPE_COMPETITOR_RISK
from app.models.organization import Organization
from app.services.notification_dispatcher import (
    NotificationEventRequest,
    dispatch_event,
)


def build_competitor_risk_event_key(
    *,
    watchlist_id: int,
    own_price: Decimal,
    competitor_price: Decimal,
) -> str:
    """Return the idempotency key for one competitor-risk transition.

    Risk alerts are edge-triggered on ``last_risk_level`` moving into
    ``high``, so a replayed observation is normally stopped by that latch.
    Keying additionally on both prices makes the dispatch itself
    idempotent: re-processing the exact same observation produces the same
    key and delivers nothing further.
    """

    return (
        "competitor_risk:"
        f"{watchlist_id}:{own_price}:{competitor_price}"
    )


def evaluate_competitor_risk_alerts(
    database_session: Session,
    *,
    listing_id: int,
    competitor_price: Decimal,
    currency: str,
    marketplace_name: str | None = None,
) -> int:
    """Notify organization owners only when risk crosses into high."""

    statement = (
        select(
            CompetitorWatchlist,
            BusinessProduct,
            Organization,
        )
        .join(
            BusinessProduct,
            BusinessProduct.id
            == CompetitorWatchlist.business_product_id,
        )
        .join(
            Organization,
            Organization.id
            == CompetitorWatchlist.organization_id,
        )
        .where(
            CompetitorWatchlist.listing_id == listing_id,
            CompetitorWatchlist.is_active.is_(True),
            BusinessProduct.is_active.is_(True),
            Organization.is_active.is_(True),
        )
        .with_for_update()
    )
    triggered = 0
    detected_at = datetime.now(timezone.utc)

    for watchlist, product, organization in database_session.execute(
        statement
    ):
        if product.selling_price is None or competitor_price <= 0:
            continue

        gap_percentage = (
            (product.selling_price - competitor_price)
            / competitor_price
            * Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        if gap_percentage >= watchlist.risk_threshold_percentage:
            risk_level = "high"
        elif gap_percentage > 0:
            risk_level = "medium"
        else:
            risk_level = "low"

        if risk_level == "high" and watchlist.last_risk_level != "high":
            event = dispatch_event(
                database_session,
                NotificationEventRequest(
                    user_id=organization.owner_user_id,
                    event_key=build_competitor_risk_event_key(
                        watchlist_id=watchlist.id,
                        own_price=product.selling_price,
                        competitor_price=competitor_price,
                    ),
                    event_type=EVENT_TYPE_COMPETITOR_RISK,
                    title="Competitor price risk detected",
                    message=(
                        f"{product.name} is {gap_percentage}% above a "
                        f"monitored competitor at {currency} "
                        f"{competitor_price:,.2f}."
                    ),
                    push_body=(
                        "A competitor price change may affect your "
                        "pricing position."
                    ),
                    action_path="/sme",
                    canonical_product_id=product.canonical_product_id,
                    payload={
                        "product_name": product.name,
                        "own_price": str(product.selling_price),
                        "competitor_price": str(competitor_price),
                        "price_gap_percentage": str(gap_percentage),
                        "risk_level": risk_level,
                        "currency": currency,
                        "marketplace": marketplace_name or "",
                        "listing_id": listing_id,
                        "organization_id": organization.id,
                        "observed_at": detected_at.isoformat(),
                    },
                ),
            )

            if event is not None:
                watchlist.last_alerted_at = detected_at
                triggered += 1

        watchlist.last_risk_level = risk_level

    database_session.flush()
    return triggered
