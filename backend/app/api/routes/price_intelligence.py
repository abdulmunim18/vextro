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

from app.api.dependencies.roles import consumer_or_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.price_intelligence import (
    BuyTimeGuidanceResponse,
    PersonalizedBuyTimeGuidanceResponse,
    ProductPriceForecastResponse,
    ProductPriceHistoryResponse,
)
from app.services.price_intelligence_service import (
    get_buy_time_guidance_response,
    get_personalized_buy_time_guidance_response,
    get_product_price_forecast_response,
    get_product_price_history_response,
)


router = APIRouter(
    prefix="/api/v1/products",
    tags=["price-intelligence"],
)


@router.get(
    "/{product_id}/forecast",
    response_model=ProductPriceForecastResponse,
)
def read_product_price_forecast_endpoint(
    product_id: int = Path(ge=1),
    database_session: Session = Depends(get_db),
) -> ProductPriceForecastResponse:
    """Return the latest validated ML forecast for an active product."""

    forecast = get_product_price_forecast_response(
        database_session,
        product_id,
    )

    if forecast is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return forecast


@router.get(
    "/{product_id}/buy-guidance",
    response_model=BuyTimeGuidanceResponse,
)
def read_buy_time_guidance_endpoint(
    product_id: int = Path(ge=1),
    database_session: Session = Depends(get_db),
) -> BuyTimeGuidanceResponse:
    """Return transparent buy-now, wait or stable guidance."""

    guidance = get_buy_time_guidance_response(
        database_session,
        product_id,
    )

    if guidance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return guidance


@router.get(
    "/{product_id}/personalized-buy-guidance",
    response_model=PersonalizedBuyTimeGuidanceResponse,
)
def read_personalized_buy_time_guidance_endpoint(
    product_id: int = Path(ge=1),
    current_user: User = Depends(consumer_or_admin),
    database_session: Session = Depends(get_db),
) -> PersonalizedBuyTimeGuidanceResponse:
    """Return Buy/Wait guidance aligned with the user's price target."""

    guidance = get_personalized_buy_time_guidance_response(
        database_session,
        product_id,
        user_id=current_user.id,
    )

    if guidance is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )

    return guidance


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
