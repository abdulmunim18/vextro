from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies.roles import authenticated_role
from app.core.database import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationListResponse,
    NotificationMarkAllReadResponse,
    NotificationResponse,
    NotificationUnreadCountResponse,
)
from app.services.notification_service import (
    NotificationNotFoundError,
    get_user_notifications,
    get_user_unread_notification_count,
    mark_all_user_notifications_read,
    mark_user_notification_read,
)


router = APIRouter(
    prefix="/api/v1/notifications",
    tags=["notifications"],
)


def _notification_not_found_exception(
    error: NotificationNotFoundError,
) -> HTTPException:
    """Convert a missing or unauthorized notification into an API error."""

    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "NOTIFICATION_NOT_FOUND",
            "message": str(error),
        },
    )


@router.get(
    "",
    response_model=NotificationListResponse,
    status_code=status.HTTP_200_OK,
)
def list_notifications_endpoint(
    unread_only: bool = Query(
        default=False,
        description="Return only unread notifications.",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
        description="Maximum number of notifications to return.",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of matching notifications to skip.",
    ),
    current_user: User = Depends(authenticated_role),
    database_session: Session = Depends(get_db),
) -> NotificationListResponse:
    """Return notifications belonging to the authenticated user."""

    return get_user_notifications(
        database_session,
        user_id=current_user.id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )


@router.get(
    "/unread-count",
    response_model=NotificationUnreadCountResponse,
    status_code=status.HTTP_200_OK,
)
def unread_notification_count_endpoint(
    current_user: User = Depends(authenticated_role),
    database_session: Session = Depends(get_db),
) -> NotificationUnreadCountResponse:
    """Return the authenticated user's unread notification count."""

    return get_user_unread_notification_count(
        database_session,
        user_id=current_user.id,
    )


@router.patch(
    "/read-all",
    response_model=NotificationMarkAllReadResponse,
    status_code=status.HTTP_200_OK,
)
def mark_all_notifications_read_endpoint(
    current_user: User = Depends(authenticated_role),
    database_session: Session = Depends(get_db),
) -> NotificationMarkAllReadResponse:
    """Mark all notifications belonging to the user as read."""

    return mark_all_user_notifications_read(
        database_session,
        user_id=current_user.id,
    )


@router.patch(
    "/{notification_id}/read",
    response_model=NotificationResponse,
    status_code=status.HTTP_200_OK,
)
def mark_notification_read_endpoint(
    notification_id: int = Path(
        ...,
        ge=1,
        description="Notification ID.",
    ),
    current_user: User = Depends(authenticated_role),
    database_session: Session = Depends(get_db),
) -> NotificationResponse:
    """Mark one notification belonging to the user as read."""

    try:
        return mark_user_notification_read(
            database_session,
            user_id=current_user.id,
            notification_id=notification_id,
        )

    except NotificationNotFoundError as error:
        raise _notification_not_found_exception(error) from error
