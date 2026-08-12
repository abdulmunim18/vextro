"""Integration tests for SME business intelligence APIs."""

from collections.abc import Generator
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.canonical_product import (
    CanonicalProduct,
)
from app.models.category import Category
from app.models.competitor_watchlist import (
    CompetitorWatchlist,
)
from app.models.organization import Organization
from app.models.platform import Platform
from app.models.product_listing import (
    ProductListing,
)
from app.models.product_variant import (
    ProductVariant,
)
from app.models.seller import Seller


TEST_PASSWORD = "StrongPassword123!"

ORGANIZATIONS_ENDPOINT = (
    "/api/v1/sme/organizations"
)


def unique_email(
    prefix: str,
) -> str:
    """Generate a unique email address."""

    return (
        f"{prefix}-{uuid4().hex}@example.com"
    )


def register_and_login(
    client: TestClient,
    *,
    account_type: str,
    prefix: str,
) -> dict[str, str]:
    """Register a user and return authorization headers."""

    email = unique_email(prefix)

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": (
                f"{account_type.title()} Test User"
            ),
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

    access_token = login_response.json()[
        "access_token"
    ]

    return {
        "Authorization": (
            f"Bearer {access_token}"
        ),
    }


@pytest.fixture
def sme_context(
    client: TestClient,
    database_session: Session,
) -> Generator[
    dict[str, object],
    None,
    None,
]:
    """Create an authenticated SME organization."""

    token = uuid4().hex[:10]

    headers = register_and_login(
        client,
        account_type="sme",
        prefix=f"sme-{token}",
    )

    create_response = client.post(
        ORGANIZATIONS_ENDPOINT,
        headers=headers,
        json={
            "name": (
                f"SME Test Organization {token}"
            ),
            "industry": "Mobile Retail",
        },
    )

    assert create_response.status_code == 201

    organization = create_response.json()

    context = {
        "token": token,
        "headers": headers,
        "organization_id": organization["id"],
        "organization": organization,
    }

    yield context

    database_session.rollback()

    database_session.execute(
        delete(Organization).where(
            Organization.id
            == int(
                context["organization_id"],
            ),
        ),
    )

    database_session.commit()


@pytest.fixture
def marketplace_context(
    database_session: Session,
) -> Generator[
    dict[str, object],
    None,
    None,
]:
    """Create a temporary marketplace listing."""

    token = uuid4().hex[:10]

    category_id = database_session.scalar(
        select(Category.id).where(
            Category.slug == "mobile-phones",
        ),
    )

    brand_id = database_session.scalar(
        select(Brand.id).where(
            Brand.slug == "samsung",
        ),
    )

    platform_id = database_session.scalar(
        select(Platform.id).where(
            Platform.code == "daraz",
        ),
    )

    assert category_id is not None
    assert brand_id is not None
    assert platform_id is not None

    canonical_product = CanonicalProduct(
        category_id=category_id,
        brand_id=brand_id,
        name=(
            f"SME Marketplace Phone {token}"
        ),
        slug=(
            f"sme-marketplace-phone-{token}"
        ),
        model=f"SME-{token}",
        description=(
            "Temporary catalog product used "
            "for SME integration tests."
        ),
        specifications={
            "test_record": True,
        },
        is_active=True,
    )

    database_session.add(canonical_product)
    database_session.flush()

    variant = ProductVariant(
        canonical_product_id=(
            canonical_product.id
        ),
        sku=f"SME-VARIANT-{token}",
        ram_gb=8,
        storage_gb=256,
        color="Black",
        condition="new",
        variant_attributes={
            "test_record": True,
        },
        is_active=True,
    )

    database_session.add(variant)
    database_session.flush()

    seller = Seller(
        platform_id=platform_id,
        external_seller_id=(
            f"SME-SELLER-{token}"
        ),
        name=f"SME Test Seller {token}",
        profile_url=(
            "https://www.daraz.pk/shop/"
            f"sme-test-{token}"
        ),
        rating=Decimal("4.70"),
        review_count=500,
        is_verified=True,
        is_active=True,
    )

    database_session.add(seller)
    database_session.flush()

    capture_time = datetime.now(
        timezone.utc,
    )

    listing = ProductListing(
        platform_id=platform_id,
        product_variant_id=variant.id,
        seller_id=seller.id,
        external_id=(
            f"SME-LISTING-{token}"
        ),
        title=(
            f"Samsung SME Test Phone {token}"
        ),
        product_url=(
            "https://www.daraz.pk/products/"
            f"sme-test-{token}"
        ),
        current_price=Decimal("124999.00"),
        original_price=Decimal("129999.00"),
        currency="PKR",
        rating=Decimal("4.60"),
        review_count=200,
        warranty="1 Year Brand Warranty",
        is_available=True,
        raw_payload={
            "test_record": True,
        },
        first_seen_at=capture_time,
        last_seen_at=capture_time,
    )

    database_session.add(listing)
    database_session.commit()

    database_session.refresh(canonical_product)
    database_session.refresh(variant)
    database_session.refresh(seller)
    database_session.refresh(listing)

    context = {
        "canonical_product_id": (
            canonical_product.id
        ),
        "variant_id": variant.id,
        "seller_id": seller.id,
        "listing_id": listing.id,
    }

    yield context

    database_session.rollback()

    database_session.execute(
        delete(CompetitorWatchlist).where(
            CompetitorWatchlist.listing_id
            == listing.id,
        ),
    )

    database_session.execute(
        delete(ProductListing).where(
            ProductListing.id == listing.id,
        ),
    )

    database_session.execute(
        delete(Seller).where(
            Seller.id == seller.id,
        ),
    )

    database_session.execute(
        delete(ProductVariant).where(
            ProductVariant.id == variant.id,
        ),
    )

    database_session.execute(
        delete(CanonicalProduct).where(
            CanonicalProduct.id
            == canonical_product.id,
        ),
    )

    database_session.commit()


def test_sme_routes_require_authentication_and_role(
    client: TestClient,
) -> None:
    """Block unauthenticated and Consumer requests."""

    no_token_response = client.get(
        ORGANIZATIONS_ENDPOINT,
    )

    assert no_token_response.status_code == 401

    consumer_headers = register_and_login(
        client,
        account_type="consumer",
        prefix="sme-consumer-block",
    )

    consumer_response = client.get(
        ORGANIZATIONS_ENDPOINT,
        headers=consumer_headers,
    )

    assert consumer_response.status_code == 403

    assert (
        consumer_response.json()["detail"]["code"]
        == "ROLE_NOT_ALLOWED"
    )


def test_sme_can_manage_organization(
    client: TestClient,
    sme_context: dict[str, object],
) -> None:
    """Create, list, read and update an organization."""

    headers = sme_context["headers"]

    assert isinstance(headers, dict)

    organization_id = int(
        sme_context["organization_id"],
    )

    created_organization = (
        sme_context["organization"]
    )

    assert isinstance(
        created_organization,
        dict,
    )

    assert created_organization["name"].startswith(
        "SME Test Organization",
    )

    assert created_organization[
        "industry"
    ] == "Mobile Retail"

    list_response = client.get(
        ORGANIZATIONS_ENDPOINT,
        headers=headers,
    )

    assert list_response.status_code == 200

    list_data = list_response.json()

    assert list_data["total"] >= 1

    assert organization_id in {
        item["id"]
        for item in list_data["items"]
    }

    read_response = client.get(
        (
            f"{ORGANIZATIONS_ENDPOINT}/"
            f"{organization_id}"
        ),
        headers=headers,
    )

    assert read_response.status_code == 200

    update_response = client.patch(
        (
            f"{ORGANIZATIONS_ENDPOINT}/"
            f"{organization_id}"
        ),
        headers=headers,
        json={
            "name": "Updated SME Mobile Store",
            "industry": None,
        },
    )

    assert update_response.status_code == 200

    updated_data = update_response.json()

    assert updated_data["name"] == (
        "Updated SME Mobile Store"
    )

    assert updated_data["slug"].startswith(
        "updated-sme-mobile-store",
    )

    assert updated_data["industry"] is None


def test_another_sme_cannot_access_organization(
    client: TestClient,
    sme_context: dict[str, object],
) -> None:
    """Hide one SME organization from another SME."""

    other_sme_headers = register_and_login(
        client,
        account_type="sme",
        prefix="other-sme",
    )

    organization_id = int(
        sme_context["organization_id"],
    )

    response = client.get(
        (
            f"{ORGANIZATIONS_ENDPOINT}/"
            f"{organization_id}"
        ),
        headers=other_sme_headers,
    )

    assert response.status_code == 404

    assert response.json()["detail"] == (
        "The requested organization "
        "was not found."
    )


def test_sme_can_manage_business_products(
    client: TestClient,
    sme_context: dict[str, object],
    marketplace_context: dict[str, object],
) -> None:
    """Create, list and update an SME product."""

    headers = sme_context["headers"]

    assert isinstance(headers, dict)

    organization_id = int(
        sme_context["organization_id"],
    )

    products_endpoint = (
        f"{ORGANIZATIONS_ENDPOINT}/"
        f"{organization_id}/products"
    )

    product_payload = {
        "canonical_product_id": int(
            marketplace_context[
                "canonical_product_id"
            ],
        ),
        "name": "Samsung Business Phone",
        "sku": "sme-phone-001",
        "cost_price": 105000,
        "selling_price": 120000,
        "currency": "pkr",
        "stock_level": 25,
        "reorder_level": 5,
    }

    create_response = client.post(
        products_endpoint,
        headers=headers,
        json=product_payload,
    )

    assert create_response.status_code == 201

    created_product = create_response.json()

    assert created_product["sku"] == (
        "SME-PHONE-001"
    )

    assert created_product["currency"] == "PKR"
    assert created_product["stock_level"] == 25

    duplicate_response = client.post(
        products_endpoint,
        headers=headers,
        json={
            **product_payload,
            "name": "Duplicate SKU Phone",
            "sku": "SME-PHONE-001",
        },
    )

    assert duplicate_response.status_code == 409

    assert duplicate_response.json()["detail"] == (
        "This SKU already exists in "
        "the organization."
    )

    list_response = client.get(
        products_endpoint,
        headers=headers,
        params={
            "query": "Samsung",
            "page": 1,
            "page_size": 10,
        },
    )

    assert list_response.status_code == 200

    list_data = list_response.json()

    assert list_data["total"] == 1
    assert list_data["total_pages"] == 1
    assert len(list_data["items"]) == 1

    product_id = created_product["id"]

    update_response = client.patch(
        f"{products_endpoint}/{product_id}",
        headers=headers,
        json={
            "selling_price": 118500,
            "stock_level": 14,
            "reorder_level": 6,
        },
    )

    assert update_response.status_code == 200

    updated_product = update_response.json()

    assert (
        updated_product["selling_price"]
        == "118500.00"
    )

    assert updated_product["stock_level"] == 14
    assert updated_product["reorder_level"] == 6


def test_sme_can_manage_competitor_watchlist(
    client: TestClient,
    sme_context: dict[str, object],
    marketplace_context: dict[str, object],
) -> None:
    """Create, list and deactivate competitor monitoring."""

    headers = sme_context["headers"]

    assert isinstance(headers, dict)

    organization_id = int(
        sme_context["organization_id"],
    )

    products_endpoint = (
        f"{ORGANIZATIONS_ENDPOINT}/"
        f"{organization_id}/products"
    )

    product_response = client.post(
        products_endpoint,
        headers=headers,
        json={
            "name": "Watchlist Test Product",
            "sku": "WATCH-001",
            "cost_price": 100000,
            "selling_price": 122000,
            "currency": "PKR",
            "stock_level": 10,
            "reorder_level": 3,
        },
    )

    assert product_response.status_code == 201

    business_product_id = (
        product_response.json()["id"]
    )

    competitors_endpoint = (
        f"{ORGANIZATIONS_ENDPOINT}/"
        f"{organization_id}/competitors"
    )

    create_response = client.post(
        competitors_endpoint,
        headers=headers,
        json={
            "business_product_id": (
                business_product_id
            ),
            "listing_id": int(
                marketplace_context[
                    "listing_id"
                ],
            ),
        },
    )

    assert create_response.status_code == 201

    watchlist_entry = create_response.json()

    assert watchlist_entry["is_active"] is True

    duplicate_response = client.post(
        competitors_endpoint,
        headers=headers,
        json={
            "business_product_id": (
                business_product_id
            ),
            "listing_id": int(
                marketplace_context[
                    "listing_id"
                ],
            ),
        },
    )

    assert duplicate_response.status_code == 409

    list_response = client.get(
        competitors_endpoint,
        headers=headers,
    )

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 1

    intelligence_response = client.get(
        (
            f"{ORGANIZATIONS_ENDPOINT}/"
            f"{organization_id}/competitor-intelligence"
        ),
        headers=headers,
    )

    assert intelligence_response.status_code == 200
    intelligence = intelligence_response.json()
    assert intelligence["summary"]["tracked_competitors"] == 1
    assert len(intelligence["items"]) == 1
    assert intelligence["items"][0]["price_gap"] == "-2999.00"

    pricing_response = client.post(
        (
            f"{ORGANIZATIONS_ENDPOINT}/"
            f"{organization_id}/pricing/scenarios"
        ),
        headers=headers,
        json={
            "business_product_id": business_product_id,
            "baseline_units": 100,
            "demand_sensitivity": 1,
        },
    )

    assert pricing_response.status_code == 200
    assert len(pricing_response.json()["scenarios"]) == 3

    for report_format, content_type in (
        ("pdf", "application/pdf"),
        (
            "xlsx",
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet",
        ),
    ):
        report_response = client.get(
            (
                f"{ORGANIZATIONS_ENDPOINT}/"
                f"{organization_id}/competitor-intelligence/report"
            ),
            headers=headers,
            params={"format": report_format},
        )
        assert report_response.status_code == 200
        assert report_response.headers["content-type"] == content_type
        assert len(report_response.content) > 100

    watchlist_id = watchlist_entry["id"]

    status_response = client.patch(
        (
            f"{competitors_endpoint}/"
            f"{watchlist_id}/status"
        ),
        headers=headers,
        json={
            "is_active": False,
        },
    )

    assert status_response.status_code == 200

    assert (
        status_response.json()["is_active"]
        is False
    )

    active_only_response = client.get(
        competitors_endpoint,
        headers=headers,
        params={
            "is_active": True,
        },
    )

    assert active_only_response.status_code == 200
    assert active_only_response.json()["total"] == 0
