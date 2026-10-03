"""Central multi-channel notification orchestrator.

One business event is handed to :func:`dispatch_event`, which records the
event, creates the in-app notification and writes one outbox row per
delivery channel inside the caller's transaction. After that transaction
commits, :func:`dispatch_pending_deliveries` contacts SMTP and the Web
Push endpoints.

    PRICE ALERT / COMPETITOR RISK EVENT
                |
                v
      dispatch_event (in transaction)
                |
                +--> InApp channel      (notifications row, immediate)
                +--> Email channel      (outbox row, pending)
                +--> WebPush channel    (outbox row, pending)
                |
             commit
                |
                v
      dispatch_pending_deliveries (after commit)

Email and Web Push are strictly secondary: a transport failure is logged
and recorded against the outbox row, and never rolls back the price
observation, the price alert or the in-app notification.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import Settings, settings as default_settings
from app.models.notification_delivery import (
    CHANNEL_EMAIL,
    CHANNEL_IN_APP,
    CHANNEL_WEB_PUSH,
    NotificationDelivery,
    STATUS_DELIVERED,
    STATUS_PENDING,
    STATUS_SKIPPED,
)
from app.models.notification_event import (
    EVENT_TYPE_COMPETITOR_RISK,
    EVENT_TYPE_DIGEST,
    EVENT_TYPE_PRICE_DROP,
    NotificationEvent,
)
from app.repositories.notification_event_repository import (
    create_delivery,
    create_event,
    list_dispatchable_deliveries,
    mark_delivery_attempted,
    mark_delivery_delivered,
    mark_delivery_failed,
    mark_delivery_skipped,
)
from app.repositories.notification_preference_repository import (
    get_or_create_user_preference,
)
from app.repositories.notification_repository import create_notification
from app.repositories.push_subscription_repository import (
    deactivate_subscription,
    list_active_user_subscriptions,
    mark_subscription_delivered,
)
from app.repositories.user_repository import get_user_by_id
from app.services.email_service import (
    EmailContent,
    EmailDeliveryError,
    EmailNotConfiguredError,
    send_email,
)
from app.services.email_templates import (
    render_competitor_risk_email,
    render_digest_email,
    render_price_drop_email,
)
from app.services.web_push_service import (
    WebPushDeliveryError,
    WebPushMessage,
    WebPushNotConfiguredError,
    WebPushSubscriptionInfo,
    send_web_push,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationEventRequest:
    """One business event to fan out across the delivery channels."""

    user_id: int
    event_key: str
    event_type: str
    title: str
    message: str
    push_body: str
    payload: dict[str, Any] = field(default_factory=dict)
    action_path: str | None = None
    price_alert_id: int | None = None
    canonical_product_id: int | None = None
    create_in_app_notification: bool = True
    email_attachment_builder_key: str | None = None


def _email_preference_enabled(
    event_type: str,
    preference: Any,
) -> bool:
    """Report whether the user accepts email for this event type."""

    if event_type == EVENT_TYPE_PRICE_DROP:
        return bool(preference.price_alert_email)

    if event_type == EVENT_TYPE_COMPETITOR_RISK:
        return bool(preference.competitor_alert_email)

    if event_type == EVENT_TYPE_DIGEST:
        return preference.digest_frequency in {"daily", "weekly"}

    return False


def _push_preference_enabled(
    event_type: str,
    preference: Any,
) -> bool:
    """Report whether the user accepts Web Push for this event type."""

    if event_type == EVENT_TYPE_PRICE_DROP:
        return bool(preference.price_alert_push)

    if event_type == EVENT_TYPE_COMPETITOR_RISK:
        return bool(preference.competitor_alert_push)

    return False


def dispatch_event(
    database_session: Session,
    request: NotificationEventRequest,
) -> NotificationEvent | None:
    """Record one event and queue every enabled delivery channel.

    Returns ``None`` when ``request.event_key`` was already dispatched, so
    callers can tell a fresh event from a replayed one.

    This function only writes rows. It performs no network I/O and must be
    called inside the caller's business transaction. Whether a transport
    is actually configured is decided later, at delivery time, so that the
    outbox reflects the user's intent rather than today's deployment.
    """

    notification = None

    if request.create_in_app_notification:
        notification = create_notification(
            database_session,
            user_id=request.user_id,
            price_alert_id=request.price_alert_id,
            canonical_product_id=request.canonical_product_id,
            notification_type=request.event_type,
            title=request.title,
            message=request.message,
            action_path=request.action_path,
        )

    event = create_event(
        database_session,
        user_id=request.user_id,
        event_key=request.event_key,
        event_type=request.event_type,
        title=request.title,
        body=request.push_body,
        payload=request.payload,
        notification_id=(
            notification.id
            if notification is not None
            else None
        ),
        action_path=request.action_path,
    )

    if event is None:
        # A concurrent or retried run already recorded this event. Undo the
        # in-app notification created above so the user sees exactly one.
        if notification is not None:
            database_session.delete(notification)
            database_session.flush()

        logger.info(
            "notification.event.duplicate_skipped event_key=%s",
            request.event_key,
        )

        return None

    logger.info(
        "notification.event.created event_key=%s type=%s user_id=%s",
        event.event_key,
        event.event_type,
        event.user_id,
    )

    if notification is not None:
        create_delivery(
            database_session,
            event_id=event.id,
            user_id=request.user_id,
            channel=CHANNEL_IN_APP,
            status=STATUS_DELIVERED,
        )

    preference = get_or_create_user_preference(
        database_session,
        user_id=request.user_id,
    )

    user = get_user_by_id(
        database_session,
        request.user_id,
    )

    email_enabled = _email_preference_enabled(
        request.event_type,
        preference,
    )

    if not email_enabled:
        create_delivery(
            database_session,
            event_id=event.id,
            user_id=request.user_id,
            channel=CHANNEL_EMAIL,
            status=STATUS_SKIPPED,
            failure_reason="Email notifications disabled by the user.",
        )

    elif user is None or not (user.email or "").strip():
        create_delivery(
            database_session,
            event_id=event.id,
            user_id=request.user_id,
            channel=CHANNEL_EMAIL,
            status=STATUS_SKIPPED,
            failure_reason="No email address is available for this user.",
        )

    else:
        create_delivery(
            database_session,
            event_id=event.id,
            user_id=request.user_id,
            channel=CHANNEL_EMAIL,
            status=STATUS_PENDING,
        )

    push_enabled = _push_preference_enabled(
        request.event_type,
        preference,
    )

    if not push_enabled:
        create_delivery(
            database_session,
            event_id=event.id,
            user_id=request.user_id,
            channel=CHANNEL_WEB_PUSH,
            status=STATUS_SKIPPED,
            failure_reason="Push notifications disabled by the user.",
        )

    elif not list_active_user_subscriptions(
        database_session,
        user_id=request.user_id,
    ):
        create_delivery(
            database_session,
            event_id=event.id,
            user_id=request.user_id,
            channel=CHANNEL_WEB_PUSH,
            status=STATUS_SKIPPED,
            failure_reason="The user has no active push subscription.",
        )

    else:
        create_delivery(
            database_session,
            event_id=event.id,
            user_id=request.user_id,
            channel=CHANNEL_WEB_PUSH,
            status=STATUS_PENDING,
        )

    return event


EMAIL_RENDERERS = {
    EVENT_TYPE_PRICE_DROP: render_price_drop_email,
    EVENT_TYPE_COMPETITOR_RISK: render_competitor_risk_email,
}


def render_event_email(
    event: NotificationEvent,
    *,
    settings: Settings | None = None,
) -> EmailContent | None:
    """Render the email body for one stored event."""

    active_settings = settings or default_settings

    if event.event_type == EVENT_TYPE_DIGEST:
        return render_digest_email(
            event.payload or {},
            settings=active_settings,
        )

    renderer = EMAIL_RENDERERS.get(event.event_type)

    if renderer is None:
        return None

    return renderer(
        event.payload or {},
        action_path=event.action_path,
        settings=active_settings,
    )


def _deliver_email_channel(
    database_session: Session,
    delivery: NotificationDelivery,
    event: NotificationEvent,
    *,
    settings: Settings,
) -> bool:
    """Attempt the email channel for one outbox row."""

    user = get_user_by_id(
        database_session,
        delivery.user_id,
    )

    if user is None or not (user.email or "").strip():
        mark_delivery_skipped(
            database_session,
            delivery,
            reason="No email address is available for this user.",
        )

        return False

    content = render_event_email(
        event,
        settings=settings,
    )

    if content is None:
        mark_delivery_skipped(
            database_session,
            delivery,
            reason=(
                "No email template exists for event type "
                f"{event.event_type}."
            ),
        )

        return False

    mark_delivery_attempted(
        database_session,
        delivery,
    )

    logger.info(
        "email.delivery.attempted event_key=%s attempt=%s",
        event.event_key,
        delivery.attempts,
    )

    try:
        send_email(
            recipient=user.email,
            content=content,
            settings=settings,
        )

    except EmailNotConfiguredError as error:
        mark_delivery_skipped(
            database_session,
            delivery,
            reason=str(error),
        )

        logger.warning(
            "email.delivery.skipped event_key=%s reason=%s",
            event.event_key,
            error,
        )

        return False

    except EmailDeliveryError as error:
        if error.is_permanent:
            mark_delivery_skipped(
                database_session,
                delivery,
                reason=str(error),
            )
        else:
            mark_delivery_failed(
                database_session,
                delivery,
                failure_reason=str(error),
            )

        logger.warning(
            "email.delivery.failed event_key=%s permanent=%s reason=%s",
            event.event_key,
            error.is_permanent,
            error,
        )

        return False

    except Exception as error:  # noqa: BLE001 - channel must never raise
        mark_delivery_failed(
            database_session,
            delivery,
            failure_reason=f"Unexpected email error: {type(error).__name__}",
        )

        logger.exception(
            "email.delivery.failed event_key=%s",
            event.event_key,
        )

        return False

    mark_delivery_delivered(
        database_session,
        delivery,
    )

    logger.info(
        "email.delivery.successful event_key=%s",
        event.event_key,
    )

    return True


def _deliver_web_push_channel(
    database_session: Session,
    delivery: NotificationDelivery,
    event: NotificationEvent,
    *,
    settings: Settings,
) -> bool:
    """Attempt Web Push for every active subscription of one user."""

    subscriptions = list_active_user_subscriptions(
        database_session,
        user_id=delivery.user_id,
    )

    if not subscriptions:
        mark_delivery_skipped(
            database_session,
            delivery,
            reason="The user has no active push subscription.",
        )

        return False

    message = WebPushMessage(
        title=event.title,
        body=event.body,
        action_path=event.action_path,
        tag=event.event_key,
    )

    mark_delivery_attempted(
        database_session,
        delivery,
    )

    delivered_count = 0
    transient_failures: list[str] = []
    permanent_failures = 0

    for subscription in subscriptions:
        try:
            send_web_push(
                subscription=WebPushSubscriptionInfo(
                    endpoint=subscription.endpoint,
                    p256dh_key=subscription.p256dh_key,
                    auth_key=subscription.auth_key,
                ),
                message=message,
                settings=settings,
            )

        except WebPushNotConfiguredError as error:
            mark_delivery_skipped(
                database_session,
                delivery,
                reason=str(error),
            )

            return False

        except WebPushDeliveryError as error:
            if error.is_permanent:
                # The endpoint is gone for good, so stop paying for it on
                # every future job.
                deactivate_subscription(
                    database_session,
                    subscription,
                )

                permanent_failures += 1

                logger.info(
                    (
                        "push.subscription.invalidated "
                        "subscription_id=%s status=%s"
                    ),
                    subscription.id,
                    error.status_code,
                )
            else:
                # A temporary failure must leave a valid subscription in
                # place for the next retry.
                transient_failures.append(str(error))

                logger.warning(
                    "push.delivery.failed subscription_id=%s reason=%s",
                    subscription.id,
                    error,
                )

            continue

        except Exception as error:  # noqa: BLE001 - channel must not raise
            transient_failures.append(
                f"Unexpected push error: {type(error).__name__}"
            )

            logger.exception(
                "push.delivery.failed subscription_id=%s",
                subscription.id,
            )

            continue

        delivered_count += 1

        mark_subscription_delivered(
            database_session,
            subscription,
        )

        logger.info(
            "push.delivery.successful event_key=%s subscription_id=%s",
            event.event_key,
            subscription.id,
        )

    if delivered_count > 0:
        mark_delivery_delivered(
            database_session,
            delivery,
        )

        return True

    if transient_failures:
        mark_delivery_failed(
            database_session,
            delivery,
            failure_reason="; ".join(transient_failures[:3]),
        )

        return False

    mark_delivery_skipped(
        database_session,
        delivery,
        reason=(
            f"All {permanent_failures} push subscriptions were expired."
        ),
    )

    return False


CHANNEL_HANDLERS = {
    CHANNEL_EMAIL: _deliver_email_channel,
    CHANNEL_WEB_PUSH: _deliver_web_push_channel,
}


def dispatch_pending_deliveries(
    database_session: Session,
    *,
    event_ids: list[int] | None = None,
    limit: int = 100,
    settings: Settings | None = None,
) -> dict[str, int]:
    """Send every outbox row still eligible for a delivery attempt.

    Call this only after the business transaction that produced the events
    has committed. Each row is committed on its own so one failing channel
    can never undo a delivery that already succeeded.
    """

    active_settings = settings or default_settings

    summary = {
        "attempted": 0,
        "delivered": 0,
        "failed": 0,
    }

    deliveries = list_dispatchable_deliveries(
        database_session,
        max_attempts=active_settings.notification_delivery_max_attempts,
        channels=(
            CHANNEL_EMAIL,
            CHANNEL_WEB_PUSH,
        ),
        event_ids=event_ids,
        limit=limit,
    )

    for delivery in deliveries:
        handler = CHANNEL_HANDLERS.get(delivery.channel)

        if handler is None:
            continue

        event = database_session.get(
            NotificationEvent,
            delivery.event_id,
        )

        if event is None:
            continue

        summary["attempted"] += 1

        try:
            was_delivered = handler(
                database_session,
                delivery,
                event,
                settings=active_settings,
            )

            database_session.commit()

        except Exception:  # noqa: BLE001 - never break the caller's job
            database_session.rollback()

            logger.exception(
                "notification.delivery.dispatch_error delivery_id=%s",
                delivery.id,
            )

            summary["failed"] += 1

            continue

        if was_delivered:
            summary["delivered"] += 1
        else:
            summary["failed"] += 1

    return summary
