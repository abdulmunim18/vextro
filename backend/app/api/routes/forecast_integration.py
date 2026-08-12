"""Internal hand-off route for the independent ML forecasting module."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies.ingestion import require_ingestion_key
from app.core.database import get_db
from app.schemas.price_intelligence import (
    PriceForecastPublishRequest,
    ProductPriceForecastResponse,
)
from app.services.price_intelligence_service import publish_price_forecast


router = APIRouter(
    prefix="/api/v1/internal/ml",
    tags=["internal-ml"],
    dependencies=[Depends(require_ingestion_key)],
)


@router.post(
    "/price-forecasts",
    response_model=ProductPriceForecastResponse,
    status_code=status.HTTP_201_CREATED,
)
def publish_price_forecast_endpoint(
    payload: PriceForecastPublishRequest,
    database_session: Session = Depends(get_db),
) -> ProductPriceForecastResponse:
    """Publish a validated, metric-bearing forecast from the ML service."""

    try:
        result = publish_price_forecast(database_session, payload)
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active product variant not found",
        )

    return result
