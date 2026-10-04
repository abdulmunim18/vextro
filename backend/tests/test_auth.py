from uuid import uuid4
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.core.config import settings
from app.models.role import Role
from app.models.user import User
from app.services.oauth_service import OAuthIdentity


TEST_PASSWORD = "StrongPassword123!"


def unique_email(prefix: str) -> str:
    """Generate a unique email for each test."""

    return f"{prefix}-{uuid4().hex}@example.com"


def register_user(
    client: TestClient,
    *,
    email: str,
    account_type: str = "consumer",
) -> dict[str, object]:
    """Register a test user."""

    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Automated Test User",
            "email": email,
            "password": TEST_PASSWORD,
            "account_type": account_type,
        },
    )

    assert response.status_code == 202

    verification_response = client.post(
        "/api/v1/auth/verify-email",
        json={"email": email, "otp": "123456"},
    )
    assert verification_response.status_code == 201
    return verification_response.json()


def login_user(
    client: TestClient,
    *,
    email: str,
    password: str = TEST_PASSWORD,
) -> dict[str, object]:
    """Log in a test user."""

    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    return response.json()


def authorization_header(
    access_token: str,
) -> dict[str, str]:
    """Create a Bearer authorization header."""

    return {
        "Authorization": f"Bearer {access_token}",
    }


def test_register_consumer_and_hash_password(
    client: TestClient,
    database_session: Session,
) -> None:
    email = unique_email("consumer")

    response_data = register_user(
        client,
        email=email,
    )

    assert response_data["email"] == email
    assert response_data["roles"] == ["consumer"]
    assert response_data["is_active"] is True
    assert response_data["is_verified"] is True

    user = database_session.scalar(
        select(User).where(User.email == email)
    )

    assert user is not None
    assert user.password_hash != TEST_PASSWORD
    assert user.password_hash.startswith("$argon2")


def test_duplicate_email_is_blocked(
    client: TestClient,
) -> None:
    email = unique_email("duplicate")

    register_user(
        client,
        email=email,
    )

    duplicate_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Duplicate User",
            "email": email,
            "password": TEST_PASSWORD,
            "account_type": "consumer",
        },
    )

    assert duplicate_response.status_code == 409

    assert (
        duplicate_response.json()["detail"]["code"]
        == "EMAIL_ALREADY_REGISTERED"
    )


def test_public_admin_registration_is_blocked(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Public Admin",
            "email": unique_email("public-admin"),
            "password": TEST_PASSWORD,
            "account_type": "admin",
        },
    )

    assert response.status_code == 422


def test_login_and_current_user(
    client: TestClient,
) -> None:
    email = unique_email("login")

    register_user(
        client,
        email=email,
    )

    wrong_password_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": "WrongPassword123!",
        },
    )

    assert wrong_password_response.status_code == 401

    login_data = login_user(
        client,
        email=email,
    )

    no_token_response = client.get(
        "/api/v1/auth/me"
    )

    assert no_token_response.status_code == 401

    me_response = client.get(
        "/api/v1/auth/me",
        headers=authorization_header(
            str(login_data["access_token"])
        ),
    )

    assert me_response.status_code == 200
    assert me_response.json()["email"] == email
    assert me_response.json()["roles"] == ["consumer"]


def test_consumer_role_access(
    client: TestClient,
) -> None:
    email = unique_email("consumer-access")

    register_user(
        client,
        email=email,
        account_type="consumer",
    )

    login_data = login_user(
        client,
        email=email,
    )

    headers = authorization_header(
        str(login_data["access_token"])
    )

    assert client.get(
        "/api/v1/access/consumer",
        headers=headers,
    ).status_code == 200

    assert client.get(
        "/api/v1/access/sme",
        headers=headers,
    ).status_code == 403

    assert client.get(
        "/api/v1/access/admin",
        headers=headers,
    ).status_code == 403


def test_sme_role_access(
    client: TestClient,
) -> None:
    email = unique_email("sme-access")

    register_user(
        client,
        email=email,
        account_type="sme",
    )

    login_data = login_user(
        client,
        email=email,
    )

    headers = authorization_header(
        str(login_data["access_token"])
    )

    assert client.get(
        "/api/v1/access/consumer",
        headers=headers,
    ).status_code == 403

    assert client.get(
        "/api/v1/access/sme",
        headers=headers,
    ).status_code == 200

    assert client.get(
        "/api/v1/access/admin",
        headers=headers,
    ).status_code == 403


def test_admin_role_access(
    client: TestClient,
    database_session: Session,
) -> None:
    email = unique_email("admin-access")

    admin_role = database_session.scalar(
        select(Role).where(Role.name == "admin")
    )

    assert admin_role is not None

    admin_user = User(
        full_name="Automated Admin",
        email=email,
        password_hash=hash_password(TEST_PASSWORD),
        is_verified=True,
    )

    admin_user.roles.append(admin_role)

    database_session.add(admin_user)
    database_session.commit()

    login_data = login_user(
        client,
        email=email,
    )

    headers = authorization_header(
        str(login_data["access_token"])
    )

    assert client.get(
        "/api/v1/access/consumer",
        headers=headers,
    ).status_code == 200

    assert client.get(
        "/api/v1/access/sme",
        headers=headers,
    ).status_code == 200

    assert client.get(
        "/api/v1/access/admin",
        headers=headers,
    ).status_code == 200


def test_refresh_rotation_and_logout(
    client: TestClient,
) -> None:
    email = unique_email("refresh")

    register_user(
        client,
        email=email,
    )

    login_data = login_user(
        client,
        email=email,
    )

    old_refresh_token = str(
        login_data["refresh_token"]
    )

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": old_refresh_token,
        },
    )

    assert refresh_response.status_code == 200

    refreshed_data = refresh_response.json()

    new_refresh_token = str(
        refreshed_data["refresh_token"]
    )

    assert new_refresh_token != old_refresh_token

    old_token_response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": old_refresh_token,
        },
    )

    assert old_token_response.status_code == 401

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={
            "refresh_token": new_refresh_token,
        },
    )

    assert logout_response.status_code == 204

    logged_out_token_response = client.post(
        "/api/v1/auth/refresh",
        json={
            "refresh_token": new_refresh_token,
        },
    )

    assert logged_out_token_response.status_code == 401


def test_signup_is_pending_until_correct_otp(
    client: TestClient,
    database_session: Session,
) -> None:
    email = unique_email("pending")
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Pending User",
            "email": email,
            "password": TEST_PASSWORD,
            "account_type": "consumer",
        },
    )
    assert response.status_code == 202
    assert database_session.scalar(
        select(User).where(User.email == email)
    ) is None

    wrong = client.post(
        "/api/v1/auth/verify-email",
        json={"email": email, "otp": "000000"},
    )
    assert wrong.status_code == 400

    verified = client.post(
        "/api/v1/auth/verify-email",
        json={"email": email, "otp": "123456"},
    )
    assert verified.status_code == 201
    assert verified.json()["is_verified"] is True


def test_password_reset_link_is_single_use(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email = unique_email("password-reset")
    register_user(client, email=email)
    delivered: dict[str, str] = {}

    def capture_reset_email(**kwargs: str) -> None:
        delivered.update(kwargs)

    monkeypatch.setattr(
        "app.services.auth_service.send_password_reset_email",
        capture_reset_email,
    )
    request = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": email},
    )
    assert request.status_code == 202
    token = parse_qs(
        urlparse(delivered["reset_url"]).query
    )["token"][0]
    new_password = "NewStrongPassword456!"

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": new_password},
    )
    assert reset.status_code == 200
    assert client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": new_password},
    ).status_code == 200
    assert client.post(
        "/api/v1/auth/reset-password",
        json={"token": token, "new_password": TEST_PASSWORD},
    ).status_code == 400


@pytest.mark.parametrize("provider", ["google", "facebook"])
def test_social_login_creates_verified_user_and_code_is_single_use(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    monkeypatch.setattr(settings, f"{provider}_oauth_client_id", "test-client")
    monkeypatch.setattr(settings, f"{provider}_oauth_client_secret", "test-secret")
    email = unique_email(provider)
    identity = OAuthIdentity(
        provider=provider,
        subject=f"{provider}-subject-{uuid4().hex}",
        email=email,
        full_name=f"{provider.title()} User",
    )
    monkeypatch.setattr(
        f"app.services.oauth_service._fetch_{provider}_identity",
        lambda _code: identity,
    )

    authorization = client.get(
        f"/api/v1/auth/oauth/{provider}/authorize",
        follow_redirects=False,
    )
    assert authorization.status_code == 307
    state = parse_qs(
        urlparse(authorization.headers["location"]).query
    )["state"][0]

    callback = client.get(
        f"/api/v1/auth/oauth/{provider}/callback",
        params={"state": state, "code": "provider-code"},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    login_code = parse_qs(
        urlparse(callback.headers["location"]).query
    )["code"][0]
    exchange = client.post(
        "/api/v1/auth/oauth/exchange",
        json={"code": login_code},
    )
    assert exchange.status_code == 200
    assert exchange.json()["user"]["email"] == email
    assert exchange.json()["user"]["is_verified"] is True
    assert client.post(
        "/api/v1/auth/oauth/exchange",
        json={"code": login_code},
    ).status_code == 401
