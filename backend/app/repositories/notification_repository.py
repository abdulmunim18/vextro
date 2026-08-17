from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification import Notification


def create_notification(
    database_session: Session,
    *,
    user_id: int,
    notification_type: str,
    title: str,
    message: str,
    price_alert_id: int | None = None,
    canonical_product_id: int | None = None,
    action_path: str | None = None,
) -> Notification:
    """Create and flush an in-app notification."""

    notification = Notification(
        user_id=user_id,
        price_alert_id=price_alert_id,
        canonical_product_id=canonical_product_id,
        notification_type=notification_type,
        title=title,
        message=message,
        action_path=action_path,
    )

    database_session.add(notification)
    database_session.flush()

    return notification


def list_user_notifications(
    database_session: Session,
    *,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> list[Notification]:
    """Return notifications belonging to one user."""

    query = select(Notification).where(
        Notification.user_id == user_id,
    )

    if unread_only:
        query = query.where(
            Notification.is_read.is_(False),
        )

    query = (
        query
        .order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .offset(offset)
        .limit(limit)
    )

    return list(
        database_session.scalars(query).all()
    )


def get_user_notification(
    database_session: Session,
    *,
    user_id: int,
    notification_id: int,
) -> Notification | None:
    """Return a notification only when it belongs to the user."""

    query = select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == user_id,
    )

    return database_session.scalar(query)


def count_unread_notifications(
    database_session: Session,
    *,
    user_id: int,
) -> int:
    """Return the number of unread notifications for one user."""

    query = select(
        func.count(Notification.id)
    ).where(
        Notification.user_id == user_id,
        Notification.is_read.is_(False),
    )

    return int(
        database_session.scalar(query) or 0
    )


def mark_notification_read(
    database_session: Session,
    notification: Notification,
) -> Notification:
    """Mark one notification as read."""

    if notification.is_read:
        return notification

    notification.is_read = True
    notification.read_at = datetime.now(UTC)

    database_session.flush()

    return notification


def mark_all_notifications_read(
    database_session: Session,
    *,
    user_id: int,
) -> int:
    """Mark all unread notifications for one user as read."""

    query = select(Notification).where(
        Notification.user_id == user_id,
        Notification.is_read.is_(False),
    )

    notifications = list(
        database_session.scalars(query).all()
    )

    if not notifications:
        return 0

    read_at = datetime.now(UTC)

    for notification in notifications:
        notification.is_read = True
        notification.read_at = read_at

    database_session.flush()

    return len(notifications)
def count_user_notifications(
    database_session: Session,
    *,
    user_id: int,
    unread_only: bool = False,
) -> int:
    """Return the total number of notifications matching the user filter."""

    query = select(
        func.count(Notification.id)
    ).where(
        Notification.user_id == user_id,
    )

    if unread_only:
        query = query.where(
            Notification.is_read.is_(False),
        )

    return int(
        database_session.scalar(query) or 0
    )