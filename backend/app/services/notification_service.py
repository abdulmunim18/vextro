from sqlalchemy.orm import Session

from app.repositories.notification_repository import (
    count_unread_notifications,
    count_user_notifications,
    get_user_notification,
    list_user_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)
from app.schemas.notification import (
    NotificationListResponse,
    NotificationMarkAllReadResponse,
    NotificationResponse,
    NotificationUnreadCountResponse,
)



class NotificationNotFoundError(Exception):
    """Raised when a notification does not exist or belongs to another user."""


def get_user_notifications(
    database_session: Session,
    *,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> NotificationListResponse:
    """Return paginated notifications owned by the authenticated user."""

    notifications = list_user_notifications(
        database_session,
        user_id=user_id,
        unread_only=unread_only,
        limit=limit,
        offset=offset,
    )

    total = count_user_notifications(
        database_session,
        user_id=user_id,
        unread_only=unread_only,
    )

    unread_count = count_unread_notifications(
        database_session,
        user_id=user_id,
    )

    return NotificationListResponse(
        total=total,
        unread_count=unread_count,
        limit=limit,
        offset=offset,
        items=[
            NotificationResponse.model_validate(notification)
            for notification in notifications
        ],
    )


def get_user_unread_notification_count(
    database_session: Session,
    *,
    user_id: int,
) -> NotificationUnreadCountResponse:
    """Return the authenticated user's unread notification count."""

    unread_count = count_unread_notifications(
        database_session,
        user_id=user_id,
    )

    return NotificationUnreadCountResponse(
        unread_count=unread_count,
    )


def mark_user_notification_read(
    database_session: Session,
    *,
    user_id: int,
    notification_id: int,
) -> NotificationResponse:
    """Mark one notification as read when it belongs to the user."""

    notification = get_user_notification(
        database_session,
        user_id=user_id,
        notification_id=notification_id,
    )

    if notification is None:
        raise NotificationNotFoundError(
            "Notification not found"
        )

    try:
        updated_notification = mark_notification_read(
            database_session,
            notification,
        )

        database_session.commit()
        database_session.refresh(updated_notification)

    except Exception:
        database_session.rollback()
        raise

    return NotificationResponse.model_validate(
        updated_notification
    )


def mark_all_user_notifications_read(
    database_session: Session,
    *,
    user_id: int,
) -> NotificationMarkAllReadResponse:
    """Mark every unread notification belonging to the user as read."""

    try:
        updated_count = mark_all_notifications_read(
            database_session,
            user_id=user_id,
        )

        database_session.commit()

    except Exception:
        database_session.rollback()
        raise

    unread_count = count_unread_notifications(
        database_session,
        user_id=user_id,
    )

    return NotificationMarkAllReadResponse(
        updated_count=updated_count,
        unread_count=unread_count,
    )