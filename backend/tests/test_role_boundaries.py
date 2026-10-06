"""Role boundaries between administrator and end-user workspaces."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from tests.test_admin_catalog import admin_headers


def test_admin_cannot_access_consumer_or_sme_features(
    client: TestClient,
    database_session: Session,
) -> None:
    """Admin is operational only, not a Consumer or SME super-role."""

    headers = admin_headers(client, database_session)
    for endpoint in (
        "/api/v1/assistant/conversations",
        "/api/v1/price-alerts",
        "/api/v1/sme/organizations",
    ):
        response = client.get(endpoint, headers=headers)
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "ROLE_NOT_ALLOWED"


def test_access_token_lifetime_is_thirty_minutes() -> None:
    """Keep interactive sessions alive for the requested half hour."""

    _, expires_in = create_access_token(user_id=1, roles=["consumer"])
    assert expires_in == 30 * 60
