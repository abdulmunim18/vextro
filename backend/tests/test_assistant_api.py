"""Integration tests for grounded assistant conversations."""

from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.platform import Platform
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant


TEST_PASSWORD = "StrongPassword123!"


def _seed_assistant_catalog(database_session: Session) -> str:
    token = uuid4().hex[:8]
    category = database_session.scalar(
        select(Category).where(Category.name == "Mobile Phones")
    )
    brand = database_session.scalar(
        select(Brand).where(Brand.name == "Samsung")
    )
    platform = database_session.scalar(
        select(Platform).where(Platform.code == "daraz")
    )
    assert category is not None
    assert brand is not None
    assert platform is not None

    names_and_prices = (
        (f"Samsung Galaxy A55 Assistant {token}", Decimal("120000")),
        (f"Samsung Galaxy A35 Assistant {token}", Decimal("90000")),
    )
    for index, (name, price) in enumerate(names_and_prices):
        product = CanonicalProduct(
            category_id=category.id,
            brand_id=brand.id,
            name=name,
            slug=f"assistant-{token}-{index}",
            model=f"ASSISTANT-{token}-{index}",
            specifications={"ram": "8GB", "storage": "256GB"},
            is_active=True,
        )
        database_session.add(product)
        database_session.flush()
        variant = ProductVariant(
            canonical_product_id=product.id,
            sku=f"ASSISTANT-{token}-{index}",
            ram_gb=8,
            storage_gb=256,
            is_active=True,
        )
        database_session.add(variant)
        database_session.flush()
        database_session.add(
            ProductListing(
                platform_id=platform.id,
                product_variant_id=variant.id,
                external_id=f"assistant-{token}-{index}",
                title=name,
                product_url=f"https://example.com/{token}/{index}",
                current_price=price,
                currency="PKR",
                is_available=True,
            )
        )
    database_session.commit()
    return names_and_prices[0][0]


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
    assert register_response.status_code == 202
    verify_response = client.post(
        "/api/v1/auth/verify-email",
        json={"email": email, "otp": "123456"},
    )
    assert verify_response.status_code == 201
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
    database_session: Session,
) -> None:
    product_name = _seed_assistant_catalog(database_session)
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
                f"What is the lowest price for {product_name}?"
            ),
        },
    )
    assert turn_response.status_code == 201
    assistant_message = turn_response.json()["assistant_message"]
    assert assistant_message["intent"] == "lowest_price"
    assert assistant_message["data_timestamp"] is not None
    assert product_name in assistant_message["content"]

    follow_up_response = client.post(
        f"/api/v1/assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "is ki RAM aur storage kitni hai?"},
    )
    assert follow_up_response.status_code == 201
    follow_up = follow_up_response.json()["assistant_message"]
    assert follow_up["intent"] == "product_details"
    assert product_name in follow_up["content"]

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
    assert product_name in contextual_answer["content"]

    redundant_suffix_response = client.post(
        f"/api/v1/assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "100000 k budget main konsa mobile acha hoga"},
    )
    assert redundant_suffix_response.status_code == 201
    redundant_suffix = redundant_suffix_response.json()["assistant_message"]
    assert redundant_suffix["intent"] == "recommendation"
    assert redundant_suffix["entities"]["budget_max"] == "100000"
    assert all(
        float(item["lowest_price"]) <= 100000
        for item in redundant_suffix["grounded_data"]["recommendations"]
    )

    read_response = client.get(
        f"/api/v1/assistant/conversations/{conversation_id}",
        headers=headers,
    )
    assert read_response.status_code == 200
    stored_messages = read_response.json()["messages"]
    assert len(stored_messages) == 10
    assert [message["role"] for message in stored_messages] == [
        "user",
        "assistant",
    ] * 5
    assert read_response.json()["message_total"] == 10
    assert read_response.json()["has_more_messages"] is False

    paged_response = client.get(
        f"/api/v1/assistant/conversations/{conversation_id}",
        headers=headers,
        params={"message_limit": 4},
    )
    assert paged_response.status_code == 200
    page = paged_response.json()
    assert len(page["messages"]) == 4
    assert page["message_total"] == 10
    assert page["has_more_messages"] is True
    assert [message["id"] for message in page["messages"]] == sorted(
        message["id"] for message in page["messages"]
    )

    other_headers = _consumer_headers(client)
    forbidden_read = client.get(
        f"/api/v1/assistant/conversations/{conversation_id}",
        headers=other_headers,
    )
    assert forbidden_read.status_code == 404


def test_assistant_refuses_out_of_scope_question_without_database_fallback(
    client: TestClient,
) -> None:
    headers = _consumer_headers(client)
    create_response = client.post(
        "/api/v1/assistant/conversations",
        headers=headers,
        json={},
    )
    conversation_id = create_response.json()["id"]

    turn_response = client.post(
        f"/api/v1/assistant/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "Aaj ka weather kya hai?"},
    )

    assert turn_response.status_code == 201
    assistant_message = turn_response.json()["assistant_message"]
    assert assistant_message["intent"] == "out_of_scope"
    assert "can't help with that request" in assistant_message["content"]
    assert "VEXTRO products" in assistant_message["content"]
    assert assistant_message["grounded_data"]["scope"] == "out_of_scope"
    assert assistant_message["data_timestamp"] is None
    assert "database" not in assistant_message["content"].lower()


def test_assistant_refuses_product_keywords_without_catalog_evidence(
    client: TestClient,
) -> None:
    headers = _consumer_headers(client)
    conversation_id = client.post(
        "/api/v1/assistant/conversations",
        headers=headers,
        json={},
    ).json()["id"]

    for content in (
        "What is the price of Bitcoin?",
        "What is the history of Samsung company?",
    ):
        response = client.post(
            f"/api/v1/assistant/conversations/{conversation_id}/messages",
            headers=headers,
            json={"content": content},
        )
        assert response.status_code == 201
        message = response.json()["assistant_message"]
        assert message["intent"] == "out_of_scope"
        assert message["grounded_data"]["scope"] == "out_of_scope"


def test_assistant_conversation_list_is_paginated(client: TestClient) -> None:
    headers = _consumer_headers(client)
    for index in range(3):
        response = client.post(
            "/api/v1/assistant/conversations",
            headers=headers,
            json={"title": f"Pagination conversation {index}"},
        )
        assert response.status_code == 201

    response = client.get(
        "/api/v1/assistant/conversations",
        headers=headers,
        params={"page": 1, "page_size": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["page"] == 1
    assert body["page_size"] == 2
