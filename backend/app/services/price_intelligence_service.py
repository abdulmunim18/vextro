from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.price_alert import PriceAlert
from app.models.price_forecast import PriceForecast
from app.repositories.price_alert_repository import (
    list_user_active_alerts_for_product,
)
from app.repositories.price_intelligence_repository import (
    ListingPriceHistoryRecord,
    get_product_for_price_history,
    get_active_variant_for_forecast,
    get_active_variant_forecast,
    get_latest_product_forecast,
    list_product_price_history,
    replace_active_variant_forecast,
)
from app.schemas.price_intelligence import (
    ListingPriceHistoryResponse,
    PriceHistoryPointResponse,
    PriceSummaryResponse,
    ProductPriceHistoryResponse,
    BuyTimeGuidanceResponse,
    PersonalizedBuyTimeGuidanceResponse,
    PriceForecastPoint,
    PriceForecastPublishRequest,
    ProductPriceForecastResponse,
)


MONEY_PRECISION = Decimal("0.01")
PERCENTAGE_PRECISION = Decimal("0.01")


def _build_price_forecast_response(
    product_id: int,
    product_name: str,
    forecast: PriceForecast | None,
) -> ProductPriceForecastResponse:
    """Map the stored ML hand-off into the stable public API contract."""

    if forecast is None:
        return ProductPriceForecastResponse(
            status="insufficient_data",
            product_id=product_id,
            product_name=product_name,
            limitations=[
                "No validated forecast has been published for this product yet.",
                "VEXTRO does not present missing predictions as guaranteed outcomes.",
            ],
        )

    points = [
        PriceForecastPoint.model_validate(point)
        for point in forecast.forecast_points
    ]

    return ProductPriceForecastResponse(
        status="available",
        product_id=product_id,
        product_name=product_name,
        product_variant_id=forecast.product_variant_id,
        forecast_id=forecast.id,
        model_name=forecast.model_name,
        model_version=forecast.model_version,
        horizon_days=forecast.horizon_days,
        currency=forecast.currency,
        training_observation_count=forecast.training_observation_count,
        training_started_at=forecast.training_started_at,
        training_ended_at=forecast.training_ended_at,
        mae=forecast.mae,
        rmse=forecast.rmse,
        mape=forecast.mape,
        confidence=forecast.confidence,
        forecast=points,
        limitations=list(forecast.limitations),
        generated_at=forecast.generated_at,
    )


def publish_price_forecast(
    database_session: Session,
    payload: PriceForecastPublishRequest,
) -> ProductPriceForecastResponse | None:
    """Validate and persist the latest output published by the ML module."""

    variant = get_active_variant_for_forecast(
        database_session,
        payload.product_variant_id,
    )

    if variant is None:
        return None

    active_forecast = get_active_variant_forecast(
        database_session,
        variant.id,
    )

    if (
        active_forecast is not None
        and payload.generated_at <= active_forecast.generated_at
    ):
        raise ValueError(
            "generated_at must be newer than the active variant forecast"
        )

    forecast = PriceForecast(
        product_variant_id=variant.id,
        model_name=payload.model_name,
        model_version=payload.model_version,
        horizon_days=payload.horizon_days,
        currency=payload.currency,
        training_observation_count=payload.training_observation_count,
        training_started_at=payload.training_started_at,
        training_ended_at=payload.training_ended_at,
        mae=payload.mae,
        rmse=payload.rmse,
        mape=payload.mape,
        confidence=payload.confidence,
        forecast_points=[
            point.model_dump(mode="json")
            for point in payload.forecast
        ],
        limitations=payload.limitations,
        generated_at=payload.generated_at,
        is_active=True,
    )

    try:
        replace_active_variant_forecast(database_session, forecast)
        database_session.commit()
    except Exception:
        database_session.rollback()
        raise
    database_session.refresh(forecast)

    product = get_product_for_price_history(
        database_session,
        variant.canonical_product_id,
    )

    if product is None:
        raise RuntimeError("Forecast variant lost its active canonical product")

    return _build_price_forecast_response(
        product.id,
        product.name,
        forecast,
    )


def get_product_price_forecast_response(
    database_session: Session,
    product_id: int,
) -> ProductPriceForecastResponse | None:
    """Return the newest validated forecast or an honest no-data response."""

    product = get_product_for_price_history(database_session, product_id)

    if product is None:
        return None

    forecast = get_latest_product_forecast(database_session, product_id)

    return _build_price_forecast_response(
        product.id,
        product.name,
        forecast,
    )


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


def get_buy_time_guidance_response(
    database_session: Session,
    product_id: int,
) -> BuyTimeGuidanceResponse | None:
    """Evaluate current price against available historical coverage."""

    history = get_product_price_history_response(
        database_session,
        product_id,
    )

    if history is None:
        return None

    current_prices = [
        listing.summary.current_price
        for listing in history.listings
        if listing.summary.current_price is not None
    ]
    all_points = [
        point
        for listing in history.listings
        for point in listing.points
        if point.is_available
    ]
    current_lowest = (
        min(current_prices)
        if current_prices
        else None
    )
    recent_lowest = (
        min(point.price for point in all_points)
        if all_points
        else None
    )
    recent_average = (
        _round_money(
            sum(
                (point.price for point in all_points),
                Decimal("0"),
            )
            / Decimal(len(all_points))
        )
        if all_points
        else None
    )
    coverage_days = 0

    if all_points:
        captured_times = [
            point.captured_at
            for point in all_points
        ]
        coverage_days = max(
            1,
            (max(captured_times) - min(captured_times)).days + 1,
        )

    reasons: list[str] = []
    limitations: list[str] = []

    if current_lowest is None:
        suggestion = "insufficient_data"
        reasons.append("No currently available marketplace offer exists.")
    elif recent_lowest is None or recent_average is None:
        suggestion = "insufficient_data"
        reasons.append(
            "Current offers exist, but historical observations are missing."
        )
    elif current_lowest <= recent_lowest * Decimal("1.02"):
        suggestion = "buy_now"
        reasons.append(
            "The lowest current offer is within 2% of the observed low."
        )
    elif (
        len(all_points) >= 5
        and current_lowest > recent_average * Decimal("1.03")
    ):
        suggestion = "wait"
        reasons.append(
            "The lowest current offer is more than 3% above the "
            "observed average."
        )
    else:
        suggestion = "price_stable"
        reasons.append(
            "The current offer is inside the normal observed price range."
        )

    observation_count = len(all_points)

    if observation_count >= 20 and coverage_days >= 30:
        confidence = "high"
    elif observation_count >= 5 and coverage_days >= 7:
        confidence = "medium"
    else:
        confidence = "low"
        limitations.append(
            "Limited observations or time coverage reduce confidence."
        )

    limitations.append(
        "This rule uses stored price history and is not a guaranteed "
        "forecast of future marketplace prices."
    )

    return BuyTimeGuidanceResponse(
        product_id=history.product_id,
        product_name=history.product_name,
        suggestion=suggestion,
        confidence=confidence,
        current_lowest_price=current_lowest,
        recent_lowest_price=recent_lowest,
        recent_average_price=recent_average,
        observation_count=observation_count,
        coverage_days=coverage_days,
        reasons=reasons,
        limitations=limitations,
        generated_at=datetime.now(timezone.utc),
    )


def _select_personalization_alert(
    alerts: list[PriceAlert],
) -> PriceAlert | None:
    """Prefer a product-wide alert, then an available listing alert."""

    product_alert = next(
        (
            alert
            for alert in alerts
            if alert.canonical_product_id is not None
        ),
        None,
    )

    if product_alert is not None:
        return product_alert

    available_listing_alert = next(
        (
            alert
            for alert in alerts
            if alert.listing is not None
            and alert.listing.is_available
        ),
        None,
    )

    return available_listing_alert or (alerts[0] if alerts else None)


def build_personalized_buy_time_guidance(
    guidance: BuyTimeGuidanceResponse,
    alerts: list[PriceAlert],
) -> PersonalizedBuyTimeGuidanceResponse:
    """Overlay a user's saved target price on transparent base guidance."""

    base_data = guidance.model_dump()

    if not alerts:
        base_data["reasons"] = [
            *guidance.reasons,
            "Create a price alert to personalize this guidance "
            "with your preferred buying price.",
        ]

        return PersonalizedBuyTimeGuidanceResponse(
            **base_data,
            is_personalized=False,
            personalization_source="no_active_alert",
            active_alert_count=0,
        )

    alert = _select_personalization_alert(alerts)

    if alert is None:
        raise RuntimeError("Expected at least one personalization alert")

    is_product_alert = alert.canonical_product_id is not None
    listing = alert.listing
    evaluated_current_price = (
        guidance.current_lowest_price
        if is_product_alert
        else (
            _round_money(listing.current_price)
            if listing is not None
            and listing.is_available
            and listing.current_price is not None
            else None
        )
    )
    target_price = _round_money(alert.target_price)
    reasons = list(guidance.reasons)
    limitations = list(guidance.limitations)
    target_reached: bool | None = None
    gap_amount: Decimal | None = None
    gap_percentage: Decimal | None = None

    if evaluated_current_price is None:
        suggestion = "insufficient_data"
        reasons.insert(
            0,
            "Your saved alert is active, but its current marketplace "
            "price is unavailable.",
        )
    else:
        target_reached = evaluated_current_price <= target_price
        gap_amount = _round_money(
            max(
                evaluated_current_price - target_price,
                Decimal("0"),
            )
        )
        gap_percentage = _round_percentage(
            (gap_amount / target_price) * Decimal("100")
        )

        if target_reached:
            suggestion = "buy_now"
            reasons.insert(
                0,
                "The evaluated current price has reached your saved "
                f"target of {alert.currency} {target_price}.",
            )
        else:
            suggestion = "wait"
            reasons.insert(
                0,
                "The evaluated current price is still "
                f"{alert.currency} {gap_amount} above your saved target.",
            )

    limitations.append(
        "Personalization uses your active price alert; it does not "
        "guarantee that the product will reach the target again."
    )

    base_data.update(
        suggestion=suggestion,
        reasons=reasons,
        limitations=limitations,
    )

    return PersonalizedBuyTimeGuidanceResponse(
        **base_data,
        is_personalized=True,
        personalization_source=(
            "product_alert" if is_product_alert else "listing_alert"
        ),
        active_alert_count=len(alerts),
        alert_id=alert.id,
        alert_target_type=(
            "product" if is_product_alert else "listing"
        ),
        target_listing_id=alert.listing_id,
        target_price=target_price,
        target_currency=alert.currency,
        evaluated_current_price=evaluated_current_price,
        target_reached=target_reached,
        target_gap_amount=gap_amount,
        target_gap_percentage=gap_percentage,
    )


def get_personalized_buy_time_guidance_response(
    database_session: Session,
    product_id: int,
    *,
    user_id: int,
) -> PersonalizedBuyTimeGuidanceResponse | None:
    """Return target-aware guidance for an authenticated consumer."""

    guidance = get_buy_time_guidance_response(
        database_session,
        product_id,
    )

    if guidance is None:
        return None

    alerts = list_user_active_alerts_for_product(
        database_session,
        user_id=user_id,
        product_id=product_id,
    )

    return build_personalized_buy_time_guidance(
        guidance,
        alerts,
    )
