import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.push_subscription import PushSubscription


def hash_endpoint(endpoint: str) -> str:
    """Return a stable digest used for endpoint uniqueness.

    Endpoints are long and vendor-specific, so a fixed-width digest keeps
    the unique index small while still identifying one browser install.
    """

    return hashlib.sha256(
        endpoint.strip().encode("utf-8"),
    ).hexdigest()


def get_subscription_by_endpoint(
    database_session: Session,
    *,
    endpoint: str,
) -> PushSubscription | None:
    """Return any subscription stored for one browser endpoint."""

    query = select(PushSubscription).where(
        PushSubscription.endpoint_hash == hash_endpoint(endpoint),
    )

    return database_session.scalar(query)


def get_user_subscription(
    database_session: Session,
    *,
    user_id: int,
    subscription_id: int,
) -> PushSubscription | None:
    """Return a subscription only when it belongs to the user."""

    query = select(PushSubscription).where(
        PushSubscription.id == subscription_id,
        PushSubscription.user_id == user_id,
    )

    return database_session.scalar(query)


def upsert_subscription(
    database_session: Session,
    *,
    user_id: int,
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
    user_agent: str | None = None,
) -> PushSubscription:
    """Store a browser subscription, re-claiming an existing endpoint.

    A browser may hand back the same endpoint after a page reload or for a
    different signed-in user on the same device, so the row is re-pointed
    at the current owner instead of duplicated.
    """

    existing_subscription = get_subscription_by_endpoint(
        database_session,
        endpoint=endpoint,
    )

    if existing_subscription is not None:
        existing_subscription.user_id = user_id
        existing_subscription.endpoint = endpoint
        existing_subscription.p256dh_key = p256dh_key
        existing_subscription.auth_key = auth_key
        existing_subscription.user_agent = user_agent
        existing_subscription.is_active = True
        existing_subscription.deactivated_at = None

        database_session.flush()

        return existing_subscription

    subscription = PushSubscription(
        user_id=user_id,
        endpoint=endpoint,
        endpoint_hash=hash_endpoint(endpoint),
        p256dh_key=p256dh_key,
        auth_key=auth_key,
        user_agent=user_agent,
        is_active=True,
    )

    database_session.add(subscription)
    database_session.flush()

    return subscription


def list_active_user_subscriptions(
    database_session: Session,
    *,
    user_id: int,
) -> list[PushSubscription]:
    """Return every active subscription owned by one user."""

    query = (
        select(PushSubscription)
        .where(
            PushSubscription.user_id == user_id,
            PushSubscription.is_active.is_(True),
        )
        .order_by(PushSubscription.id.asc())
    )

    return list(
        database_session.scalars(query).all()
    )


def count_active_user_subscriptions(
    database_session: Session,
    *,
    user_id: int,
) -> int:
    """Return how many active subscriptions one user has."""

    return len(
        list_active_user_subscriptions(
            database_session,
            user_id=user_id,
        )
    )


def deactivate_subscription(
    database_session: Session,
    subscription: PushSubscription,
) -> PushSubscription:
    """Disable one subscription without deleting its history."""

    if subscription.is_active:
        subscription.is_active = False
        subscription.deactivated_at = datetime.now(UTC)

        database_session.flush()

    return subscription


def mark_subscription_delivered(
    database_session: Session,
    subscription: PushSubscription,
) -> PushSubscription:
    """Record a successful delivery against one subscription."""

    subscription.last_delivered_at = datetime.now(UTC)

    database_session.flush()

    return subscription
