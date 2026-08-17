from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.schemas.product_comparison import (
    ProductComparisonItemResponse,
    ProductComparisonResponse,
    ProductComparisonSummaryResponse,
)
from app.services.price_intelligence_service import (
    get_product_price_history_response,
)
from app.services.product_catalog_service import (
    get_product_detail,
    get_product_listings_response,
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


def _build_comparison_summary(
    comparison_items: list[ProductComparisonItemResponse],
) -> ProductComparisonSummaryResponse:
    """Build a transparent price summary across compared products."""

    price_candidates: list[
        tuple[int, str, Decimal, str]
    ] = []

    for item in comparison_items:
        if not item.listings.items:
            continue

        lowest_listing = min(
            item.listings.items,
            key=lambda listing: listing.current_price,
        )

        price_candidates.append(
            (
                item.product.id,
                item.product.name,
                lowest_listing.current_price,
                lowest_listing.currency,
            )
        )

    if not price_candidates:
        return ProductComparisonSummaryResponse()

    currencies = {
        candidate[3]
        for candidate in price_candidates
    }

    if len(currencies) != 1:
        return ProductComparisonSummaryResponse()

    sorted_candidates = sorted(
        price_candidates,
        key=lambda candidate: candidate[2],
    )

    cheapest = sorted_candidates[0]

    cheapest_product_id = cheapest[0]
    cheapest_product_name = cheapest[1]
    lowest_current_price = _round_money(
        cheapest[2]
    )
    currency = cheapest[3]

    price_gap: Decimal | None = None
    price_gap_percentage: Decimal | None = None

    if len(sorted_candidates) >= 2:
        highest_price = sorted_candidates[-1][2]

        price_gap = _round_money(
            highest_price - cheapest[2]
        )

        if cheapest[2] > 0:
            price_gap_percentage = _round_percentage(
                (
                    price_gap
                    / cheapest[2]
                )
                * Decimal("100")
            )

    return ProductComparisonSummaryResponse(
        cheapest_product_id=cheapest_product_id,
        cheapest_product_name=cheapest_product_name,
        lowest_current_price=lowest_current_price,
        currency=currency,
        price_gap=price_gap,
        price_gap_percentage=price_gap_percentage,
    )


def get_product_comparison_response(
    database_session: Session,
    product_ids: list[int],
) -> ProductComparisonResponse | None:
    """Return aggregated comparison data for selected products."""

    comparison_items: list[
        ProductComparisonItemResponse
    ] = []

    for product_id in product_ids:
        product = get_product_detail(
            database_session,
            product_id,
        )

        if product is None:
            return None

        listings = get_product_listings_response(
            database_session,
            product_id,
        )

        price_history = (
            get_product_price_history_response(
                database_session,
                product_id,
            )
        )

        if listings is None or price_history is None:
            return None

        comparison_items.append(
            ProductComparisonItemResponse(
                product=product,
                listings=listings,
                price_history=price_history,
            )
        )

    summary = _build_comparison_summary(
        comparison_items
    )

    return ProductComparisonResponse(
        total=len(comparison_items),
        items=comparison_items,
        summary=summary,
    )