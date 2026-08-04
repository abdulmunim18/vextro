from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User


TEST_PASSWORD = "StrongPassword123!"


def unique_email(prefix: str) -> str:
    return (
        f"{prefix}-{uuid4().hex}@example.com"
    )


def authorization_header(
    access_token: str,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
    }


def register_user(
    client: TestClient,
    *,
    full_name: str,
    account_type: str,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": full_name,
            "email": unique_email(
                account_type
            ),
            "password": TEST_PASSWORD,
            "account_type": account_type,
        },
    )

    assert response.status_code == 201

    return response.json()


def create_admin_user(
    database_session: Session,
    *,
    full_name: str = "Users Administrator",
) -> User:
    admin_role = database_session.scalar(
        select(Role).where(
            Role.name == "admin"
        )
    )

    assert admin_role is not None

    admin_user = User(
        full_name=full_name,
        email=unique_email("admin"),
        password_hash=hash_password(
            TEST_PASSWORD
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


def admin_headers(
    client: TestClient,
    database_session: Session,
) -> tuple[User, dict[str, str]]:
    admin_user = create_admin_user(
        database_session
    )

    tokens = login(
        client,
        email=admin_user.email,
    )

    return (
        admin_user,
        authorization_header(
            str(tokens["access_token"])
        ),
    )


def test_admin_users_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/admin/users"
    )

    assert response.status_code == 401


def test_consumer_cannot_list_admin_users(
    client: TestClient,
) -> None:
    consumer = register_user(
        client,
        full_name="Restricted Consumer",
        account_type="consumer",
    )

    tokens = login(
        client,
        email=str(consumer["email"]),
    )

    response = client.get(
        "/api/v1/admin/users",
        headers=authorization_header(
            str(tokens["access_token"])
        ),
    )

    assert response.status_code == 403


def test_admin_can_list_paginated_users(
    client: TestClient,
    database_session: Session,
) -> None:
    _, headers = admin_headers(
        client,
        database_session,
    )

    register_user(
        client,
        full_name="Pagination Consumer",
        account_type="consumer",
    )

    register_user(
        client,
        full_name="Pagination SME",
        account_type="sme",
    )

    response = client.get(
        "/api/v1/admin/users",
        params={
            "page": 1,
            "page_size": 2,
        },
        headers=headers,
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["page"] == 1
    assert response_data["page_size"] == 2
    assert response_data["total_items"] >= 3
    assert response_data["total_pages"] >= 2
    assert len(response_data["items"]) <= 2


def test_admin_can_search_and_filter_users(
    client: TestClient,
    database_session: Session,
) -> None:
    _, headers = admin_headers(
        client,
        database_session,
    )

    unique_name = (
        f"Searchable SME {uuid4().hex}"
    )

    sme_user = register_user(
        client,
        full_name=unique_name,
        account_type="sme",
    )

    response = client.get(
        "/api/v1/admin/users",
        params={
            "q": unique_name,
            "role": "sme",
            "is_active": True,
        },
        headers=headers,
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["total_items"] == 1
    assert len(response_data["items"]) == 1

    returned_user = response_data["items"][0]

    assert returned_user["id"] == sme_user["id"]
    assert returned_user["full_name"] == unique_name
    assert returned_user["roles"] == ["sme"]
    assert returned_user["is_active"] is True


def test_admin_can_deactivate_and_reactivate_user(
    client: TestClient,
    database_session: Session,
) -> None:
    _, headers = admin_headers(
        client,
        database_session,
    )

    consumer = register_user(
        client,
        full_name="Status Consumer",
        account_type="consumer",
    )

    user_id = int(consumer["id"])

    deactivate_response = client.patch(
        (
            f"/api/v1/admin/users/"
            f"{user_id}/status"
        ),
        json={
            "is_active": False,
        },
        headers=headers,
    )

    assert deactivate_response.status_code == 200
    assert (
        deactivate_response.json()["is_active"]
        is False
    )

    database_session.expire_all()

    stored_user = database_session.scalar(
        select(User).where(
            User.id == user_id
        )
    )

    assert stored_user is not None
    assert stored_user.is_active is False

    reactivate_response = client.patch(
        (
            f"/api/v1/admin/users/"
            f"{user_id}/status"
        ),
        json={
            "is_active": True,
        },
        headers=headers,
    )

    assert reactivate_response.status_code == 200
    assert (
        reactivate_response.json()["is_active"]
        is True
    )


def test_admin_cannot_deactivate_self(
    client: TestClient,
    database_session: Session,
) -> None:
    admin_user, headers = admin_headers(
        client,
        database_session,
    )

    response = client.patch(
        (
            f"/api/v1/admin/users/"
            f"{admin_user.id}/status"
        ),
        json={
            "is_active": False,
        },
        headers=headers,
    )

    assert response.status_code == 409

    assert (
        response.json()["detail"]["code"]
        == "CANNOT_DEACTIVATE_SELF"
    )


def test_status_update_rejects_missing_user(
    client: TestClient,
    database_session: Session,
) -> None:
    _, headers = admin_headers(
        client,
        database_session,
    )

    response = client.patch(
        "/api/v1/admin/users/999999999/status",
        json={
            "is_active": False,
        },
        headers=headers,
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]["code"]
        == "USER_NOT_FOUND"
    )


def test_admin_users_rejects_invalid_role(
    client: TestClient,
    database_session: Session,
) -> None:
    _, headers = admin_headers(
        client,
        database_session,
    )

    response = client.get(
        "/api/v1/admin/users",
        params={
            "role": "super-admin",
        },
        headers=headers,
    )

    assert response.status_code == 422