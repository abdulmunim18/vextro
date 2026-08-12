from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class ORMResponse(BaseModel):
    """Base response schema supporting SQLAlchemy objects."""

    model_config = ConfigDict(from_attributes=True)


class PriceHistoryPointResponse(ORMResponse):
    """One historical price snapshot for a marketplace listing."""

    id: int
    listing_id: int
    price: Decimal
    original_price: Decimal | None
    currency: str
    is_available: bool
    source: str
    captured_at: datetime


class PriceSummaryResponse(BaseModel):
    """Calculated price statistics for one marketplace listing."""

    current_price: Decimal | None = None
    lowest_price: Decimal | None = None
    highest_price: Decimal | None = None
    average_price: Decimal | None = None
    price_change: Decimal | None = None
    price_change_percentage: Decimal | None = None
    first_captured_at: datetime | None = None
    last_captured_at: datetime | None = None


class ListingPriceHistoryResponse(BaseModel):
    """Historical pricing information for one marketplace listing."""

    listing_id: int
    platform_id: int
    seller_id: int | None

    listing_title: str
    product_url: str
    currency: str

    platform_name: str | None = None
    seller_name: str | None = None

    summary: PriceSummaryResponse

    points: list[PriceHistoryPointResponse] = Field(
        default_factory=list,
    )


class ProductPriceHistoryResponse(BaseModel):
    """Complete historical pricing response for a canonical product."""

    product_id: int
    product_name: str

    date_from: datetime | None = None
    date_to: datetime | None = None

    total_listings: int = Field(ge=0)
    total_points: int = Field(ge=0)

    listings: list[ListingPriceHistoryResponse] = Field(
        default_factory=list,
    )


class BuyTimeGuidanceResponse(BaseModel):
    """Transparent rule-based buy-now or wait guidance."""

    product_id: int
    product_name: str
    suggestion: str
    confidence: str
    current_lowest_price: Decimal | None
    recent_lowest_price: Decimal | None
    recent_average_price: Decimal | None
    observation_count: int = Field(ge=0)
    coverage_days: int = Field(ge=0)
    reasons: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    generated_at: datetime


class PersonalizedBuyTimeGuidanceResponse(
    BuyTimeGuidanceResponse
):
    """Buy/Wait guidance enriched by the user's active price alert."""

    is_personalized: bool
    personalization_source: Literal[
        "product_alert",
        "listing_alert",
        "no_active_alert",
    ]
    active_alert_count: int = Field(ge=0)
    alert_id: int | None = None
    alert_target_type: Literal["product", "listing"] | None = None
    target_listing_id: int | None = None
    target_price: Decimal | None = None
    target_currency: str | None = None
    evaluated_current_price: Decimal | None = None
    target_reached: bool | None = None
    target_gap_amount: Decimal | None = None
    target_gap_percentage: Decimal | None = None


class PriceForecastPoint(BaseModel):
    """One future price produced by a versioned forecasting model."""

    forecast_date: date
    predicted_price: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=2,
    )


class PriceForecastPublishRequest(BaseModel):
    """Validated hand-off contract used by the ML forecasting pipeline."""

    product_variant_id: int = Field(ge=1)
    model_name: str = Field(min_length=1, max_length=80)
    model_version: str = Field(min_length=1, max_length=80)
    horizon_days: int = Field(ge=1, le=90)
    currency: str = Field(default="PKR", min_length=3, max_length=3)
    training_observation_count: int = Field(ge=1)
    training_started_at: datetime | None = None
    training_ended_at: datetime | None = None
    mae: Decimal | None = Field(default=None, ge=0)
    rmse: Decimal | None = Field(default=None, ge=0)
    mape: Decimal | None = Field(default=None, ge=0)
    confidence: Literal["low", "medium", "high"]
    forecast: list[PriceForecastPoint] = Field(min_length=1, max_length=90)
    limitations: list[str] = Field(min_length=1, max_length=20)
    generated_at: datetime

    @field_validator("currency")
    @classmethod
    def normalize_forecast_currency(cls, value: str) -> str:
        normalized = value.strip().upper()

        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must contain exactly three letters")

        return normalized

    @field_validator("model_name", "model_version")
    @classmethod
    def strip_model_identifier(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("model identifiers cannot be blank")

        return normalized

    @field_validator("limitations")
    @classmethod
    def normalize_limitations(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values if value.strip()]
        return list(dict.fromkeys(normalized))

    @model_validator(mode="after")
    def validate_forecast_contract(self) -> Self:
        if self.horizon_days != len(self.forecast):
            raise ValueError("horizon_days must equal the number of forecast points")

        if self.mae is None and self.rmse is None and self.mape is None:
            raise ValueError("at least one forecast evaluation metric is required")

        if not self.limitations:
            raise ValueError("at least one forecast limitation is required")

        forecast_dates = [point.forecast_date for point in self.forecast]

        if forecast_dates != sorted(forecast_dates):
            raise ValueError("forecast points must be ordered by forecast_date")

        if len(set(forecast_dates)) != len(forecast_dates):
            raise ValueError("forecast dates must be unique")

        if any(value <= self.generated_at.date() for value in forecast_dates):
            raise ValueError("forecast dates must be after generated_at")

        if (
            self.training_started_at is not None
            and self.training_ended_at is not None
            and self.training_started_at > self.training_ended_at
        ):
            raise ValueError("training_started_at cannot be after training_ended_at")

        return self


class ProductPriceForecastResponse(BaseModel):
    """Latest forecast available for a canonical product."""

    status: Literal["available", "insufficient_data"]
    product_id: int
    product_name: str
    product_variant_id: int | None = None
    forecast_id: int | None = None
    model_name: str | None = None
    model_version: str | None = None
    horizon_days: int = Field(default=0, ge=0)
    currency: str | None = None
    training_observation_count: int = Field(default=0, ge=0)
    training_started_at: datetime | None = None
    training_ended_at: datetime | None = None
    mae: Decimal | None = None
    rmse: Decimal | None = None
    mape: Decimal | None = None
    confidence: Literal["low", "medium", "high"] | None = None
    forecast: list[PriceForecastPoint] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    generated_at: datetime | None = None


class PriceAlertCreate(BaseModel):
    """Request for creating a product or listing price alert."""

    canonical_product_id: int | None = Field(
        default=None,
        ge=1,
    )

    listing_id: int | None = Field(
        default=None,
        ge=1,
    )

    target_price: Decimal = Field(
        gt=0,
        max_digits=14,
        decimal_places=2,
    )

    currency: str = Field(
        default="PKR",
        min_length=3,
        max_length=3,
    )

    @field_validator("currency")
    @classmethod
    def normalize_currency(
        cls,
        value: str,
    ) -> str:
        """Normalize and validate the currency code."""

        normalized_currency = value.strip().upper()

        if (
            len(normalized_currency) != 3
            or not normalized_currency.isalpha()
        ):
            raise ValueError(
                "currency must contain exactly three letters"
            )

        return normalized_currency

    @model_validator(mode="after")
    def validate_exactly_one_target(self) -> Self:
        """Require either a product or listing target, never both."""

        has_product_target = self.canonical_product_id is not None
        has_listing_target = self.listing_id is not None

        if has_product_target == has_listing_target:
            raise ValueError(
                "Exactly one of canonical_product_id "
                "or listing_id must be provided"
            )

        return self


class PriceAlertUpdate(BaseModel):
    """Fields that may be changed on an existing alert."""

    target_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=14,
        decimal_places=2,
    )

    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )

    is_active: bool | None = None

    @field_validator("currency")
    @classmethod
    def normalize_optional_currency(
        cls,
        value: str | None,
    ) -> str | None:
        """Normalize an optional currency code."""

        if value is None:
            return None

        normalized_currency = value.strip().upper()

        if (
            len(normalized_currency) != 3
            or not normalized_currency.isalpha()
        ):
            raise ValueError(
                "currency must contain exactly three letters"
            )

        return normalized_currency

    @model_validator(mode="after")
    def require_at_least_one_update(self) -> Self:
        """Reject an empty PATCH request."""

        if (
            self.target_price is None
            and self.currency is None
            and self.is_active is None
        ):
            raise ValueError(
                "At least one field must be provided"
            )

        return self


class PriceAlertResponse(ORMResponse):
    """Authenticated consumer price-alert response."""

    id: int
    user_id: int

    canonical_product_id: int | None
    listing_id: int | None

    target_price: Decimal
    currency: str

    is_active: bool
    is_triggered: bool
    notification_count: int

    last_checked_at: datetime | None
    triggered_at: datetime | None
    last_notified_at: datetime | None

    created_at: datetime
    updated_at: datetime


class PriceAlertListResponse(BaseModel):
    """Alerts belonging to the authenticated consumer."""

    total: int = Field(ge=0)

    items: list[PriceAlertResponse] = Field(
        default_factory=list,
    )
