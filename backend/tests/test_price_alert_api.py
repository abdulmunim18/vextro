from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.platform import Platform
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.seller import Seller


TEST_PASSWORD = "StrongPassword123!"


def unique_value(prefix: str) -> str:
    """Generate a unique value for test records."""

    return f"{prefix}-{uuid4().hex[:12]}"


def register_and_login(
    client: TestClient,
    *,
    account_type: str = "consumer",
) -> dict[str, str]:
    """Register a user and return its authorization header."""

    email = f"{unique_value(account_type)}@example.com"

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": f"Price Alert {account_type.title()}",
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

    return {
        "Authorization": f"Bearer {access_token}",
    }


def create_price_alert_target(
    database_session: Session,
) -> tuple[CanonicalProduct, ProductListing]:
    """Create one product and one marketplace listing."""

    category = Category(
        name=unique_value("Alert API Category"),
        slug=unique_value("alert-api-category").lower(),
        is_active=True,
    )

    brand = Brand(
        name=unique_value("Alert API Brand"),
        slug=unique_value("alert-api-brand").lower(),
        is_active=True,
    )

    platform_code = unique_value("alert-api-platform").lower()

    platform = Platform(
        name=unique_value("Alert API Platform"),
        code=platform_code,
        base_url=f"https://{platform_code}.example.com",
        is_active=True,
    )

    database_session.add_all(
        [
            category,
            brand,
            platform,
        ]
    )
    database_session.flush()

    product = CanonicalProduct(
        category_id=category.id,
        brand_id=brand.id,
        name=unique_value("Alert API Smartphone"),
        slug=unique_value("alert-api-smartphone").lower(),
        model=unique_value("ALERT-API-MODEL"),
        description="Product used for price alert API tests.",
        specifications={
            "ram": "8 GB",
            "storage": "256 GB",
        },
        is_active=True,
    )

    database_session.add(product)
    database_session.flush()

    variant = ProductVariant(
        canonical_product_id=product.id,
        sku=unique_value("ALERT-API-SKU"),
        ram_gb=8,
        storage_gb=256,
        color="Black",
        condition="new",
        is_active=True,
    )

    seller = Seller(
        platform_id=platform.id,
        external_seller_id=unique_value("alert-api-seller"),
        name=unique_value("Alert API Seller"),
        rating=Decimal("4.70"),
        review_count=200,
        is_verified=True,
        is_active=True,
    )

    database_session.add_all(
        [
            variant,
            seller,
        ]
    )
    database_session.flush()

    listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=variant.id,
        seller_id=seller.id,
        external_id=unique_value("alert-api-listing"),
        title="Alert API Smartphone Listing",
        product_url="https://example.com/products/alert-api-phone",
        current_price=Decimal("120000.00"),
        original_price=Decimal("130000.00"),
        currency="PKR",
        is_available=True,
    )

    database_session.add(listing)
    database_session.commit()

    return product, listing


def test_price_alert_routes_require_an_allowed_role(
    client: TestClient,
) -> None:
    """Unauthenticated and SME users cannot access consumer alerts."""

    unauthenticated_response = client.get(
        "/api/v1/price-alerts"
    )

    assert unauthenticated_response.status_code == 401

    sme_headers = register_and_login(
        client,
        account_type="sme",
    )

    sme_response = client.get(
        "/api/v1/price-alerts",
        headers=sme_headers,
    )

    assert sme_response.status_code == 403


def test_consumer_can_create_list_and_read_own_alerts(
    client: TestClient,
    database_session: Session,
) -> None:
    """A consumer can create product and listing alerts."""

    headers = register_and_login(client)

    product, listing = create_price_alert_target(
        database_session
    )

    product_alert_response = client.post(
        "/api/v1/price-alerts",
        headers=headers,
        json={
            "canonical_product_id": product.id,
            "target_price": "110000.00",
            "currency": "pkr",
        },
    )

    assert product_alert_response.status_code == 201

    product_alert = product_alert_response.json()

    assert product_alert["canonical_product_id"] == product.id
    assert product_alert["listing_id"] is None
    assert product_alert["currency"] == "PKR"
    assert product_alert["is_active"] is True

    listing_alert_response = client.post(
        "/api/v1/price-alerts",
        headers=headers,
        json={
            "listing_id": listing.id,
            "target_price": "105000.00",
            "currency": "PKR",
        },
    )

    assert listing_alert_response.status_code == 201

    listing_alert = listing_alert_response.json()

    assert listing_alert["listing_id"] == listing.id
    assert listing_alert["canonical_product_id"] is None

    list_response = client.get(
        "/api/v1/price-alerts",
        headers=headers,
    )

    assert list_response.status_code == 200

    list_body = list_response.json()

    assert list_body["total"] == 2
    assert {
        item["id"]
        for item in list_body["items"]
    } == {
        product_alert["id"],
        listing_alert["id"],
    }

    detail_response = client.get(
        f"/api/v1/price-alerts/{product_alert['id']}",
        headers=headers,
    )

    assert detail_response.status_code == 200
    assert detail_response.json()["id"] == product_alert["id"]


def test_duplicate_active_alert_returns_conflict(
    client: TestClient,
    database_session: Session,
) -> None:
    """The same user cannot create two active alerts for one target."""

    headers = register_and_login(client)

    product, _listing = create_price_alert_target(
        database_session
    )

    payload = {
        "canonical_product_id": product.id,
        "target_price": "110000.00",
        "currency": "PKR",
    }

    first_response = client.post(
        "/api/v1/price-alerts",
        headers=headers,
        json=payload,
    )

    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/v1/price-alerts",
        headers=headers,
        json={
            **payload,
            "target_price": "100000.00",
        },
    )

    assert duplicate_response.status_code == 409

    assert (
        duplicate_response.json()["detail"]["code"]
        == "PRICE_ALERT_ALREADY_EXISTS"
    )


def test_missing_target_and_invalid_payload_are_rejected(
    client: TestClient,
    database_session: Session,
) -> None:
    """Missing targets return 404 and invalid target selection returns 422."""

    headers = register_and_login(client)

    product, listing = create_price_alert_target(
        database_session
    )

    missing_target_response = client.post(
        "/api/v1/price-alerts",
        headers=headers,
        json={
            "canonical_product_id": 999999999,
            "target_price": "100000.00",
            "currency": "PKR",
        },
    )

    assert missing_target_response.status_code == 404

    assert (
        missing_target_response.json()["detail"]["code"]
        == "PRICE_ALERT_TARGET_NOT_FOUND"
    )

    two_targets_response = client.post(
        "/api/v1/price-alerts",
        headers=headers,
        json={
            "canonical_product_id": product.id,
            "listing_id": listing.id,
            "target_price": "100000.00",
            "currency": "PKR",
        },
    )

    assert two_targets_response.status_code == 422

    no_target_response = client.post(
        "/api/v1/price-alerts",
        headers=headers,
        json={
            "target_price": "100000.00",
            "currency": "PKR",
        },
    )

    assert no_target_response.status_code == 422


def test_user_cannot_access_or_modify_another_users_alert(
    client: TestClient,
    database_session: Session,
) -> None:
    """Alert ownership must be enforced for read, update, and delete."""

    owner_headers = register_and_login(client)
    other_user_headers = register_and_login(client)

    product, _listing = create_price_alert_target(
        database_session
    )

    create_response = client.post(
        "/api/v1/price-alerts",
        headers=owner_headers,
        json={
            "canonical_product_id": product.id,
            "target_price": "100000.00",
            "currency": "PKR",
        },
    )

    assert create_response.status_code == 201

    alert_id = create_response.json()["id"]

    read_response = client.get(
        f"/api/v1/price-alerts/{alert_id}",
        headers=other_user_headers,
    )

    update_response = client.patch(
        f"/api/v1/price-alerts/{alert_id}",
        headers=other_user_headers,
        json={
            "target_price": "90000.00",
        },
    )

    delete_response = client.delete(
        f"/api/v1/price-alerts/{alert_id}",
        headers=other_user_headers,
    )

    assert read_response.status_code == 404
    assert update_response.status_code == 404
    assert delete_response.status_code == 404

    for response in (
        read_response,
        update_response,
        delete_response,
    ):
        assert (
            response.json()["detail"]["code"]
            == "PRICE_ALERT_NOT_FOUND"
        )


def test_consumer_can_update_deactivate_and_reactivate_alert(
    client: TestClient,
    database_session: Session,
) -> None:
    """The owner can update, deactivate, and reactivate an alert."""

    headers = register_and_login(client)

    product, _listing = create_price_alert_target(
        database_session
    )

    create_response = client.post(
        "/api/v1/price-alerts",
        headers=headers,
        json={
            "canonical_product_id": product.id,
            "target_price": "110000.00",
            "currency": "PKR",
        },
    )

    assert create_response.status_code == 201

    alert_id = create_response.json()["id"]

    update_response = client.patch(
        f"/api/v1/price-alerts/{alert_id}",
        headers=headers,
        json={
            "target_price": "95000.00",
            "currency": "usd",
        },
    )

    assert update_response.status_code == 200

    updated_alert = update_response.json()

    assert Decimal(
        str(updated_alert["target_price"])
    ) == Decimal("95000.00")

    assert updated_alert["currency"] == "USD"
    assert updated_alert["is_active"] is True

    deactivate_response = client.delete(
        f"/api/v1/price-alerts/{alert_id}",
        headers=headers,
    )

    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False

    reactivate_response = client.patch(
        f"/api/v1/price-alerts/{alert_id}",
        headers=headers,
        json={
            "is_active": True,
        },
    )

    assert reactivate_response.status_code == 200
    assert reactivate_response.json()["is_active"] is True
    assert reactivate_response.json()["is_triggered"] is False