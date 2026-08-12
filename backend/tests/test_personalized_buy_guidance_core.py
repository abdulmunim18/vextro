from datetime import datetime, timezone
from decimal import Decimal

from app.models.price_alert import PriceAlert
from app.models.product_listing import ProductListing
from app.schemas.price_intelligence import BuyTimeGuidanceResponse
from app.services.price_intelligence_service import (
    build_personalized_buy_time_guidance,
)


def make_guidance(
    *,
    current_price: Decimal = Decimal("125000.00"),
    suggestion: str = "buy_now",
) -> BuyTimeGuidanceResponse:
    """Create deterministic base guidance for personalization tests."""

    return BuyTimeGuidanceResponse(
        product_id=1,
        product_name="Test phone",
        suggestion=suggestion,
        confidence="medium",
        current_lowest_price=current_price,
        recent_lowest_price=Decimal("120000.00"),
        recent_average_price=Decimal("123000.00"),
        observation_count=12,
        coverage_days=10,
        reasons=["Base historical reason."],
        limitations=["Base historical limitation."],
        generated_at=datetime(2026, 8, 12, tzinfo=timezone.utc),
    )


def make_product_alert(
    target_price: Decimal,
) -> PriceAlert:
    """Create an in-memory active product alert."""

    return PriceAlert(
        id=10,
        user_id=20,
        canonical_product_id=1,
        target_price=target_price,
        currency="PKR",
        is_active=True,
    )


def test_no_active_alert_keeps_base_guidance_and_explains_setup() -> None:
    """Users without a target should receive transparent generic guidance."""

    result = build_personalized_buy_time_guidance(
        make_guidance(),
        [],
    )

    assert result.is_personalized is False
    assert result.personalization_source == "no_active_alert"
    assert result.active_alert_count == 0
    assert result.suggestion == "buy_now"
    assert "Create a price alert" in result.reasons[-1]


def test_unreached_product_target_overrides_generic_buy_signal() -> None:
    """A user's lower target should produce personalized wait guidance."""

    result = build_personalized_buy_time_guidance(
        make_guidance(suggestion="buy_now"),
        [make_product_alert(Decimal("115000.00"))],
    )

    assert result.is_personalized is True
    assert result.personalization_source == "product_alert"
    assert result.suggestion == "wait"
    assert result.target_reached is False
    assert result.target_gap_amount == Decimal("10000.00")
    assert result.target_gap_percentage == Decimal("8.70")
    assert result.evaluated_current_price == Decimal("125000.00")


def test_reached_product_target_returns_buy_now() -> None:
    """A current price at the saved target should be actionable."""

    result = build_personalized_buy_time_guidance(
        make_guidance(
            current_price=Decimal("110000.00"),
            suggestion="wait",
        ),
        [make_product_alert(Decimal("110000.00"))],
    )

    assert result.suggestion == "buy_now"
    assert result.target_reached is True
    assert result.target_gap_amount == Decimal("0.00")
    assert result.target_gap_percentage == Decimal("0.00")


def test_listing_alert_uses_its_listing_price() -> None:
    """Listing targets must not be evaluated against another cheaper offer."""

    listing = ProductListing(
        id=30,
        current_price=Decimal("90000.00"),
        currency="PKR",
        is_available=True,
    )
    alert = PriceAlert(
        id=11,
        user_id=20,
        listing_id=listing.id,
        target_price=Decimal("95000.00"),
        currency="PKR",
        is_active=True,
    )
    alert.listing = listing

    result = build_personalized_buy_time_guidance(
        make_guidance(current_price=Decimal("80000.00")),
        [alert],
    )

    assert result.personalization_source == "listing_alert"
    assert result.alert_target_type == "listing"
    assert result.target_listing_id == listing.id
    assert result.evaluated_current_price == Decimal("90000.00")
    assert result.target_reached is True
    assert result.suggestion == "buy_now"
