from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.notification_delivery import (
    NotificationDelivery,
    STATUS_FAILED,
    STATUS_PENDING,
)
from app.models.notification_event import NotificationEvent


def get_event_by_key(
    database_session: Session,
    *,
    event_key: str,
) -> NotificationEvent | None:
    """Return an already-recorded event for one idempotency key."""

    query = select(NotificationEvent).where(
        NotificationEvent.event_key == event_key,
    )

    return database_session.scalar(query)


def create_event(
    database_session: Session,
    *,
    user_id: int,
    event_key: str,
    event_type: str,
    title: str,
    body: str,
    payload: dict[str, Any],
    notification_id: int | None = None,
    action_path: str | None = None,
) -> NotificationEvent | None:
    """Record a new notification event, or ``None`` when it already exists.

    The unique ``event_key`` index is the authority: a retried job or a
    re-processed price observation loses the race and gets ``None`` back,
    so no channel is ever delivered twice.
    """

    existing_event = get_event_by_key(
        database_session,
        event_key=event_key,
    )

    if existing_event is not None:
        return None

    event = NotificationEvent(
        user_id=user_id,
        notification_id=notification_id,
        event_key=event_key,
        event_type=event_type,
        title=title,
        body=body,
        action_path=action_path,
        payload=payload,
    )

    database_session.add(event)

    try:
        with database_session.begin_nested():
            database_session.flush()

    except IntegrityError:
        database_session.expunge(event)

        return None

    return event


def create_delivery(
    database_session: Session,
    *,
    event_id: int,
    user_id: int,
    channel: str,
    status: str,
    failure_reason: str | None = None,
) -> NotificationDelivery:
    """Record one channel delivery row for an event."""

    now = datetime.now(UTC)

    delivery = NotificationDelivery(
        event_id=event_id,
        user_id=user_id,
        channel=channel,
        status=status,
        attempts=0,
        delivered_at=(
            now
            if status == "delivered"
            else None
        ),
        failure_reason=failure_reason,
    )

    database_session.add(delivery)
    database_session.flush()

    return delivery


def list_dispatchable_deliveries(
    database_session: Session,
    *,
    max_attempts: int,
    channels: tuple[str, ...] | None = None,
    event_ids: list[int] | None = None,
    limit: int = 100,
) -> list[NotificationDelivery]:
    """Return outbox rows still eligible for a delivery attempt."""

    conditions = [
        NotificationDelivery.status.in_(
            [
                STATUS_PENDING,
                STATUS_FAILED,
            ]
        ),
        NotificationDelivery.attempts < max_attempts,
    ]

    if channels:
        conditions.append(
            NotificationDelivery.channel.in_(list(channels)),
        )

    if event_ids is not None:
        if not event_ids:
            return []

        conditions.append(
            NotificationDelivery.event_id.in_(event_ids),
        )

    query = (
        select(NotificationDelivery)
        .where(and_(*conditions))
        .order_by(NotificationDelivery.id.asc())
        .limit(limit)
        .with_for_update(skip_locked=True)
    )

    return list(
        database_session.scalars(query).all()
    )


def mark_delivery_attempted(
    database_session: Session,
    delivery: NotificationDelivery,
) -> NotificationDelivery:
    """Count one delivery attempt before the transport is contacted."""

    delivery.attempts += 1
    delivery.attempted_at = datetime.now(UTC)

    database_session.flush()

    return delivery


def mark_delivery_delivered(
    database_session: Session,
    delivery: NotificationDelivery,
) -> NotificationDelivery:
    """Record a successful channel delivery."""

    delivery.status = "delivered"
    delivery.delivered_at = datetime.now(UTC)
    delivery.failure_reason = None

    database_session.flush()

    return delivery


def mark_delivery_failed(
    database_session: Session,
    delivery: NotificationDelivery,
    *,
    failure_reason: str,
) -> NotificationDelivery:
    """Record a failed channel delivery for later bounded retry."""

    delivery.status = STATUS_FAILED
    delivery.failure_reason = failure_reason[:500]

    database_session.flush()

    return delivery


def mark_delivery_skipped(
    database_session: Session,
    delivery: NotificationDelivery,
    *,
    reason: str,
) -> NotificationDelivery:
    """Record that a channel will not be attempted again."""

    delivery.status = "skipped"
    delivery.failure_reason = reason[:500]

    database_session.flush()

    return delivery


def list_user_events_in_period(
    database_session: Session,
    *,
    user_id: int,
    event_types: tuple[str, ...],
    period_start: datetime,
    period_end: datetime,
    limit: int = 50,
) -> list[NotificationEvent]:
    """Return a user's events recorded inside one digest period."""

    query = (
        select(NotificationEvent)
        .where(
            NotificationEvent.user_id == user_id,
            NotificationEvent.event_type.in_(list(event_types)),
            NotificationEvent.created_at >= period_start,
            NotificationEvent.created_at < period_end,
        )
        .order_by(NotificationEvent.created_at.asc())
        .limit(limit)
    )

    return list(
        database_session.scalars(query).all()
    )
