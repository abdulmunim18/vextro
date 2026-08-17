from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.notification_repository import create_notification


TEST_PASSWORD = "StrongPassword123!"


def unique_value(prefix: str) -> str:
    """Generate a unique value for test records."""

    return f"{prefix}-{uuid4().hex[:12]}"


def register_and_login(
    client: TestClient,
    *,
    account_type: str = "consumer",
) -> tuple[dict[str, str], str]:
    """Register a test user and return authorization headers plus email."""

    email = f"{unique_value(account_type)}@example.com"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": f"Notification {account_type.title()}",
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

    access_token = login_response.json()["access_token"]

    return (
        {
            "Authorization": f"Bearer {access_token}",
        },
        email,
    )


def get_user_by_email(
    database_session: Session,
    email: str,
) -> User:
    """Return a registered test user."""

    user = database_session.scalar(
        select(User).where(
            User.email == email,
        )
    )

    assert user is not None

    return user


def create_test_notification(
    database_session: Session,
    *,
    user_id: int,
    title: str,
):
    """Create and commit one notification for a test user."""

    notification = create_notification(
        database_session,
        user_id=user_id,
        notification_type="price_drop",
        title=title,
        message=f"{title} message",
        action_path="/alerts",
    )

    database_session.commit()
    database_session.refresh(notification)

    return notification


def test_notification_routes_require_allowed_role(
    client: TestClient,
) -> None:
    """Unauthenticated and SME users cannot access consumer notifications."""

    unauthenticated_response = client.get(
        "/api/v1/notifications"
    )

    assert unauthenticated_response.status_code == 401

    sme_headers, _email = register_and_login(
        client,
        account_type="sme",
    )

    sme_response = client.get(
        "/api/v1/notifications",
        headers=sme_headers,
    )

    assert sme_response.status_code == 403


def test_consumer_starts_with_empty_notifications(
    client: TestClient,
) -> None:
    """A new consumer has an empty notification inbox."""

    headers, _email = register_and_login(client)

    list_response = client.get(
        "/api/v1/notifications",
        headers=headers,
    )

    assert list_response.status_code == 200

    body = list_response.json()

    assert body["total"] == 0
    assert body["unread_count"] == 0
    assert body["limit"] == 50
    assert body["offset"] == 0
    assert body["items"] == []

    count_response = client.get(
        "/api/v1/notifications/unread-count",
        headers=headers,
    )

    assert count_response.status_code == 200
    assert count_response.json()["unread_count"] == 0


def test_consumer_can_list_filter_and_paginate_notifications(
    client: TestClient,
    database_session: Session,
) -> None:
    """Consumers can list only their own notifications with filters."""

    headers, email = register_and_login(client)

    user = get_user_by_email(
        database_session,
        email,
    )

    first = create_test_notification(
        database_session,
        user_id=user.id,
        title="First notification",
    )

    second = create_test_notification(
        database_session,
        user_id=user.id,
        title="Second notification",
    )

    third = create_test_notification(
        database_session,
        user_id=user.id,
        title="Third notification",
    )

    first.is_read = True
    database_session.commit()

    list_response = client.get(
        "/api/v1/notifications?limit=2&offset=0",
        headers=headers,
    )

    assert list_response.status_code == 200

    body = list_response.json()

    assert body["total"] == 3
    assert body["unread_count"] == 2
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["items"]) == 2

    returned_ids = {
        item["id"]
        for item in body["items"]
    }

    assert third.id in returned_ids
    assert second.id in returned_ids

    unread_response = client.get(
        "/api/v1/notifications?unread_only=true",
        headers=headers,
    )

    assert unread_response.status_code == 200

    unread_body = unread_response.json()

    assert unread_body["total"] == 2
    assert unread_body["unread_count"] == 2

    assert {
        item["id"]
        for item in unread_body["items"]
    } == {
        second.id,
        third.id,
    }


def test_consumer_can_mark_one_notification_read_with_ownership_protection(
    client: TestClient,
    database_session: Session,
) -> None:
    """A user can read their notification but not another user's."""

    owner_headers, owner_email = register_and_login(client)
    other_headers, _other_email = register_and_login(client)

    owner = get_user_by_email(
        database_session,
        owner_email,
    )

    notification = create_test_notification(
        database_session,
        user_id=owner.id,
        title="Price dropped",
    )

    forbidden_response = client.patch(
        f"/api/v1/notifications/{notification.id}/read",
        headers=other_headers,
    )

    assert forbidden_response.status_code == 404

    assert (
        forbidden_response.json()["detail"]["code"]
        == "NOTIFICATION_NOT_FOUND"
    )

    read_response = client.patch(
        f"/api/v1/notifications/{notification.id}/read",
        headers=owner_headers,
    )

    assert read_response.status_code == 200

    body = read_response.json()

    assert body["id"] == notification.id
    assert body["is_read"] is True
    assert body["read_at"] is not None

    count_response = client.get(
        "/api/v1/notifications/unread-count",
        headers=owner_headers,
    )

    assert count_response.status_code == 200
    assert count_response.json()["unread_count"] == 0


def test_consumer_can_mark_all_notifications_read(
    client: TestClient,
    database_session: Session,
) -> None:
    """A consumer can clear all unread notifications at once."""

    headers, email = register_and_login(client)

    user = get_user_by_email(
        database_session,
        email,
    )

    create_test_notification(
        database_session,
        user_id=user.id,
        title="Notification one",
    )

    create_test_notification(
        database_session,
        user_id=user.id,
        title="Notification two",
    )

    before_response = client.get(
        "/api/v1/notifications/unread-count",
        headers=headers,
    )

    assert before_response.status_code == 200
    assert before_response.json()["unread_count"] == 2

    read_all_response = client.patch(
        "/api/v1/notifications/read-all",
        headers=headers,
    )

    assert read_all_response.status_code == 200

    body = read_all_response.json()

    assert body["updated_count"] == 2
    assert body["unread_count"] == 0

    unread_response = client.get(
        "/api/v1/notifications?unread_only=true",
        headers=headers,
    )

    assert unread_response.status_code == 200
    assert unread_response.json()["total"] == 0
    assert unread_response.json()["items"] == []