"""Notification preference and push-subscription application logic.

Every function here is scoped to one ``user_id`` taken from the verified
access token, so a user can only ever read or change their own
preferences and their own browser subscriptions.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.core.config import Settings, settings as default_settings
from app.models.notification_preference import NotificationPreference
from app.repositories.notification_preference_repository import (
    get_or_create_user_preference,
    update_user_preference,
)
from app.repositories.push_subscription_repository import (
    count_active_user_subscriptions,
    deactivate_subscription,
    get_subscription_by_endpoint,
    upsert_subscription,
)
from app.schemas.notification import (
    NotificationPreferenceResponse,
    NotificationPreferenceUpdate,
    PushSubscriptionCreate,
    PushSubscriptionResponse,
    PushUnsubscribeResponse,
)


logger = logging.getLogger(__name__)


def _build_preference_response(
    database_session: Session,
    preference: NotificationPreference,
    *,
    settings: Settings,
) -> NotificationPreferenceResponse:
    """Combine stored preferences with server capability information."""

    return NotificationPreferenceResponse(
        price_alert_in_app=True,
        price_alert_email=preference.price_alert_email,
        price_alert_push=preference.price_alert_push,
        competitor_alert_in_app=True,
        competitor_alert_email=preference.competitor_alert_email,
        competitor_alert_push=preference.competitor_alert_push,
        digest_frequency=preference.digest_frequency,
        digest_timezone=settings.digest_timezone,
        is_email_configured=settings.is_email_configured,
        is_push_configured=settings.is_web_push_configured,
        active_push_subscription_count=(
            count_active_user_subscriptions(
                database_session,
                user_id=preference.user_id,
            )
        ),
        vapid_public_key=settings.vapid_public_key,
    )


def get_user_notification_preferences(
    database_session: Session,
    *,
    user_id: int,
    settings: Settings | None = None,
) -> NotificationPreferenceResponse:
    """Return the user's preferences, creating sensible defaults first."""

    active_settings = settings or default_settings

    try:
        preference = get_or_create_user_preference(
            database_session,
            user_id=user_id,
        )

        database_session.commit()

    except Exception:
        database_session.rollback()
        raise

    return _build_preference_response(
        database_session,
        preference,
        settings=active_settings,
    )


def update_user_notification_preferences(
    database_session: Session,
    *,
    user_id: int,
    payload: NotificationPreferenceUpdate,
    settings: Settings | None = None,
) -> NotificationPreferenceResponse:
    """Apply the authenticated user's preference changes."""

    active_settings = settings or default_settings

    try:
        preference = get_or_create_user_preference(
            database_session,
            user_id=user_id,
        )

        updated_preference = update_user_preference(
            database_session,
            preference,
            price_alert_email=payload.price_alert_email,
            price_alert_push=payload.price_alert_push,
            competitor_alert_email=payload.competitor_alert_email,
            competitor_alert_push=payload.competitor_alert_push,
            digest_frequency=payload.digest_frequency,
        )

        database_session.commit()
        database_session.refresh(updated_preference)

    except Exception:
        database_session.rollback()
        raise

    logger.info(
        "notification.preferences.updated user_id=%s digest=%s",
        user_id,
        updated_preference.digest_frequency,
    )

    return _build_preference_response(
        database_session,
        updated_preference,
        settings=active_settings,
    )


def register_user_push_subscription(
    database_session: Session,
    *,
    user_id: int,
    payload: PushSubscriptionCreate,
    user_agent: str | None = None,
) -> PushSubscriptionResponse:
    """Store a browser subscription for the authenticated user."""

    try:
        subscription = upsert_subscription(
            database_session,
            user_id=user_id,
            endpoint=payload.endpoint,
            p256dh_key=payload.keys.p256dh,
            auth_key=payload.keys.auth,
            user_agent=(user_agent or None),
        )

        preference = get_or_create_user_preference(
            database_session,
            user_id=user_id,
        )

        # Registering a browser is an explicit opt-in to push delivery.
        if not preference.price_alert_push:
            preference.price_alert_push = True

        if not preference.competitor_alert_push:
            preference.competitor_alert_push = True

        database_session.commit()
        database_session.refresh(subscription)

    except Exception:
        database_session.rollback()
        raise

    logger.info(
        "push.subscription.registered user_id=%s subscription_id=%s",
        user_id,
        subscription.id,
    )

    return PushSubscriptionResponse.model_validate(subscription)


def remove_user_push_subscription(
    database_session: Session,
    *,
    user_id: int,
    endpoint: str,
) -> PushUnsubscribeResponse:
    """Disable one browser subscription owned by the current user.

    An endpoint belonging to another user is treated as not found, so the
    endpoint cannot be used to disable somebody else's subscription.
    """

    subscription = get_subscription_by_endpoint(
        database_session,
        endpoint=endpoint,
    )

    if subscription is None or subscription.user_id != user_id:
        return PushUnsubscribeResponse(
            deactivated=False,
        )

    try:
        deactivate_subscription(
            database_session,
            subscription,
        )

        database_session.commit()

    except Exception:
        database_session.rollback()
        raise

    logger.info(
        "push.subscription.deactivated user_id=%s subscription_id=%s",
        user_id,
        subscription.id,
    )

    return PushUnsubscribeResponse(
        deactivated=True,
    )
