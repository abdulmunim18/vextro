"""Module 6.14 end-to-end flow through the real ingestion API.

This exercises the complete acceptance path:

    POST /api/v1/internal/acquisition/listings
      -> price observation committed
      -> price alert evaluated and latched
      -> notification event recorded
      -> in-app notification, email and Web Push dispatched

plus the regression surface the module must not break: the notification
bell list, the unread counter, mark-read, mark-all-read and the existing
PDF and Excel report generators.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.notification_delivery import NotificationDelivery
from app.models.notification_event import NotificationEvent
from app.services import notification_dispatcher
from tests.notification_factories import (
    RecordingEmailTransport,
    RecordingPushTransport,
    create_preference,
    create_push_subscription,
    notification_settings,
)
from tests.test_acquisition import (  # noqa: F401 - pytest fixtures
    BASE_CAPTURE_TIME,
    ENDPOINT,
    acquisition_alert_context,
    acquisition_context,
    build_payload,
    configure_ingestion_key,
    ingestion_headers,
)


@pytest.fixture
def captured_transports(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[RecordingEmailTransport, RecordingPushTransport]:
    """Capture email and push, and pin test SMTP/VAPID settings.

    ``AcquisitionService`` flushes the whole outbox with the application's
    own settings, so the dispatcher's settings object is patched too, and
    any delivery another test deliberately left failed is retired first.
    Otherwise this test would observe those retries as its own sends.
    """

    database_session.execute(
        update(NotificationDelivery)
        .where(
            NotificationDelivery.status.in_(
                ["pending", "failed"],
            ),
        )
        .values(
            status="skipped",
            failure_reason="Retired by the end-to-end test fixture.",
        )
    )

    database_session.commit()

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
    monkeypatch.setattr(
        notification_dispatcher,
        "default_settings",
        notification_settings(),
    )

    return email_transport, push_transport


def ingest_price(
    client: TestClient,
    context: dict[str, object],
    *,
    price: int,
    minute_offset: int,
) -> dict:
    """Post one marketplace capture through the ingestion API."""

    payload = build_payload(
        context,
        captured_at=BASE_CAPTURE_TIME
        + timedelta(minutes=minute_offset),
        current_price=price,
    )

    response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=payload,
    )

    assert response.status_code in {200, 201}, response.text

    return response.json()


def test_full_consumer_price_alert_flow(
    client: TestClient,
    database_session: Session,
    acquisition_context: dict[str, object],  # noqa: F811
    acquisition_alert_context: dict[str, object],  # noqa: F811
    captured_transports,
) -> None:
    """One ingestion run drives all three channels exactly once."""

    email_transport, push_transport = captured_transports

    user_id = int(acquisition_alert_context["user_id"])

    create_preference(
        database_session,
        user_id=user_id,
        price_alert_email=True,
        price_alert_push=True,
    )

    create_push_subscription(
        database_session,
        user_id=user_id,
    )

    database_session.commit()

    # The alert target is PKR 115,000. An observation above it is silent.
    above_target = ingest_price(
        client,
        acquisition_context,
        price=120000,
        minute_offset=0,
    )

    assert above_target["alerts_triggered"] == 0
    assert email_transport.sent == []
    assert push_transport.sent == []

    # Crossing the target fans out to every enabled channel.
    crossed = ingest_price(
        client,
        acquisition_context,
        price=114000,
        minute_offset=1,
    )

    assert crossed["alerts_triggered"] == 1

    database_session.expire_all()

    notifications = list(
        database_session.scalars(
            select(Notification).where(
                Notification.user_id == user_id,
            )
        ).all()
    )

    assert len(notifications) == 1
    assert notifications[0].notification_type == "price_drop"
    assert notifications[0].is_read is False
    assert notifications[0].action_path == (
        f"/products/{acquisition_context['product_id']}"
    )

    assert len(email_transport.sent) == 1
    assert len(push_transport.sent) == 1

    _recipient, content = email_transport.sent[0]

    assert "reached your target" in content.subject
    assert "PKR 114,000.00" in content.html_body
    assert "PKR 115,000.00" in content.html_body
    assert "http://localhost:5173/products/" in content.html_body

    deliveries = {
        delivery.channel: delivery
        for delivery in database_session.scalars(
            select(NotificationDelivery).where(
                NotificationDelivery.user_id == user_id,
            )
        ).all()
    }

    assert deliveries["in_app"].status == "delivered"
    assert deliveries["email"].status == "delivered"
    assert deliveries["web_push"].status == "delivered"

    # A further observation below target must not notify again.
    lower = ingest_price(
        client,
        acquisition_context,
        price=110000,
        minute_offset=2,
    )

    assert lower["alerts_triggered"] == 0
    assert len(email_transport.sent) == 1
    assert len(push_transport.sent) == 1

    database_session.expire_all()

    assert (
        database_session.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user_id,
            )
        )
        == 1
    )

    assert (
        database_session.scalar(
            select(func.count(NotificationEvent.id)).where(
                NotificationEvent.user_id == user_id,
            )
        )
        == 1
    )

    # Re-posting the exact same capture is a duplicate, not a new alert.
    duplicate_payload = build_payload(
        acquisition_context,
        captured_at=BASE_CAPTURE_TIME + timedelta(minutes=1),
        current_price=114000,
    )

    duplicate_response = client.post(
        ENDPOINT,
        headers=ingestion_headers(),
        json=duplicate_payload,
    )

    assert duplicate_response.status_code in {200, 201}
    assert duplicate_response.json()["status"] == "duplicate"

    assert len(email_transport.sent) == 1
    assert len(push_transport.sent) == 1


def test_notification_bell_regression_surface(
    client: TestClient,
    database_session: Session,
) -> None:
    """The bell list, unread count and both mark-read routes still work."""

    from uuid import uuid4

    from app.repositories.notification_repository import (
        create_notification,
    )
    from app.models.user import User

    email = f"bell-regression-{uuid4().hex[:10]}@example.com"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Bell Regression User",
            "email": email,
            "password": "StrongPassword123!",
            "account_type": "consumer",
        },
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "StrongPassword123!",
        },
    )

    assert login_response.status_code == 200

    headers = {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        ),
    }

    user = database_session.scalar(
        select(User).where(User.email == email)
    )

    assert user is not None

    for index in range(3):
        create_notification(
            database_session,
            user_id=user.id,
            notification_type="price_drop",
            title=f"Regression notification {index}",
            message="Regression message",
            action_path="/alerts",
        )

    database_session.commit()

    list_response = client.get(
        "/api/v1/notifications",
        headers=headers,
    )

    assert list_response.status_code == 200

    body = list_response.json()

    assert body["total"] == 3
    assert body["unread_count"] == 3
    assert len(body["items"]) == 3

    count_response = client.get(
        "/api/v1/notifications/unread-count",
        headers=headers,
    )

    assert count_response.status_code == 200
    assert count_response.json()["unread_count"] == 3

    first_notification_id = body["items"][0]["id"]

    read_response = client.patch(
        f"/api/v1/notifications/{first_notification_id}/read",
        headers=headers,
    )

    assert read_response.status_code == 200
    assert read_response.json()["is_read"] is True

    assert (
        client.get(
            "/api/v1/notifications/unread-count",
            headers=headers,
        ).json()["unread_count"]
        == 2
    )

    read_all_response = client.patch(
        "/api/v1/notifications/read-all",
        headers=headers,
    )

    assert read_all_response.status_code == 200
    assert read_all_response.json()["updated_count"] == 2
    assert read_all_response.json()["unread_count"] == 0

    unread_only_response = client.get(
        "/api/v1/notifications",
        headers=headers,
        params={"unread_only": True},
    )

    assert unread_only_response.status_code == 200
    assert unread_only_response.json()["items"] == []


def test_existing_report_generators_still_work() -> None:
    """The PDF and Excel generators module 6.14 reuses are intact."""

    from datetime import UTC, datetime

    from app.schemas.sme import (
        CompetitorInsightResponse,
        CompetitorIntelligenceResponse,
        CompetitorIntelligenceSummary,
    )
    from app.services.competitor_report_service import (
        build_competitor_pdf,
        build_competitor_xlsx,
    )

    intelligence = CompetitorIntelligenceResponse(
        organization_id=1,
        generated_at=datetime.now(UTC),
        summary=CompetitorIntelligenceSummary(
            tracked_competitors=1,
            tracked_products=1,
            average_price_gap=Decimal("20000.00"),
            products_at_risk=1,
            estimated_average_market_share_percentage=Decimal("35.00"),
            risk_threshold_percentage=Decimal("5.00"),
            estimation_note="Estimated from tracked listings only.",
        ),
        items=[
            CompetitorInsightResponse(
                watchlist_id=1,
                business_product_id=1,
                listing_id=1,
                own_product_name="Samsung Galaxy A55 (our stock)",
                own_price=Decimal("120000.00"),
                competitor_price=Decimal("100000.00"),
                currency="PKR",
                platform_name="Daraz",
                seller_name="Competitor Seller",
                price_gap=Decimal("20000.00"),
                price_gap_percentage=Decimal("20.00"),
                price_position="above",
                risk_level="high",
                risk_reasons=["Competitor is 20% cheaper"],
                estimated_own_market_share_percentage=Decimal("35.00"),
            )
        ],
    )

    pdf_bytes = build_competitor_pdf(
        organization_name="Notify Traders",
        intelligence=intelligence,
    )

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1000

    xlsx_bytes = build_competitor_xlsx(
        organization_name="Notify Traders",
        intelligence=intelligence,
    )

    assert xlsx_bytes.startswith(b"PK")
    assert len(xlsx_bytes) > 1000
