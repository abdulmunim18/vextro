"""Module 6.14 Web Push delivery and subscription ownership tests."""

from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.notification import Notification
from app.models.push_subscription import PushSubscription
from app.repositories.push_subscription_repository import hash_endpoint
from app.services import notification_dispatcher
from app.services.web_push_service import WebPushDeliveryError
from tests.notification_factories import (
    RecordingPushTransport,
    create_consumer_alert_fixture,
    create_push_subscription,
    notification_settings,
    unique_value,
)
from tests.test_notification_email_delivery import (
    delivery_for,
    trigger_alert,
)


TEST_PASSWORD = "StrongPassword123!"


def register_and_login(
    client: TestClient,
    *,
    account_type: str = "consumer",
) -> dict[str, str]:
    """Register a user and return their authorization headers."""

    email = f"push-{account_type}-{uuid4().hex[:10]}@example.com"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": f"Push {account_type.title()}",
            "email": email,
            "password": TEST_PASSWORD,
            "account_type": account_type,
        },
    )

    assert register_response.status_code == 202
    verify_response = client.post(
        "/api/v1/auth/verify-email",
        json={"email": email, "otp": "123456"},
    )
    assert verify_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    return {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        ),
    }


def subscription_payload(endpoint: str | None = None) -> dict:
    """Return a browser-shaped subscription payload."""

    return {
        "endpoint": (
            endpoint
            or f"https://push.example.com/{unique_value('ep')}"
        ),
        "keys": {
            "p256dh": unique_value("p256dh-key-material"),
            "auth": unique_value("auth-key"),
        },
    }


def test_valid_subscription_receives_push(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A triggered alert pushes to every active subscription."""

    fixture = create_consumer_alert_fixture(
        database_session,
        target_price=Decimal("100000.00"),
        price_alert_email=False,
    )

    transport = RecordingPushTransport()

    monkeypatch.setattr(
        notification_dispatcher,
        "send_web_push",
        transport,
    )

    assert (
        trigger_alert(
            database_session,
            fixture,
            price=Decimal("97500.00"),
            settings=notification_settings(),
        )
        == 1
    )

    assert len(transport.sent) == 1

    _endpoint, message = transport.sent[0]

    assert message.title == "Price target reached"
    assert "Samsung Galaxy A55" in message.body
    assert "PKR 97,500.00" in message.body
    assert message.action_path == f"/products/{fixture.product.id}"

    push_delivery = delivery_for(
        database_session,
        user_id=fixture.user.id,
        channel="web_push",
    )

    assert push_delivery is not None
    assert push_delivery.status == "delivered"
    assert push_delivery.attempts == 1


def test_disabled_push_preference_sends_nothing(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user who disabled push gets no browser notification."""

    fixture = create_consumer_alert_fixture(
        database_session,
        price_alert_email=False,
        price_alert_push=False,
    )

    transport = RecordingPushTransport()

    monkeypatch.setattr(
        notification_dispatcher,
        "send_web_push",
        transport,
    )

    trigger_alert(
        database_session,
        fixture,
        price=Decimal("90000.00"),
        settings=notification_settings(),
    )

    assert transport.sent == []

    push_delivery = delivery_for(
        database_session,
        user_id=fixture.user.id,
        channel="web_push",
    )

    assert push_delivery is not None
    assert push_delivery.status == "skipped"
    assert "disabled by the user" in push_delivery.failure_reason


def test_no_subscription_does_not_crash(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A user with push enabled but no browser registered is skipped."""

    fixture = create_consumer_alert_fixture(
        database_session,
        price_alert_email=False,
        with_push_subscription=False,
    )

    transport = RecordingPushTransport()

    monkeypatch.setattr(
        notification_dispatcher,
        "send_web_push",
        transport,
    )

    assert (
        trigger_alert(
            database_session,
            fixture,
            price=Decimal("90000.00"),
            settings=notification_settings(),
        )
        == 1
    )

    assert transport.sent == []

    push_delivery = delivery_for(
        database_session,
        user_id=fixture.user.id,
        channel="web_push",
    )

    assert push_delivery is not None
    assert push_delivery.status == "skipped"
    assert "no active push subscription" in push_delivery.failure_reason

    in_app_count = database_session.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == fixture.user.id,
        )
    )

    assert in_app_count == 1


def test_expired_subscription_is_deactivated(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 410 Gone endpoint is retired so later jobs skip it."""

    fixture = create_consumer_alert_fixture(
        database_session,
        price_alert_email=False,
    )

    transport = RecordingPushTransport(
        error=WebPushDeliveryError(
            "Endpoint gone",
            is_permanent=True,
            status_code=410,
        ),
    )

    monkeypatch.setattr(
        notification_dispatcher,
        "send_web_push",
        transport,
    )

    trigger_alert(
        database_session,
        fixture,
        price=Decimal("90000.00"),
        settings=notification_settings(),
    )

    subscriptions = list(
        database_session.scalars(
            select(PushSubscription).where(
                PushSubscription.user_id == fixture.user.id,
            )
        ).all()
    )

    assert len(subscriptions) == 1
    assert subscriptions[0].is_active is False
    assert subscriptions[0].deactivated_at is not None

    push_delivery = delivery_for(
        database_session,
        user_id=fixture.user.id,
        channel="web_push",
    )

    assert push_delivery is not None
    assert push_delivery.status == "skipped"
    assert "expired" in push_delivery.failure_reason


def test_temporary_push_error_keeps_subscription(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 503 does not destroy a still-valid subscription."""

    fixture = create_consumer_alert_fixture(
        database_session,
        price_alert_email=False,
    )

    transport = RecordingPushTransport(
        error=WebPushDeliveryError(
            "Service unavailable",
            is_permanent=False,
            status_code=503,
        ),
    )

    monkeypatch.setattr(
        notification_dispatcher,
        "send_web_push",
        transport,
    )

    trigger_alert(
        database_session,
        fixture,
        price=Decimal("90000.00"),
        settings=notification_settings(),
    )

    subscriptions = list(
        database_session.scalars(
            select(PushSubscription).where(
                PushSubscription.user_id == fixture.user.id,
            )
        ).all()
    )

    assert len(subscriptions) == 1
    assert subscriptions[0].is_active is True

    push_delivery = delivery_for(
        database_session,
        user_id=fixture.user.id,
        channel="web_push",
    )

    assert push_delivery is not None
    assert push_delivery.status == "failed"
    assert push_delivery.attempts == 1


def test_one_expired_endpoint_does_not_block_a_valid_one(
    database_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A dead device is retired while a live device still receives push."""

    fixture = create_consumer_alert_fixture(
        database_session,
        price_alert_email=False,
    )

    dead_endpoint = f"https://push.example.com/{unique_value('dead')}"

    create_push_subscription(
        database_session,
        user_id=fixture.user.id,
        endpoint=dead_endpoint,
    )

    database_session.commit()

    delivered_endpoints: list[str] = []

    def selective_transport(
        *,
        subscription,
        message,
        settings=None,
    ) -> None:
        if subscription.endpoint == dead_endpoint:
            raise WebPushDeliveryError(
                "Endpoint gone",
                is_permanent=True,
                status_code=404,
            )

        delivered_endpoints.append(subscription.endpoint)

    monkeypatch.setattr(
        notification_dispatcher,
        "send_web_push",
        selective_transport,
    )

    trigger_alert(
        database_session,
        fixture,
        price=Decimal("90000.00"),
        settings=notification_settings(),
    )

    assert len(delivered_endpoints) == 1
    assert dead_endpoint not in delivered_endpoints

    dead_subscription = database_session.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint_hash
            == hash_endpoint(dead_endpoint),
        )
    )

    assert dead_subscription is not None
    assert dead_subscription.is_active is False

    push_delivery = delivery_for(
        database_session,
        user_id=fixture.user.id,
        channel="web_push",
    )

    assert push_delivery is not None
    assert push_delivery.status == "delivered"


def test_subscribe_requires_authentication(
    client: TestClient,
) -> None:
    """Anonymous callers cannot register a push subscription."""

    response = client.post(
        "/api/v1/notifications/push/subscribe",
        json=subscription_payload(),
    )

    assert response.status_code == 401


def test_subscribe_and_resubscribe_is_idempotent(
    client: TestClient,
    database_session: Session,
) -> None:
    """Re-sending the same endpoint updates one row instead of adding."""

    headers = register_and_login(client)

    payload = subscription_payload()

    first_response = client.post(
        "/api/v1/notifications/push/subscribe",
        headers=headers,
        json=payload,
    )

    assert first_response.status_code == 201

    first_id = first_response.json()["id"]

    second_response = client.post(
        "/api/v1/notifications/push/subscribe",
        headers=headers,
        json=payload,
    )

    assert second_response.status_code == 201
    assert second_response.json()["id"] == first_id

    stored_count = database_session.scalar(
        select(func.count(PushSubscription.id)).where(
            PushSubscription.endpoint_hash
            == hash_endpoint(payload["endpoint"]),
        )
    )

    assert stored_count == 1


def test_subscribe_rejects_non_https_endpoint(
    client: TestClient,
) -> None:
    """An arbitrary scheme never reaches the Web Push client."""

    headers = register_and_login(client)

    response = client.post(
        "/api/v1/notifications/push/subscribe",
        headers=headers,
        json={
            "endpoint": "http://attacker.example.com/push",
            "keys": {
                "p256dh": "p256dh-key-material-value",
                "auth": "auth-key-value",
            },
        },
    )

    assert response.status_code == 422


def test_user_cannot_unsubscribe_another_users_subscription(
    client: TestClient,
    database_session: Session,
) -> None:
    """One user's endpoint cannot be disabled by somebody else."""

    owner_headers = register_and_login(client)
    attacker_headers = register_and_login(client)

    payload = subscription_payload()

    create_response = client.post(
        "/api/v1/notifications/push/subscribe",
        headers=owner_headers,
        json=payload,
    )

    assert create_response.status_code == 201

    # httpx needs request() to send a body with DELETE.
    attacker_response = client.request(
        "DELETE",
        "/api/v1/notifications/push/unsubscribe",
        headers=attacker_headers,
        json={
            "endpoint": payload["endpoint"],
        },
    )

    assert attacker_response.status_code == 200
    assert attacker_response.json()["deactivated"] is False

    database_session.expire_all()

    subscription = database_session.scalar(
        select(PushSubscription).where(
            PushSubscription.endpoint_hash
            == hash_endpoint(payload["endpoint"]),
        )
    )

    assert subscription is not None
    assert subscription.is_active is True

    owner_response = client.request(
        "DELETE",
        "/api/v1/notifications/push/unsubscribe",
        headers=owner_headers,
        json={
            "endpoint": payload["endpoint"],
        },
    )

    assert owner_response.status_code == 200
    assert owner_response.json()["deactivated"] is True

    database_session.expire_all()

    database_session.refresh(subscription)

    assert subscription.is_active is False


def _generate_browser_keys() -> tuple[str, str]:
    """Return a real P-256 public key and auth secret, browser style."""

    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    def urlsafe(raw: bytes) -> str:
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    browser_key = ec.generate_private_key(ec.SECP256R1())

    p256dh = urlsafe(
        browser_key.public_key().public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
    )

    return p256dh, urlsafe(b"0123456789abcdef")


def _generate_vapid_private_key() -> str:
    """Return a real VAPID application server private key."""

    import base64

    from cryptography.hazmat.primitives.asymmetric import ec

    vapid_key = ec.generate_private_key(ec.SECP256R1())

    raw = vapid_key.private_numbers().private_value.to_bytes(32, "big")

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def test_real_vapid_encryption_accepts_the_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The payload survives real aes128gcm encryption and VAPID signing.

    This exercises ``pywebpush`` and ``http_ece`` for real rather than
    mocking the transport. The encryption layer concatenates raw bytes, so
    a ``str`` payload raises ``TypeError`` here; only the HTTP request
    itself is intercepted.
    """

    import pywebpush

    from app.services.web_push_service import (
        WebPushMessage,
        WebPushSubscriptionInfo,
        send_web_push,
    )

    p256dh, auth = _generate_browser_keys()

    settings = notification_settings(
        vapid_private_key=_generate_vapid_private_key(),
        vapid_subject="mailto:alerts@vextro.test",
    )

    captured: dict[str, object] = {}

    def intercept(
        self,
        data=None,
        headers=None,
        ttl=0,
        gcm_key=None,
        reg_id=None,
        content_encoding="aes128gcm",
        curl=False,
        timeout=None,
    ):
        # Encrypt for real, then stop before any network call.
        captured["body"] = self.encode(
            data,
            content_encoding=content_encoding,
        )["body"]
        captured["authorization"] = (headers or {}).get(
            "Authorization",
            "",
        )

        class Accepted:
            status_code = 201
            text = ""

        return Accepted()

    monkeypatch.setattr(
        pywebpush.WebPusher,
        "send",
        intercept,
    )

    message = WebPushMessage(
        title="Price target reached",
        body="Samsung Galaxy A55 is now PKR 97,500.00.",
        action_path="/products/42",
        tag="price_alert:7:trigger:0",
    )

    assert isinstance(message.as_payload(), bytes)

    send_web_push(
        subscription=WebPushSubscriptionInfo(
            endpoint="https://fcm.googleapis.com/fcm/send/regression",
            p256dh_key=p256dh,
            auth_key=auth,
        ),
        message=message,
        settings=settings,
    )

    assert len(captured["body"]) > 50

    authorization = str(captured["authorization"])

    assert authorization.lower().startswith("vapid")
    assert "t=" in authorization
    assert "k=" in authorization


def test_web_push_requires_vapid_configuration() -> None:
    """Delivery refuses before any network call without VAPID keys."""

    from app.services.web_push_service import (
        WebPushMessage,
        WebPushNotConfiguredError,
        WebPushSubscriptionInfo,
        send_web_push,
    )

    with pytest.raises(WebPushNotConfiguredError):
        send_web_push(
            subscription=WebPushSubscriptionInfo(
                endpoint="https://push.example.com/endpoint",
                p256dh_key="p256dh-key-material",
                auth_key="auth-key",
            ),
            message=WebPushMessage(
                title="Test",
                body="Test",
            ),
            settings=notification_settings(
                vapid_private_key=None,
            ),
        )


@pytest.mark.parametrize(
    ("status_code", "is_permanent"),
    [
        (404, True),
        (410, True),
        (429, False),
        (503, False),
    ],
)
def test_push_failure_classification(
    status_code: int,
    is_permanent: bool,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only a gone endpoint counts as permanently dead."""

    import pywebpush
    from pywebpush import WebPushException

    from app.services.web_push_service import (
        WebPushMessage,
        WebPushSubscriptionInfo,
        send_web_push,
    )

    class Rejection:
        text = "rejected"

    Rejection.status_code = status_code

    def reject(*_args, **_kwargs):
        raise WebPushException(
            "rejected",
            response=Rejection(),
        )

    monkeypatch.setattr(
        pywebpush.WebPusher,
        "send",
        reject,
    )

    # Real browser keys, so the failure comes from the transport rather
    # than from subscription validation.
    p256dh, auth = _generate_browser_keys()

    with pytest.raises(WebPushDeliveryError) as error_info:
        send_web_push(
            subscription=WebPushSubscriptionInfo(
                endpoint="https://push.example.com/classify",
                p256dh_key=p256dh,
                auth_key=auth,
            ),
            message=WebPushMessage(
                title="Test",
                body="Test",
            ),
            settings=notification_settings(
                vapid_private_key=_generate_vapid_private_key(),
            ),
        )

    assert error_info.value.status_code == status_code
    assert error_info.value.is_permanent is is_permanent
