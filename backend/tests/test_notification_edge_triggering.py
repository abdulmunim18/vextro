"""Module 6.14 edge-triggering tests for price alerts and competitor risk.

Price alerts are **one-time**: the first qualifying observation latches
``is_triggered`` and the alert stays quiet afterwards. It re-arms only when
its owner reactivates it through the API, which also starts a new event
key generation. These tests pin that behaviour down.
"""

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.notification_event import NotificationEvent
from app.repositories.price_alert_repository import update_price_alert
from app.services import notification_dispatcher
from app.services.competitor_alert_service import (
    evaluate_competitor_risk_alerts,
)
from tests.notification_factories import (
    RecordingEmailTransport,
    RecordingPushTransport,
    create_consumer_alert_fixture,
    create_sme_risk_fixture,
    notification_settings,
)
from tests.test_notification_email_delivery import (
    trigger_alert,
    user_event_ids,
)


def notification_count(
    database_session: Session,
    *,
    user_id: int,
    notification_type: str | None = None,
) -> int:
    """Count a user's in-app notifications."""

    query = select(func.count(Notification.id)).where(
        Notification.user_id == user_id,
    )

    if notification_type is not None:
        query = query.where(
            Notification.notification_type == notification_type,
        )

    return int(database_session.scalar(query) or 0)


@pytest.fixture
def transports(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[RecordingEmailTransport, RecordingPushTransport]:
    """Capture both secondary channels for one test."""

    email_transport = RecordingEmailTransport()
    push_transport = RecordingPushTransport()

    monkeypatch.setattr(
        notification_dispatcher,
        "send_email",
        email_transport,
    )
    monkeypatch.setattr(
        notification_dispatcher,
        "send_web_push",
        push_transport,
    )

    return email_transport, push_transport


def test_price_above_target_never_notifies(
    database_session: Session,
    transports,
) -> None:
    """An observation above the target produces nothing at all."""

    email_transport, push_transport = transports

    fixture = create_consumer_alert_fixture(
        database_session,
        target_price=Decimal("100000.00"),
    )

    assert (
        trigger_alert(
            database_session,
            fixture,
            price=Decimal("105000.00"),
            settings=notification_settings(),
        )
        == 0
    )

    database_session.refresh(fixture.alert)

    assert fixture.alert.is_triggered is False
    assert fixture.alert.notification_count == 0
    assert fixture.alert.last_checked_at is not None

    assert email_transport.sent == []
    assert push_transport.sent == []

    assert (
        notification_count(
            database_session,
            user_id=fixture.user.id,
        )
        == 0
    )


def test_crossing_target_notifies_every_channel_once(
    database_session: Session,
    transports,
) -> None:
    """Crossing the target fans out to in-app, email and push exactly once."""

    email_transport, push_transport = transports

    fixture = create_consumer_alert_fixture(
        database_session,
        target_price=Decimal("100000.00"),
    )

    settings = notification_settings()

    assert (
        trigger_alert(
            database_session,
            fixture,
            price=Decimal("105000.00"),
            settings=settings,
        )
        == 0
    )

    assert (
        trigger_alert(
            database_session,
            fixture,
            price=Decimal("99000.00"),
            settings=settings,
        )
        == 1
    )

    assert (
        notification_count(
            database_session,
            user_id=fixture.user.id,
            notification_type="price_drop",
        )
        == 1
    )

    assert len(email_transport.sent) == 1
    assert len(push_transport.sent) == 1


def test_staying_below_target_never_spams(
    database_session: Session,
    transports,
) -> None:
    """Further observations below the target send nothing more."""

    email_transport, push_transport = transports

    fixture = create_consumer_alert_fixture(
        database_session,
        target_price=Decimal("100000.00"),
    )

    settings = notification_settings()

    trigger_alert(
        database_session,
        fixture,
        price=Decimal("99000.00"),
        settings=settings,
    )

    for lower_price in (
        Decimal("98500.00"),
        Decimal("98000.00"),
    ):
        assert (
            trigger_alert(
                database_session,
                fixture,
                price=lower_price,
                settings=settings,
            )
            == 0
        )

    # A rebound above the target does not re-arm a one-time alert.
    assert (
        trigger_alert(
            database_session,
            fixture,
            price=Decimal("103000.00"),
            settings=settings,
        )
        == 0
    )

    assert (
        trigger_alert(
            database_session,
            fixture,
            price=Decimal("97000.00"),
            settings=settings,
        )
        == 0
    )

    assert (
        notification_count(
            database_session,
            user_id=fixture.user.id,
            notification_type="price_drop",
        )
        == 1
    )

    assert len(email_transport.sent) == 1
    assert len(push_transport.sent) == 1


def test_owner_reactivation_rearms_the_alert(
    database_session: Session,
    transports,
) -> None:
    """Reactivating a triggered alert allows exactly one new notification."""

    email_transport, push_transport = transports

    fixture = create_consumer_alert_fixture(
        database_session,
        target_price=Decimal("100000.00"),
    )

    settings = notification_settings()

    trigger_alert(
        database_session,
        fixture,
        price=Decimal("99000.00"),
        settings=settings,
    )

    assert len(email_transport.sent) == 1

    # Deactivate then reactivate through the repository the API uses.
    update_price_alert(
        database_session,
        fixture.alert,
        is_active=False,
    )
    update_price_alert(
        database_session,
        fixture.alert,
        is_active=True,
    )

    database_session.commit()
    database_session.refresh(fixture.alert)

    assert fixture.alert.is_triggered is False

    assert (
        trigger_alert(
            database_session,
            fixture,
            price=Decimal("96000.00"),
            settings=settings,
        )
        == 1
    )

    assert (
        notification_count(
            database_session,
            user_id=fixture.user.id,
            notification_type="price_drop",
        )
        == 2
    )

    assert len(email_transport.sent) == 2
    assert len(push_transport.sent) == 2

    event_keys = sorted(
        database_session.scalars(
            select(NotificationEvent.event_key).where(
                NotificationEvent.user_id == fixture.user.id,
            )
        ).all()
    )

    assert event_keys == [
        f"price_alert:{fixture.alert.id}:trigger:0",
        f"price_alert:{fixture.alert.id}:trigger:1",
    ]


def dispatch_competitor_risk(
    database_session: Session,
    fixture,
    *,
    competitor_price: Decimal,
    settings=None,
) -> int:
    """Evaluate one competitor observation and flush its deliveries."""

    triggered = evaluate_competitor_risk_alerts(
        database_session,
        listing_id=fixture.listing.id,
        competitor_price=competitor_price,
        currency="PKR",
        marketplace_name="Daraz Test Marketplace",
    )

    database_session.commit()

    if settings is not None:
        notification_dispatcher.dispatch_pending_deliveries(
            database_session,
            event_ids=user_event_ids(
                database_session,
                user_id=fixture.owner.id,
            ),
            settings=settings,
        )

    return triggered


def test_low_to_high_risk_notifies_every_channel(
    database_session: Session,
    transports,
) -> None:
    """A LOW to HIGH transition reaches in-app, email and push."""

    email_transport, push_transport = transports

    fixture = create_sme_risk_fixture(
        database_session,
        own_price=Decimal("120000.00"),
        risk_threshold_percentage=Decimal("5.00"),
        last_risk_level="low",
    )

    assert (
        dispatch_competitor_risk(
            database_session,
            fixture,
            competitor_price=Decimal("100000.00"),
            settings=notification_settings(),
        )
        == 1
    )

    database_session.refresh(fixture.watchlist)

    assert fixture.watchlist.last_risk_level == "high"
    assert fixture.watchlist.last_alerted_at is not None

    assert (
        notification_count(
            database_session,
            user_id=fixture.owner.id,
            notification_type="competitor_risk",
        )
        == 1
    )

    assert len(email_transport.sent) == 1
    assert len(push_transport.sent) == 1

    _recipient, content = email_transport.sent[0]

    assert "Competitor Alert" in content.subject
    assert "PKR 100,000.00" in content.html_body
    assert "PKR 120,000.00" in content.html_body
    assert "HIGH" in content.html_body

    _endpoint, message = push_transport.sent[0]

    assert message.title == "Competitor price risk detected"
    assert "pricing position" in message.body


def test_high_to_high_risk_does_not_spam(
    database_session: Session,
    transports,
) -> None:
    """Risk staying high sends nothing further."""

    email_transport, push_transport = transports

    fixture = create_sme_risk_fixture(
        database_session,
        own_price=Decimal("120000.00"),
        last_risk_level="low",
    )

    settings = notification_settings()

    dispatch_competitor_risk(
        database_session,
        fixture,
        competitor_price=Decimal("100000.00"),
        settings=settings,
    )

    assert (
        dispatch_competitor_risk(
            database_session,
            fixture,
            competitor_price=Decimal("99000.00"),
            settings=settings,
        )
        == 0
    )

    assert (
        notification_count(
            database_session,
            user_id=fixture.owner.id,
            notification_type="competitor_risk",
        )
        == 1
    )

    assert len(email_transport.sent) == 1
    assert len(push_transport.sent) == 1


def test_medium_to_high_risk_notifies_again(
    database_session: Session,
    transports,
) -> None:
    """Risk easing to medium and returning to high raises a new alert."""

    email_transport, push_transport = transports

    fixture = create_sme_risk_fixture(
        database_session,
        own_price=Decimal("120000.00"),
        risk_threshold_percentage=Decimal("10.00"),
        last_risk_level="low",
    )

    settings = notification_settings()

    assert (
        dispatch_competitor_risk(
            database_session,
            fixture,
            competitor_price=Decimal("100000.00"),
            settings=settings,
        )
        == 1
    )

    # 120000 vs 118000 is a 1.69% gap: medium, not high.
    assert (
        dispatch_competitor_risk(
            database_session,
            fixture,
            competitor_price=Decimal("118000.00"),
            settings=settings,
        )
        == 0
    )

    database_session.refresh(fixture.watchlist)

    assert fixture.watchlist.last_risk_level == "medium"

    assert (
        dispatch_competitor_risk(
            database_session,
            fixture,
            competitor_price=Decimal("95000.00"),
            settings=settings,
        )
        == 1
    )

    assert (
        notification_count(
            database_session,
            user_id=fixture.owner.id,
            notification_type="competitor_risk",
        )
        == 2
    )

    assert len(email_transport.sent) == 2
    assert len(push_transport.sent) == 2


def test_competitor_risk_respects_disabled_channels(
    database_session: Session,
    transports,
) -> None:
    """An SME who disabled both extras still gets the in-app alert."""

    email_transport, push_transport = transports

    fixture = create_sme_risk_fixture(
        database_session,
        own_price=Decimal("120000.00"),
        last_risk_level="low",
        competitor_alert_email=False,
        competitor_alert_push=False,
    )

    assert (
        dispatch_competitor_risk(
            database_session,
            fixture,
            competitor_price=Decimal("100000.00"),
            settings=notification_settings(),
        )
        == 1
    )

    assert email_transport.sent == []
    assert push_transport.sent == []

    assert (
        notification_count(
            database_session,
            user_id=fixture.owner.id,
            notification_type="competitor_risk",
        )
        == 1
    )


def test_replayed_competitor_observation_is_idempotent(
    database_session: Session,
    transports,
) -> None:
    """Re-evaluating the same observation cannot duplicate the alert."""

    email_transport, push_transport = transports

    fixture = create_sme_risk_fixture(
        database_session,
        own_price=Decimal("120000.00"),
        last_risk_level="low",
    )

    settings = notification_settings()

    dispatch_competitor_risk(
        database_session,
        fixture,
        competitor_price=Decimal("100000.00"),
        settings=settings,
    )

    # Rewind the risk latch the way a rolled-back job would.
    fixture.watchlist.last_risk_level = "low"
    database_session.commit()

    assert (
        dispatch_competitor_risk(
            database_session,
            fixture,
            competitor_price=Decimal("100000.00"),
            settings=settings,
        )
        == 0
    )

    assert (
        notification_count(
            database_session,
            user_id=fixture.owner.id,
            notification_type="competitor_risk",
        )
        == 1
    )

    assert len(email_transport.sent) == 1
    assert len(push_transport.sent) == 1
