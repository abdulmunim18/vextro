"""Evaluate SME competitor risks when a listing price is captured."""

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business_product import BusinessProduct
from app.models.competitor_watchlist import CompetitorWatchlist
from app.models.organization import Organization
from app.repositories.notification_repository import create_notification


def evaluate_competitor_risk_alerts(
    database_session: Session,
    *,
    listing_id: int,
    competitor_price: Decimal,
    currency: str,
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
            create_notification(
                database_session,
                user_id=organization.owner_user_id,
                canonical_product_id=product.canonical_product_id,
                notification_type="competitor_risk",
                title="Competitor price risk detected",
                message=(
                    f"{product.name} is {gap_percentage}% above a "
                    f"monitored competitor at {currency} "
                    f"{competitor_price:,.2f}."
                ),
                action_path="/sme",
            )
            watchlist.last_alerted_at = datetime.now(timezone.utc)
            triggered += 1

        watchlist.last_risk_level = risk_level

    database_session.flush()
    return triggered
