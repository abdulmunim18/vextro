from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.notification_preference import NotificationPreference


def get_user_preference(
    database_session: Session,
    *,
    user_id: int,
) -> NotificationPreference | None:
    """Return the stored preference row for one user, if any."""

    query = select(NotificationPreference).where(
        NotificationPreference.user_id == user_id,
    )

    return database_session.scalar(query)


def get_or_create_user_preference(
    database_session: Session,
    *,
    user_id: int,
) -> NotificationPreference:
    """Return the user's preference row, creating defaults when missing."""

    preference = get_user_preference(
        database_session,
        user_id=user_id,
    )

    if preference is not None:
        return preference

    preference = NotificationPreference(
        user_id=user_id,
        price_alert_email=True,
        price_alert_push=True,
        competitor_alert_email=True,
        competitor_alert_push=True,
        digest_frequency="off",
    )

    database_session.add(preference)

    try:
        with database_session.begin_nested():
            database_session.flush()

    except IntegrityError:
        # Another concurrent request created the row first.
        database_session.expunge(preference)

        existing_preference = get_user_preference(
            database_session,
            user_id=user_id,
        )

        if existing_preference is None:
            raise

        return existing_preference

    return preference


def update_user_preference(
    database_session: Session,
    preference: NotificationPreference,
    *,
    price_alert_email: bool | None = None,
    price_alert_push: bool | None = None,
    competitor_alert_email: bool | None = None,
    competitor_alert_push: bool | None = None,
    digest_frequency: str | None = None,
) -> NotificationPreference:
    """Apply only the supplied preference changes."""

    if price_alert_email is not None:
        preference.price_alert_email = price_alert_email

    if price_alert_push is not None:
        preference.price_alert_push = price_alert_push

    if competitor_alert_email is not None:
        preference.competitor_alert_email = competitor_alert_email

    if competitor_alert_push is not None:
        preference.competitor_alert_push = competitor_alert_push

    if digest_frequency is not None:
        preference.digest_frequency = digest_frequency

    database_session.flush()

    return preference


def list_digest_recipients(
    database_session: Session,
    *,
    frequency: str,
) -> list[NotificationPreference]:
    """Return preference rows subscribed to one digest frequency."""

    query = (
        select(NotificationPreference)
        .where(
            NotificationPreference.digest_frequency == frequency,
        )
        .order_by(NotificationPreference.user_id.asc())
    )

    return list(
        database_session.scalars(query).all()
    )
