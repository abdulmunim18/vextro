"""Module 6.14 notification preference API tests."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.notification_preference import NotificationPreference
from app.models.user import User


TEST_PASSWORD = "StrongPassword123!"

PREFERENCES_ENDPOINT = "/api/v1/notifications/preferences"


def register_and_login(
    client: TestClient,
    *,
    account_type: str = "consumer",
) -> tuple[dict[str, str], str]:
    """Register a user and return headers plus their email."""

    email = f"prefs-{account_type}-{uuid4().hex[:10]}@example.com"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": f"Prefs {account_type.title()}",
            "email": email,
            "password": TEST_PASSWORD,
            "account_type": account_type,
        },
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    return (
        {
            "Authorization": (
                f"Bearer {login_response.json()['access_token']}"
            ),
        },
        email,
    )


def test_preferences_require_authentication(
    client: TestClient,
) -> None:
    """Anonymous callers cannot read or change preferences."""

    assert client.get(PREFERENCES_ENDPOINT).status_code == 401

    assert (
        client.patch(
            PREFERENCES_ENDPOINT,
            json={"price_alert_email": False},
        ).status_code
        == 401
    )


def test_defaults_are_created_on_first_read(
    client: TestClient,
    database_session: Session,
) -> None:
    """A new user gets sensible defaults, with digests off."""

    headers, email = register_and_login(client)

    response = client.get(
        PREFERENCES_ENDPOINT,
        headers=headers,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["price_alert_in_app"] is True
    assert body["competitor_alert_in_app"] is True
    assert body["price_alert_email"] is True
    assert body["price_alert_push"] is True
    assert body["competitor_alert_email"] is True
    assert body["competitor_alert_push"] is True
    assert body["digest_frequency"] == "off"
    assert body["active_push_subscription_count"] == 0
    assert body["digest_timezone"]

    # The response advertises capability, never a secret.
    assert "vapid_private_key" not in body
    assert "smtp_password" not in body

    user = database_session.scalar(
        select(User).where(User.email == email)
    )

    assert user is not None

    stored_preference = database_session.scalar(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user.id,
        )
    )

    assert stored_preference is not None
    assert stored_preference.digest_frequency == "off"


def test_user_can_update_their_own_preferences(
    client: TestClient,
    database_session: Session,
) -> None:
    """Supplied fields change and omitted fields stay untouched."""

    headers, email = register_and_login(client)

    response = client.patch(
        PREFERENCES_ENDPOINT,
        headers=headers,
        json={
            "price_alert_email": False,
            "digest_frequency": "weekly",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["price_alert_email"] is False
    assert body["price_alert_push"] is True
    assert body["digest_frequency"] == "weekly"

    user = database_session.scalar(
        select(User).where(User.email == email)
    )

    assert user is not None

    database_session.expire_all()

    stored_preference = database_session.scalar(
        select(NotificationPreference).where(
            NotificationPreference.user_id == user.id,
        )
    )

    assert stored_preference is not None
    assert stored_preference.price_alert_email is False
    assert stored_preference.digest_frequency == "weekly"


def test_invalid_digest_frequency_is_rejected(
    client: TestClient,
) -> None:
    """Only off, daily and weekly are accepted."""

    headers, _email = register_and_login(client)

    response = client.patch(
        PREFERENCES_ENDPOINT,
        headers=headers,
        json={"digest_frequency": "hourly"},
    )

    assert response.status_code == 422


def test_unknown_preference_field_is_rejected(
    client: TestClient,
) -> None:
    """An unexpected field cannot smuggle in a change."""

    headers, _email = register_and_login(client)

    response = client.patch(
        PREFERENCES_ENDPOINT,
        headers=headers,
        json={"user_id": 1},
    )

    assert response.status_code == 422


def test_one_user_cannot_change_another_users_preferences(
    client: TestClient,
    database_session: Session,
) -> None:
    """Preferences are keyed off the token, never off request data."""

    first_headers, first_email = register_and_login(client)
    second_headers, second_email = register_and_login(client)

    first_user = database_session.scalar(
        select(User).where(User.email == first_email)
    )
    second_user = database_session.scalar(
        select(User).where(User.email == second_email)
    )

    assert first_user is not None
    assert second_user is not None

    assert (
        client.patch(
            PREFERENCES_ENDPOINT,
            headers=first_headers,
            json={"price_alert_email": False},
        ).status_code
        == 200
    )

    second_response = client.get(
        PREFERENCES_ENDPOINT,
        headers=second_headers,
    )

    assert second_response.status_code == 200
    assert second_response.json()["price_alert_email"] is True

    database_session.expire_all()

    second_preference = database_session.scalar(
        select(NotificationPreference).where(
            NotificationPreference.user_id == second_user.id,
        )
    )

    assert second_preference is not None
    assert second_preference.price_alert_email is True


def test_sme_user_can_manage_their_own_preferences(
    client: TestClient,
) -> None:
    """SME owners receive competitor alerts, so they own preferences too."""

    headers, _email = register_and_login(
        client,
        account_type="sme",
    )

    read_response = client.get(
        PREFERENCES_ENDPOINT,
        headers=headers,
    )

    assert read_response.status_code == 200

    update_response = client.patch(
        PREFERENCES_ENDPOINT,
        headers=headers,
        json={
            "competitor_alert_email": False,
            "digest_frequency": "daily",
        },
    )

    assert update_response.status_code == 200

    body = update_response.json()

    assert body["competitor_alert_email"] is False
    assert body["digest_frequency"] == "daily"


def test_push_subscribe_opts_the_user_into_push(
    client: TestClient,
) -> None:
    """Registering a browser flips the push preferences back on."""

    headers, _email = register_and_login(client)

    assert (
        client.patch(
            PREFERENCES_ENDPOINT,
            headers=headers,
            json={
                "price_alert_push": False,
                "competitor_alert_push": False,
            },
        ).status_code
        == 200
    )

    subscribe_response = client.post(
        "/api/v1/notifications/push/subscribe",
        headers=headers,
        json={
            "endpoint": (
                f"https://push.example.com/{uuid4().hex}"
            ),
            "keys": {
                "p256dh": "p256dh-key-material-value",
                "auth": "auth-key-value",
            },
        },
    )

    assert subscribe_response.status_code == 201

    read_response = client.get(
        PREFERENCES_ENDPOINT,
        headers=headers,
    )

    assert read_response.status_code == 200

    body = read_response.json()

    assert body["price_alert_push"] is True
    assert body["competitor_alert_push"] is True
    assert body["active_push_subscription_count"] == 1
