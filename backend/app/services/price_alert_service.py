from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from datetime import UTC, datetime
from app.models.price_alert import PriceAlert
from decimal import Decimal
from app.repositories.price_alert_repository import (
    create_price_alert,
    deactivate_price_alert,
    find_active_duplicate_alert,
    get_active_product_target,
    update_price_alert,
    get_listing_target,
    get_user_price_alert,
    list_user_price_alerts,
    list_active_price_alerts_for_capture,
)
from app.schemas.price_intelligence import (
    PriceAlertCreate,
    PriceAlertListResponse,
    PriceAlertResponse,
    PriceAlertUpdate,
)
def evaluate_price_alerts_for_capture(
    database_session: Session,
    *,
    canonical_product_id: int,
    listing_id: int,
    current_price: Decimal,
    currency: str,
) -> int:
    """Evaluate active alerts affected by one marketplace price capture."""

    alerts = list_active_price_alerts_for_capture(
        database_session,
        canonical_product_id=canonical_product_id,
        listing_id=listing_id,
        currency=currency,
    )

    if not alerts:
        return 0

    checked_at = datetime.now(UTC)
    triggered_count = 0

    for alert in alerts:
        alert.last_checked_at = checked_at

        if alert.is_triggered:
            continue

        if current_price > alert.target_price:
            continue

        alert.is_triggered = True
        alert.triggered_at = checked_at
        triggered_count += 1

    database_session.flush()

    return triggered_count


class PriceAlertTargetNotFoundError(Exception):
    """Raised when the requested product or listing does not exist."""


class PriceAlertAlreadyExistsError(Exception):
    """Raised when a user already has an active alert for the target."""


class PriceAlertNotFoundError(Exception):
    """Raised when an alert does not exist or belongs to another user."""


def _validate_alert_target(
    database_session: Session,
    payload: PriceAlertCreate,
) -> None:
    """Verify that the selected alert target exists."""

    if payload.canonical_product_id is not None:
        product = get_active_product_target(
            database_session,
            payload.canonical_product_id,
        )

        if product is None:
            raise PriceAlertTargetNotFoundError(
                "Product not found"
            )

        return

    if payload.listing_id is not None:
        listing = get_listing_target(
            database_session,
            payload.listing_id,
        )

        if listing is None:
            raise PriceAlertTargetNotFoundError(
                "Product listing not found"
            )


def _check_duplicate_active_alert(
    database_session: Session,
    *,
    user_id: int,
    canonical_product_id: int | None,
    listing_id: int | None,
    exclude_alert_id: int | None = None,
) -> None:
    """Reject another active alert for the same user and target."""

    duplicate_alert = find_active_duplicate_alert(
        database_session,
        user_id=user_id,
        canonical_product_id=canonical_product_id,
        listing_id=listing_id,
        exclude_alert_id=exclude_alert_id,
    )

    if duplicate_alert is not None:
        raise PriceAlertAlreadyExistsError(
            "An active price alert already exists for this target"
        )


def create_user_price_alert(
    database_session: Session,
    *,
    user_id: int,
    payload: PriceAlertCreate,
) -> PriceAlertResponse:
    """Create a price alert for the authenticated user."""

    _validate_alert_target(
        database_session,
        payload,
    )

    _check_duplicate_active_alert(
        database_session,
        user_id=user_id,
        canonical_product_id=payload.canonical_product_id,
        listing_id=payload.listing_id,
    )

    try:
        alert = create_price_alert(
            database_session,
            user_id=user_id,
            canonical_product_id=payload.canonical_product_id,
            listing_id=payload.listing_id,
            target_price=payload.target_price,
            currency=payload.currency,
        )

        database_session.commit()
        database_session.refresh(alert)

    except IntegrityError as error:
        database_session.rollback()

        raise PriceAlertAlreadyExistsError(
            "An active price alert already exists for this target"
        ) from error

    except Exception:
        database_session.rollback()
        raise

    return PriceAlertResponse.model_validate(alert)


def get_user_price_alerts(
    database_session: Session,
    *,
    user_id: int,
) -> PriceAlertListResponse:
    """Return all alerts owned by the authenticated user."""

    alerts = list_user_price_alerts(
        database_session,
        user_id,
    )

    alert_responses = [
        PriceAlertResponse.model_validate(alert)
        for alert in alerts
    ]

    return PriceAlertListResponse(
        total=len(alert_responses),
        items=alert_responses,
    )


def get_user_price_alert_detail(
    database_session: Session,
    *,
    user_id: int,
    alert_id: int,
) -> PriceAlertResponse:
    """Return one alert when it belongs to the authenticated user."""

    alert = get_user_price_alert(
        database_session,
        user_id=user_id,
        alert_id=alert_id,
    )

    if alert is None:
        raise PriceAlertNotFoundError(
            "Price alert not found"
        )

    return PriceAlertResponse.model_validate(alert)


def update_user_price_alert(
    database_session: Session,
    *,
    user_id: int,
    alert_id: int,
    payload: PriceAlertUpdate,
) -> PriceAlertResponse:
    """Update an alert belonging to the authenticated user."""

    alert = get_user_price_alert(
        database_session,
        user_id=user_id,
        alert_id=alert_id,
    )

    if alert is None:
        raise PriceAlertNotFoundError(
            "Price alert not found"
        )

    is_being_reactivated = (
        payload.is_active is True
        and alert.is_active is False
    )

    if is_being_reactivated:
        _check_duplicate_active_alert(
            database_session,
            user_id=user_id,
            canonical_product_id=alert.canonical_product_id,
            listing_id=alert.listing_id,
            exclude_alert_id=alert.id,
        )

    try:
        updated_alert = update_price_alert(
            database_session,
            alert,
            target_price=payload.target_price,
            currency=payload.currency,
            is_active=payload.is_active,
        )

        database_session.commit()
        database_session.refresh(updated_alert)

    except IntegrityError as error:
        database_session.rollback()

        raise PriceAlertAlreadyExistsError(
            "An active price alert already exists for this target"
        ) from error

    except Exception:
        database_session.rollback()
        raise

    return PriceAlertResponse.model_validate(
        updated_alert
    )


def deactivate_user_price_alert(
    database_session: Session,
    *,
    user_id: int,
    alert_id: int,
) -> PriceAlertResponse:
    """Deactivate an alert belonging to the authenticated user."""

    alert = get_user_price_alert(
        database_session,
        user_id=user_id,
        alert_id=alert_id,
    )

    if alert is None:
        raise PriceAlertNotFoundError(
            "Price alert not found"
        )

    try:
        deactivated_alert = deactivate_price_alert(
            database_session,
            alert,
        )

        database_session.commit()
        database_session.refresh(deactivated_alert)

    except Exception:
        database_session.rollback()
        raise

    return PriceAlertResponse.model_validate(
        deactivated_alert
    )