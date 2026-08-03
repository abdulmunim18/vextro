from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.price_intelligence import (
    ProductPriceHistoryResponse,
)
from app.services.price_intelligence_service import (
    get_product_price_history_response,
)


router = APIRouter(
    prefix="/api/v1/products",
    tags=["price-intelligence"],
)


@router.get(
    "/{product_id}/price-history",
    response_model=ProductPriceHistoryResponse,
    status_code=status.HTTP_200_OK,
)
def read_product_price_history(
    product_id: int = Path(
        ...,
        ge=1,
        description="Canonical product ID.",
    ),
    date_from: datetime | None = Query(
        default=None,
        description=(
            "Include snapshots captured at or after this ISO 8601 date."
        ),
    ),
    date_to: datetime | None = Query(
        default=None,
        description=(
            "Include snapshots captured at or before this ISO 8601 date."
        ),
    ),
    database_session: Session = Depends(get_db),
) -> ProductPriceHistoryResponse:
    """Return chart-ready historical prices for one active product."""

    try:
        result = get_product_price_history_response(
            database_session,
            product_id,
            date_from=date_from,
            date_to=date_to,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return result