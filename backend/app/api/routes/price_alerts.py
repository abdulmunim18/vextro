from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies.roles import consumer_or_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.price_intelligence import (
    PriceAlertCreate,
    PriceAlertListResponse,
    PriceAlertResponse,
    PriceAlertUpdate,
)
from app.services.price_alert_service import (
    PriceAlertAlreadyExistsError,
    PriceAlertNotFoundError,
    PriceAlertTargetNotFoundError,
    create_user_price_alert,
    deactivate_user_price_alert,
    get_user_price_alert_detail,
    get_user_price_alerts,
    update_user_price_alert,
)


router = APIRouter(
    prefix="/api/v1/price-alerts",
    tags=["price-alerts"],
)


def _target_not_found_exception(
    error: PriceAlertTargetNotFoundError,
) -> HTTPException:
    """Convert a missing alert target into an API error."""

    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "PRICE_ALERT_TARGET_NOT_FOUND",
            "message": str(error),
        },
    )


def _duplicate_alert_exception(
    error: PriceAlertAlreadyExistsError,
) -> HTTPException:
    """Convert a duplicate active alert into an API error."""

    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "PRICE_ALERT_ALREADY_EXISTS",
            "message": str(error),
        },
    )


def _alert_not_found_exception(
    error: PriceAlertNotFoundError,
) -> HTTPException:
    """Convert a missing or unauthorized alert into an API error."""

    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "PRICE_ALERT_NOT_FOUND",
            "message": str(error),
        },
    )


@router.post(
    "",
    response_model=PriceAlertResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_price_alert_endpoint(
    payload: PriceAlertCreate,
    current_user: User = Depends(consumer_or_admin),
    database_session: Session = Depends(get_db),
) -> PriceAlertResponse:
    """Create a product-level or listing-level price alert."""

    try:
        return create_user_price_alert(
            database_session,
            user_id=current_user.id,
            payload=payload,
        )

    except PriceAlertTargetNotFoundError as error:
        raise _target_not_found_exception(error) from error

    except PriceAlertAlreadyExistsError as error:
        raise _duplicate_alert_exception(error) from error


@router.get(
    "",
    response_model=PriceAlertListResponse,
    status_code=status.HTTP_200_OK,
)
def list_price_alerts_endpoint(
    current_user: User = Depends(consumer_or_admin),
    database_session: Session = Depends(get_db),
) -> PriceAlertListResponse:
    """Return alerts belonging to the authenticated user."""

    return get_user_price_alerts(
        database_session,
        user_id=current_user.id,
    )


@router.get(
    "/{alert_id}",
    response_model=PriceAlertResponse,
    status_code=status.HTTP_200_OK,
)
def read_price_alert_endpoint(
    alert_id: int = Path(
        ...,
        ge=1,
        description="Price alert ID.",
    ),
    current_user: User = Depends(consumer_or_admin),
    database_session: Session = Depends(get_db),
) -> PriceAlertResponse:
    """Return one alert owned by the authenticated user."""

    try:
        return get_user_price_alert_detail(
            database_session,
            user_id=current_user.id,
            alert_id=alert_id,
        )

    except PriceAlertNotFoundError as error:
        raise _alert_not_found_exception(error) from error


@router.patch(
    "/{alert_id}",
    response_model=PriceAlertResponse,
    status_code=status.HTTP_200_OK,
)
def update_price_alert_endpoint(
    payload: PriceAlertUpdate,
    alert_id: int = Path(
        ...,
        ge=1,
        description="Price alert ID.",
    ),
    current_user: User = Depends(consumer_or_admin),
    database_session: Session = Depends(get_db),
) -> PriceAlertResponse:
    """Update or reactivate an alert owned by the user."""

    try:
        return update_user_price_alert(
            database_session,
            user_id=current_user.id,
            alert_id=alert_id,
            payload=payload,
        )

    except PriceAlertNotFoundError as error:
        raise _alert_not_found_exception(error) from error

    except PriceAlertAlreadyExistsError as error:
        raise _duplicate_alert_exception(error) from error


@router.delete(
    "/{alert_id}",
    response_model=PriceAlertResponse,
    status_code=status.HTTP_200_OK,
)
def deactivate_price_alert_endpoint(
    alert_id: int = Path(
        ...,
        ge=1,
        description="Price alert ID.",
    ),
    current_user: User = Depends(consumer_or_admin),
    database_session: Session = Depends(get_db),
) -> PriceAlertResponse:
    """Deactivate an alert without deleting its database record."""

    try:
        return deactivate_user_price_alert(
            database_session,
            user_id=current_user.id,
            alert_id=alert_id,
        )

    except PriceAlertNotFoundError as error:
        raise _alert_not_found_exception(error) from error