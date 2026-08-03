from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.repositories.price_intelligence_repository import (
    ListingPriceHistoryRecord,
    get_product_for_price_history,
    list_product_price_history,
)
from app.schemas.price_intelligence import (
    ListingPriceHistoryResponse,
    PriceHistoryPointResponse,
    PriceSummaryResponse,
    ProductPriceHistoryResponse,
)


MONEY_PRECISION = Decimal("0.01")
PERCENTAGE_PRECISION = Decimal("0.01")


def _round_money(value: Decimal) -> Decimal:
    """Round a monetary value to two decimal places."""

    return value.quantize(
        MONEY_PRECISION,
        rounding=ROUND_HALF_UP,
    )


def _round_percentage(value: Decimal) -> Decimal:
    """Round a percentage value to two decimal places."""

    return value.quantize(
        PERCENTAGE_PRECISION,
        rounding=ROUND_HALF_UP,
    )


def _build_price_summary(
    record: ListingPriceHistoryRecord,
) -> PriceSummaryResponse:
    """Calculate pricing statistics for one marketplace listing."""

    current_price = _round_money(
        record.listing.current_price
    )

    if not record.points:
        return PriceSummaryResponse(
            current_price=current_price,
        )

    prices = [
        point.price
        for point in record.points
    ]

    first_price = prices[0]

    lowest_price = _round_money(
        min(prices)
    )

    highest_price = _round_money(
        max(prices)
    )

    average_price = _round_money(
        sum(
            prices,
            Decimal("0.00"),
        )
        / Decimal(len(prices))
    )

    price_change = _round_money(
        current_price - first_price
    )

    price_change_percentage: Decimal | None = None

    if first_price > 0:
        price_change_percentage = _round_percentage(
            (
                price_change
                / first_price
            )
            * Decimal("100")
        )

    return PriceSummaryResponse(
        current_price=current_price,
        lowest_price=lowest_price,
        highest_price=highest_price,
        average_price=average_price,
        price_change=price_change,
        price_change_percentage=price_change_percentage,
        first_captured_at=record.points[0].captured_at,
        last_captured_at=record.points[-1].captured_at,
    )


def get_product_price_history_response(
    database_session: Session,
    product_id: int,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> ProductPriceHistoryResponse | None:
    """Return chart-ready price history for one active product."""

    if (
        date_from is not None
        and date_to is not None
        and date_from > date_to
    ):
        raise ValueError(
            "date_from cannot be later than date_to"
        )

    product = get_product_for_price_history(
        database_session,
        product_id,
    )

    if product is None:
        return None

    records = list_product_price_history(
        database_session,
        product_id,
        date_from=date_from,
        date_to=date_to,
    )

    listing_responses: list[
        ListingPriceHistoryResponse
    ] = []

    total_points = 0

    for record in records:
        points = [
            PriceHistoryPointResponse.model_validate(point)
            for point in record.points
        ]

        total_points += len(points)

        listing_responses.append(
            ListingPriceHistoryResponse(
                listing_id=record.listing.id,
                platform_id=record.listing.platform_id,
                seller_id=record.listing.seller_id,
                listing_title=record.listing.title,
                product_url=record.listing.product_url,
                currency=record.listing.currency,
                platform_name=record.platform_name,
                seller_name=record.seller_name,
                summary=_build_price_summary(record),
                points=points,
            )
        )

    return ProductPriceHistoryResponse(
        product_id=product.id,
        product_name=product.name,
        date_from=date_from,
        date_to=date_to,
        total_listings=len(listing_responses),
        total_points=total_points,
        listings=listing_responses,
    )