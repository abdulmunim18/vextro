"""Integration tests for grounded assistant conversations."""

from uuid import uuid4

from fastapi.testclient import TestClient


TEST_PASSWORD = "StrongPassword123!"


def _consumer_headers(client: TestClient) -> dict[str, str]:
    email = f"assistant-{uuid4().hex}@example.com"
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Assistant Test Consumer",
            "email": email,
            "password": TEST_PASSWORD,
            "account_type": "consumer",
        },
    )
    assert register_response.status_code == 201
    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
    )
    assert login_response.status_code == 200
    return {
        "Authorization": (
            f"Bearer {login_response.json()['access_token']}"
        ),
    }


def test_assistant_conversation_is_private_and_grounded(
    client: TestClient,
) -> None:
    headers = _consumer_headers(client)
    create_response = client.post(
        "/api/v1/assistant/conversations",
        headers=headers,
        json={},
    )
    assert create_response.status_code == 201
    conversation_id = create_response.json()["id"]

    turn_response = client.post(
        (
            f"/api/v1/assistant/conversations/"
            f"{conversation_id}/messages"
        ),
        headers=headers,
        json={
            "content": (
                "What is the lowest price for Samsung Galaxy A55?"
            ),
        },
    )
    assert turn_response.status_code == 201
    assistant_message = turn_response.json()["assistant_message"]
    assert assistant_message["intent"] == "lowest_price"
    assert assistant_message["data_timestamp"] is not None
    assert "Samsung Galaxy A55" in assistant_message["content"]

    follow_up_response = client.post(
        f"/api/v1/assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "is ki RAM aur storage kitni hai?"},
    )
    assert follow_up_response.status_code == 201
    follow_up = follow_up_response.json()["assistant_message"]
    assert follow_up["intent"] == "product_details"
    assert "Samsung Galaxy A55" in follow_up["content"]

    recommendation_response = client.post(
        f"/api/v1/assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "150k ke andar phone recommend karo"},
    )
    assert recommendation_response.status_code == 201
    recommendation = recommendation_response.json()["assistant_message"]
    assert recommendation["intent"] == "recommendation"
    assert recommendation["entities"]["budget_max"] == "150000"
    assert recommendation["entities"]["category"] == "Mobile Phones"

    contextual_response = client.post(
        f"/api/v1/assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "pehle wale ki RAM aur storage kitni hai?"},
    )
    assert contextual_response.status_code == 201
    contextual_answer = contextual_response.json()["assistant_message"]
    assert contextual_answer["intent"] == "product_details"
    assert "Samsung Galaxy A55" in contextual_answer["content"]

    read_response = client.get(
        f"/api/v1/assistant/conversations/{conversation_id}",
        headers=headers,
    )
    assert read_response.status_code == 200
    assert len(read_response.json()["messages"]) == 8

    other_headers = _consumer_headers(client)
    forbidden_read = client.get(
        f"/api/v1/assistant/conversations/{conversation_id}",
        headers=other_headers,
    )
    assert forbidden_read.status_code == 404
