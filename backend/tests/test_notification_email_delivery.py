"""Module 6.14 email delivery tests."""

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.notification_delivery import NotificationDelivery
from app.models.notification_event import NotificationEvent
from app.services import notification_dispatcher
from app.services.email_service import (
    EmailDeliveryError,
    EmailNotConfiguredError,
)
from app.services.notification_dispatcher import (
    dispatch_pending_deliveries,
)
from app.services.price_alert_service import (
    evaluate_price_alerts_for_capture,
)
from tests.notification_factories import (
    RecordingEmailTransport,
    create_consumer_alert_fixture,
    notification_settings,
    settings_without_email,
)


def user_event_ids(
    database_session: Session,
    *,
    user_id: int,
) -> list[int]:
    """Return every event id recorded for one user.

    The outbox is global, so tests scope each dispatch to the user under
    test instead of retrying rows another test deliberately left failed.
    """

    return list(
        database_session.scalars(
            select(NotificationEvent.id).where(
                NotificationEvent.user_id == user_id,
            )
        ).all()
    )


def trigger_alert(
    database_session: Session,
    fixture,
    *,
    price: Decimal,
    settings=None,
) -> int:
    """Run one price capture against the fixture's alert."""

    triggered = evaluate_price_alerts_for_capture(
        database_session,
        canonical_product_id=fixture.product.id,
        listing_id=fixture.listing.id,
        current_price=price,
        currency="PKR",
        marketplace_name="Daraz Test Marketplace",
    )

    database_session.commit()

    if settings is not None:
        dispatch_pending_deliveries(
            database_session,
            event_ids=user_event_ids(
                database_session,
                user_id=fixture.user.id,
            ),
            settings=settings,
        )

    return triggered


def delivery_for(
    database_session: Session,
    *,
    user_id: int,
    channel: str,
) -> NotificationDelivery | None:
    """Return one user's delivery row for a channel."""

    query = (
        select(NotificationDelivery)
        .where(
            NotificationDelivery.user_id == user_id,
            NotificationDelivery.channel == channel,
        )
        .order_by(NotificationDelivery.id.desc())
        .limit(1)
    )

    return database_session.scalar(query)


def test_price_alert_trigger_sends_email(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A crossed target delivers one email to the alert owner."""

    fixture = create_consumer_alert_fixture(
        database_session,
        target_price=Decimal("100000.00"),
        with_push_subscription=False,
    )

    transport = RecordingEmailTransport()

    monkeypatch.setattr(
        notification_dispatcher,
        "send_email",
        transport,
    )

    settings = notification_settings()

    assert (
        trigger_alert(
            database_session,
            fixture,
            price=Decimal("97500.00"),
            settings=settings,
        )
        == 1
    )

    assert transport.recipients == [fixture.user.email]

    _recipient, content = transport.sent[0]

    assert content.subject == (
        "Price Alert: Samsung Galaxy A55 reached your target"
    )
    assert "PKR 97,500.00" in content.html_body
    assert "PKR 100,000.00" in content.html_body
    assert "Daraz Test Marketplace" in content.html_body
    assert "http://localhost:5173/products/" in content.html_body

    # The plain-text fallback carries the same facts.
    assert "PKR 97,500.00" in content.text_body
    assert "PKR 100,000.00" in content.text_body

    email_delivery = delivery_for(
        database_session,
        user_id=fixture.user.id,
        channel="email",
    )

    assert email_delivery is not None
    assert email_delivery.status == "delivered"
    assert email_delivery.attempts == 1
    assert email_delivery.delivered_at is not None


def test_disabled_email_preference_sends_nothing(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user who disabled email receives only the in-app notification."""

    fixture = create_consumer_alert_fixture(
        database_session,
        price_alert_email=False,
        with_push_subscription=False,
    )

    transport = RecordingEmailTransport()

    monkeypatch.setattr(
        notification_dispatcher,
        "send_email",
        transport,
    )

    trigger_alert(
        database_session,
        fixture,
        price=Decimal("90000.00"),
        settings=notification_settings(),
    )

    assert transport.sent == []

    email_delivery = delivery_for(
        database_session,
        user_id=fixture.user.id,
        channel="email",
    )

    assert email_delivery is not None
    assert email_delivery.status == "skipped"
    assert "disabled by the user" in email_delivery.failure_reason

    in_app_count = database_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == fixture.user.id,
        )
    )

    assert in_app_count == 1


def test_missing_sender_configuration_does_not_crash(
    database_session: Session,
) -> None:
    """An unconfigured SMTP server skips email without raising.

    The real email service runs here: it refuses before opening any
    connection, so no transport is mocked.
    """

    fixture = create_consumer_alert_fixture(
        database_session,
        with_push_subscription=False,
    )

    trigger_alert(
        database_session,
        fixture,
        price=Decimal("80000.00"),
        settings=settings_without_email(),
    )

    email_delivery = delivery_for(
        database_session,
        user_id=fixture.user.id,
        channel="email",
    )

    assert email_delivery is not None
    assert email_delivery.status == "skipped"
    assert "not configured" in email_delivery.failure_reason


def test_user_without_email_address_does_not_crash(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blank account email skips the channel instead of failing."""

    fixture = create_consumer_alert_fixture(
        database_session,
        with_push_subscription=False,
    )

    fixture.user.email = "   "
    database_session.commit()

    transport = RecordingEmailTransport()

    monkeypatch.setattr(
        notification_dispatcher,
        "send_email",
        transport,
    )

    triggered = trigger_alert(
        database_session,
        fixture,
        price=Decimal("75000.00"),
        settings=notification_settings(),
    )

    assert triggered == 1
    assert transport.sent == []

    email_delivery = delivery_for(
        database_session,
        user_id=fixture.user.id,
        channel="email",
    )

    assert email_delivery is not None
    assert email_delivery.status == "skipped"
    assert "No email address" in email_delivery.failure_reason

    in_app_count = database_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == fixture.user.id,
        )
    )

    assert in_app_count == 1


def test_smtp_failure_preserves_in_app_notification_and_alert(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A transient SMTP error never rolls back the core transaction."""

    fixture = create_consumer_alert_fixture(
        database_session,
        with_push_subscription=False,
    )

    transport = RecordingEmailTransport(
        error=EmailDeliveryError("Connection refused"),
    )

    monkeypatch.setattr(
        notification_dispatcher,
        "send_email",
        transport,
    )

    triggered = trigger_alert(
        database_session,
        fixture,
        price=Decimal("95000.00"),
        settings=notification_settings(),
    )

    assert triggered == 1

    database_session.refresh(fixture.alert)

    assert fixture.alert.is_triggered is True
    assert fixture.alert.notification_count == 1

    notifications = list(
        database_session.scalars(
            select(Notification).where(
                Notification.user_id == fixture.user.id,
            )
        ).all()
    )

    assert len(notifications) == 1
    assert notifications[0].notification_type == "price_drop"

    email_delivery = delivery_for(
        database_session,
        user_id=fixture.user.id,
        channel="email",
    )

    assert email_delivery is not None
    assert email_delivery.status == "failed"
    assert email_delivery.attempts == 1
    assert "Connection refused" in email_delivery.failure_reason


def test_permanent_smtp_rejection_is_not_retried(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A rejected recipient is skipped rather than retried forever."""

    fixture = create_consumer_alert_fixture(
        database_session,
        with_push_subscription=False,
    )

    transport = RecordingEmailTransport(
        error=EmailDeliveryError(
            "Recipient refused",
            is_permanent=True,
        ),
    )

    monkeypatch.setattr(
        notification_dispatcher,
        "send_email",
        transport,
    )

    settings = notification_settings()

    trigger_alert(
        database_session,
        fixture,
        price=Decimal("95000.00"),
        settings=settings,
    )

    email_delivery = delivery_for(
        database_session,
        user_id=fixture.user.id,
        channel="email",
    )

    assert email_delivery is not None
    assert email_delivery.status == "skipped"

    summary = dispatch_pending_deliveries(
        database_session,
        event_ids=user_event_ids(
            database_session,
            user_id=fixture.user.id,
        ),
        settings=settings,
    )

    assert summary["attempted"] == 0


def test_failed_email_retries_within_bounded_budget(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retries stop at NOTIFICATION_DELIVERY_MAX_ATTEMPTS."""

    fixture = create_consumer_alert_fixture(
        database_session,
        with_push_subscription=False,
    )

    transport = RecordingEmailTransport(
        error=EmailDeliveryError("Temporary outage"),
    )

    monkeypatch.setattr(
        notification_dispatcher,
        "send_email",
        transport,
    )

    settings = notification_settings(
        notification_delivery_max_attempts=2,
    )

    trigger_alert(
        database_session,
        fixture,
        price=Decimal("95000.00"),
        settings=settings,
    )

    email_delivery = delivery_for(
        database_session,
        user_id=fixture.user.id,
        channel="email",
    )

    assert email_delivery is not None
    assert email_delivery.attempts == 1

    second_summary = dispatch_pending_deliveries(
        database_session,
        event_ids=user_event_ids(
            database_session,
            user_id=fixture.user.id,
        ),
        settings=settings,
    )

    assert second_summary["attempted"] == 1

    database_session.refresh(email_delivery)

    assert email_delivery.attempts == 2

    third_summary = dispatch_pending_deliveries(
        database_session,
        event_ids=user_event_ids(
            database_session,
            user_id=fixture.user.id,
        ),
        settings=settings,
    )

    assert third_summary["attempted"] == 0

    database_session.refresh(email_delivery)

    assert email_delivery.attempts == 2
    assert email_delivery.status == "failed"


def test_unconfigured_smtp_raises_from_email_service() -> None:
    """The email service refuses to send without a host."""

    from app.services.email_service import EmailContent, send_email

    with pytest.raises(EmailNotConfiguredError):
        send_email(
            recipient="someone@example.com",
            content=EmailContent(
                subject="Test",
                html_body="<p>Test</p>",
                text_body="Test",
            ),
            settings=settings_without_email(),
        )


def test_duplicate_event_does_not_send_a_second_email(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Re-processing the same observation cannot duplicate the email."""

    fixture = create_consumer_alert_fixture(
        database_session,
        with_push_subscription=False,
    )

    transport = RecordingEmailTransport()

    monkeypatch.setattr(
        notification_dispatcher,
        "send_email",
        transport,
    )

    settings = notification_settings()

    trigger_alert(
        database_session,
        fixture,
        price=Decimal("97500.00"),
        settings=settings,
    )

    assert len(transport.sent) == 1

    # Simulate a job that committed its deliveries but whose alert state
    # was replayed: the same arming generation is evaluated again, which
    # rebuilds the identical event key.
    fixture.alert.is_triggered = False
    fixture.alert.notification_count = 0
    database_session.commit()

    trigger_alert(
        database_session,
        fixture,
        price=Decimal("97500.00"),
        settings=settings,
    )

    assert len(transport.sent) == 1

    event_count = database_session.scalar(
        select(func.count(NotificationEvent.id)).where(
            NotificationEvent.user_id == fixture.user.id,
        )
    )

    assert event_count == 1

    notification_count = database_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == fixture.user.id,
        )
    )

    assert notification_count == 1
