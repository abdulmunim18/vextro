from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.price_intelligence import (
    ProductPriceHistoryResponse,
)
from app.schemas.product_catalog import (
    ProductDetailResponse,
    ProductListingsResponse,
)


class ProductComparisonItemResponse(BaseModel):
    """Complete comparison data for one canonical product."""

    product: ProductDetailResponse
    listings: ProductListingsResponse
    price_history: ProductPriceHistoryResponse


class ProductComparisonSummaryResponse(BaseModel):
    """Transparent price-based summary for compared products."""

    cheapest_product_id: int | None = None
    cheapest_product_name: str | None = None
    lowest_current_price: Decimal | None = None
    currency: str | None = None

    price_gap: Decimal | None = None
    price_gap_percentage: Decimal | None = None


class ProductComparisonResponse(BaseModel):
    """Side-by-side comparison response for selected products."""

    total: int = Field(
        ge=2,
        le=3,
    )

    items: list[ProductComparisonItemResponse] = Field(
        min_length=2,
        max_length=3,
    )

    summary: ProductComparisonSummaryResponse