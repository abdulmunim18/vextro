from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User


TEST_PASSWORD = "StrongPassword123!"


def unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}@example.com"


def authorization_header(
    access_token: str,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
    }


def register_consumer(
    client: TestClient,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Dashboard Consumer",
            "email": unique_email("consumer"),
            "password": TEST_PASSWORD,
            "account_type": "consumer",
        },
    )

    assert response.status_code == 201

    return response.json()


def create_admin_user(
    database_session: Session,
) -> User:
    admin_role = database_session.scalar(
        select(Role).where(
            Role.name == "admin",
        )
    )

    assert admin_role is not None

    admin_user = User(
        full_name="Dashboard Administrator",
        email=unique_email("admin"),
        password_hash=hash_password(
            TEST_PASSWORD,
        ),
        is_active=True,
        is_verified=True,
    )

    admin_user.roles.append(admin_role)

    database_session.add(admin_user)
    database_session.commit()
    database_session.refresh(admin_user)

    return admin_user


def login(
    client: TestClient,
    *,
    email: str,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200

    return response.json()


def test_admin_dashboard_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/admin/dashboard",
    )

    assert response.status_code == 401


def test_consumer_cannot_access_admin_dashboard(
    client: TestClient,
) -> None:
    consumer = register_consumer(client)

    tokens = login(
        client,
        email=str(consumer["email"]),
    )

    response = client.get(
        "/api/v1/admin/dashboard",
        headers=authorization_header(
            str(tokens["access_token"]),
        ),
    )

    assert response.status_code == 403


def test_admin_can_read_dashboard_statistics(
    client: TestClient,
    database_session: Session,
) -> None:
    admin_user = create_admin_user(
        database_session,
    )

    tokens = login(
        client,
        email=admin_user.email,
    )

    response = client.get(
        "/api/v1/admin/dashboard",
        headers=authorization_header(
            str(tokens["access_token"]),
        ),
    )

    assert response.status_code == 200

    response_data = response.json()

    expected_fields = {
        "total_users",
        "active_users",
        "consumer_users",
        "sme_users",
        "admin_users",
        "canonical_products",
        "active_products",
        "marketplace_listings",
        "available_listings",
        "total_price_alerts",
        "active_price_alerts",
        "triggered_price_alerts",
    }

    assert set(response_data) == expected_fields

    for field_name in expected_fields:
        assert response_data[field_name] >= 0

    assert response_data["total_users"] >= 1
    assert response_data["admin_users"] >= 1