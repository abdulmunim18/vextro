"""Module 6.14 scheduled digest report tests."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.digest_run import DigestRun
from app.models.notification_event import NotificationEvent
from app.services import digest_service
from app.services.digest_service import (
    build_digest_payload,
    resolve_digest_period,
    run_digest_cycle,
    send_user_digest,
)
from tests.notification_factories import (
    RecordingEmailTransport,
    create_consumer_alert_fixture,
    create_preference,
    create_sme_risk_fixture,
    create_user,
    notification_settings,
)


def seed_price_drop_event(
    database_session: Session,
    *,
    user_id: int,
    created_at: datetime,
    product_name: str = "Samsung Galaxy A55",
    current_price: str = "97500.00",
    target_price: str = "100000.00",
) -> NotificationEvent:
    """Record one historical price-drop event at a chosen moment."""

    event = NotificationEvent(
        user_id=user_id,
        event_key=(
            f"test:price_drop:{user_id}:{created_at.isoformat()}"
        ),
        event_type="price_drop",
        title="Price target reached",
        body="Price target reached",
        action_path="/alerts",
        payload={
            "product_name": product_name,
            "current_price": current_price,
            "target_price": target_price,
            "currency": "PKR",
            "marketplace": "Daraz Test Marketplace",
        },
        created_at=created_at,
    )

    database_session.add(event)
    database_session.flush()
    database_session.commit()

    return event


def seed_competitor_event(
    database_session: Session,
    *,
    user_id: int,
    created_at: datetime,
) -> NotificationEvent:
    """Record one historical competitor-risk event."""

    event = NotificationEvent(
        user_id=user_id,
        event_key=(
            f"test:competitor_risk:{user_id}:{created_at.isoformat()}"
        ),
        event_type="competitor_risk",
        title="Competitor price risk detected",
        body="Competitor price risk detected",
        action_path="/sme",
        payload={
            "product_name": "Samsung Galaxy A55 (our stock)",
            "own_price": "120000.00",
            "competitor_price": "100000.00",
            "price_gap_percentage": "20.00",
            "risk_level": "high",
            "currency": "PKR",
        },
        created_at=created_at,
    )

    database_session.add(event)
    database_session.flush()
    database_session.commit()

    return event


def test_daily_period_covers_the_previous_local_day() -> None:
    """The daily window is yesterday in the configured timezone."""

    settings = notification_settings(
        digest_timezone="Asia/Karachi",
    )

    reference = datetime(
        2026,
        10,
        3,
        8,
        0,
        tzinfo=UTC,
    )

    period = resolve_digest_period(
        frequency="daily",
        reference=reference,
        settings=settings,
    )

    assert period.frequency == "daily"
    assert period.period_key == "2026-10-02"
    assert period.end_utc - period.start_utc == timedelta(days=1)

    # Asia/Karachi is UTC+5, so local midnight is 19:00 UTC the day before.
    assert period.start_utc == datetime(
        2026,
        10,
        1,
        19,
        0,
        tzinfo=UTC,
    )


def test_weekly_period_covers_the_previous_full_week() -> None:
    """The weekly window is the last complete seven-day block."""

    settings = notification_settings(
        digest_timezone="Asia/Karachi",
        digest_weekly_day=0,
    )

    reference = datetime(
        2026,
        10,
        5,
        9,
        0,
        tzinfo=UTC,
    )

    period = resolve_digest_period(
        frequency="weekly",
        reference=reference,
        settings=settings,
    )

    assert period.frequency == "weekly"
    assert period.end_utc - period.start_utc == timedelta(days=7)
    assert period.period_key.startswith("2026-W")


def test_daily_digest_contains_only_the_period_events(
    database_session: Session,
) -> None:
    """Events outside the window are excluded from the payload."""

    settings = notification_settings()

    period = resolve_digest_period(
        frequency="daily",
        settings=settings,
    )

    user = create_user(
        database_session,
        prefix="digest-consumer",
    )

    create_preference(
        database_session,
        user_id=user.id,
        digest_frequency="daily",
    )

    database_session.commit()

    seed_price_drop_event(
        database_session,
        user_id=user.id,
        created_at=period.start_utc + timedelta(hours=2),
        product_name="In Window Product",
    )

    seed_price_drop_event(
        database_session,
        user_id=user.id,
        created_at=period.start_utc - timedelta(days=3),
        product_name="Too Old Product",
    )

    seed_price_drop_event(
        database_session,
        user_id=user.id,
        created_at=period.end_utc + timedelta(hours=1),
        product_name="Too New Product",
    )

    payload = build_digest_payload(
        database_session,
        user_id=user.id,
        period=period,
    )

    assert payload is not None
    assert payload["frequency"] == "daily"
    assert payload["audience"] == "consumer"
    assert payload["event_count"] == 1

    all_lines = "\n".join(
        line
        for section in payload["sections"]
        for line in section["lines"]
    )

    assert "In Window Product" in all_lines
    assert "Too Old Product" not in all_lines
    assert "Too New Product" not in all_lines


def test_weekly_digest_uses_the_weekly_window(
    database_session: Session,
) -> None:
    """A weekly digest reads the weekly period, not the daily one."""

    settings = notification_settings()

    weekly_period = resolve_digest_period(
        frequency="weekly",
        settings=settings,
    )

    user = create_user(
        database_session,
        prefix="digest-weekly",
    )

    create_preference(
        database_session,
        user_id=user.id,
        digest_frequency="weekly",
    )

    database_session.commit()

    seed_price_drop_event(
        database_session,
        user_id=user.id,
        created_at=weekly_period.start_utc + timedelta(days=2),
        product_name="Mid Week Product",
    )

    payload = build_digest_payload(
        database_session,
        user_id=user.id,
        period=weekly_period,
    )

    assert payload is not None
    assert payload["frequency"] == "weekly"
    assert payload["event_count"] == 1

    daily_period = resolve_digest_period(
        frequency="daily",
        settings=settings,
    )

    daily_payload = build_digest_payload(
        database_session,
        user_id=user.id,
        period=daily_period,
    )

    # The same event is outside yesterday's window.
    assert daily_payload is None


def test_empty_digest_is_not_sent(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A quiet period produces no email at all."""

    transport = RecordingEmailTransport()

    monkeypatch.setattr(
        digest_service,
        "send_email",
        transport,
    )

    settings = notification_settings()

    user = create_user(
        database_session,
        prefix="digest-empty",
    )

    create_preference(
        database_session,
        user_id=user.id,
        digest_frequency="daily",
    )

    database_session.commit()

    period = resolve_digest_period(
        frequency="daily",
        settings=settings,
    )

    status = send_user_digest(
        database_session,
        user_id=user.id,
        period=period,
        settings=settings,
    )

    assert status == "skipped_empty"
    assert transport.sent == []

    run = database_session.scalar(
        select(DigestRun).where(
            DigestRun.user_id == user.id,
        )
    )

    assert run is not None
    assert run.status == "skipped_empty"
    assert run.event_count == 0


def test_digest_is_delivered_once_per_period(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second scheduler firing for the same period sends nothing."""

    transport = RecordingEmailTransport()

    monkeypatch.setattr(
        digest_service,
        "send_email",
        transport,
    )

    settings = notification_settings()

    period = resolve_digest_period(
        frequency="daily",
        settings=settings,
    )

    user = create_user(
        database_session,
        prefix="digest-once",
    )

    create_preference(
        database_session,
        user_id=user.id,
        digest_frequency="daily",
    )

    database_session.commit()

    seed_price_drop_event(
        database_session,
        user_id=user.id,
        created_at=period.start_utc + timedelta(hours=3),
    )

    first_status = send_user_digest(
        database_session,
        user_id=user.id,
        period=period,
        settings=settings,
    )

    assert first_status == "delivered"
    assert len(transport.sent) == 1

    _recipient, content = transport.sent[0]

    assert "Daily Digest" in content.subject
    assert "Samsung Galaxy A55" in content.html_body
    assert "Samsung Galaxy A55" in content.text_body
    assert content.attachments == ()

    second_status = send_user_digest(
        database_session,
        user_id=user.id,
        period=period,
        settings=settings,
    )

    assert second_status == "duplicate"
    assert len(transport.sent) == 1

    run_count = database_session.scalar(
        select(func.count(DigestRun.id)).where(
            DigestRun.user_id == user.id,
        )
    )

    assert run_count == 1


def test_disabled_digest_is_never_sent(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user with digests off is not even a candidate."""

    transport = RecordingEmailTransport()

    monkeypatch.setattr(
        digest_service,
        "send_email",
        transport,
    )

    settings = notification_settings()

    period = resolve_digest_period(
        frequency="daily",
        settings=settings,
    )

    user = create_user(
        database_session,
        prefix="digest-off",
    )

    create_preference(
        database_session,
        user_id=user.id,
        digest_frequency="off",
    )

    database_session.commit()

    seed_price_drop_event(
        database_session,
        user_id=user.id,
        created_at=period.start_utc + timedelta(hours=3),
    )

    run_digest_cycle(
        database_session,
        frequency="daily",
        settings=settings,
    )

    assert all(
        recipient != user.email
        for recipient in transport.recipients
    )

    run_count = database_session.scalar(
        select(func.count(DigestRun.id)).where(
            DigestRun.user_id == user.id,
        )
    )

    assert run_count == 0


def test_sme_digest_reports_competitor_events(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An SME owner's digest summarizes competitor risk, not price alerts."""

    transport = RecordingEmailTransport()

    monkeypatch.setattr(
        digest_service,
        "send_email",
        transport,
    )

    settings = notification_settings(
        digest_attach_sme_report=False,
    )

    period = resolve_digest_period(
        frequency="daily",
        settings=settings,
    )

    fixture = create_sme_risk_fixture(
        database_session,
        own_price=Decimal("120000.00"),
        with_push_subscription=False,
    )

    fixture.preference.digest_frequency = "daily"
    database_session.commit()

    seed_competitor_event(
        database_session,
        user_id=fixture.owner.id,
        created_at=period.start_utc + timedelta(hours=4),
    )

    status = send_user_digest(
        database_session,
        user_id=fixture.owner.id,
        period=period,
        settings=settings,
    )

    assert status == "delivered"
    assert len(transport.sent) == 1

    _recipient, content = transport.sent[0]

    assert "Daily Digest" in content.subject
    assert "Competitor risk events" in content.html_body
    assert "PKR 100,000.00" in content.html_body
    assert "/sme" in content.html_body


def test_digest_cycle_processes_only_matching_frequency(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A weekly subscriber is untouched by the daily cycle."""

    transport = RecordingEmailTransport()

    monkeypatch.setattr(
        digest_service,
        "send_email",
        transport,
    )

    settings = notification_settings()

    daily_period = resolve_digest_period(
        frequency="daily",
        settings=settings,
    )

    weekly_user = create_user(
        database_session,
        prefix="digest-weekly-only",
    )

    create_preference(
        database_session,
        user_id=weekly_user.id,
        digest_frequency="weekly",
    )

    database_session.commit()

    seed_price_drop_event(
        database_session,
        user_id=weekly_user.id,
        created_at=daily_period.start_utc + timedelta(hours=2),
    )

    run_digest_cycle(
        database_session,
        frequency="daily",
        settings=settings,
    )

    daily_run_count = database_session.scalar(
        select(func.count(DigestRun.id)).where(
            DigestRun.user_id == weekly_user.id,
            DigestRun.frequency == "daily",
        )
    )

    assert daily_run_count == 0


def test_digest_failure_is_recorded_without_raising(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An SMTP outage records a failed run instead of crashing the job."""

    from app.services.email_service import EmailDeliveryError

    transport = RecordingEmailTransport(
        error=EmailDeliveryError("Connection refused"),
    )

    monkeypatch.setattr(
        digest_service,
        "send_email",
        transport,
    )

    settings = notification_settings()

    period = resolve_digest_period(
        frequency="daily",
        settings=settings,
    )

    user = create_user(
        database_session,
        prefix="digest-failure",
    )

    create_preference(
        database_session,
        user_id=user.id,
        digest_frequency="daily",
    )

    database_session.commit()

    seed_price_drop_event(
        database_session,
        user_id=user.id,
        created_at=period.start_utc + timedelta(hours=1),
    )

    status = send_user_digest(
        database_session,
        user_id=user.id,
        period=period,
        settings=settings,
    )

    assert status == "failed"

    run = database_session.scalar(
        select(DigestRun).where(
            DigestRun.user_id == user.id,
        )
    )

    assert run is not None
    assert run.status == "failed"
    assert "Connection refused" in run.failure_reason


def test_consumer_digest_lists_watching_alerts(
    database_session: Session,
) -> None:
    """A triggered alert digest also shows the alerts still watching."""

    settings = notification_settings()

    period = resolve_digest_period(
        frequency="daily",
        settings=settings,
    )

    fixture = create_consumer_alert_fixture(
        database_session,
        target_price=Decimal("100000.00"),
        with_push_subscription=False,
    )

    fixture.preference.digest_frequency = "daily"
    database_session.commit()

    seed_price_drop_event(
        database_session,
        user_id=fixture.user.id,
        created_at=period.start_utc + timedelta(hours=5),
    )

    payload = build_digest_payload(
        database_session,
        user_id=fixture.user.id,
        period=period,
    )

    assert payload is not None

    section_titles = [
        section["title"] for section in payload["sections"]
    ]

    assert "Price alerts triggered" in section_titles
    assert "Alerts still watching" in section_titles
