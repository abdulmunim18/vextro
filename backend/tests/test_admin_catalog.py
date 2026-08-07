from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.platform import Platform
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.role import Role
from app.models.seller import Seller
from app.models.user import User


TEST_PASSWORD = "StrongPassword123!"


@pytest.fixture(autouse=True)
def cleanup_admin_catalog_records(
    database_session: Session,
):
    """Remove catalog records created by each admin-catalog test."""

    original_listing_ids = set(
        database_session.scalars(
            select(ProductListing.id)
        ).all()
    )

    original_seller_ids = set(
        database_session.scalars(
            select(Seller.id)
        ).all()
    )

    original_variant_ids = set(
        database_session.scalars(
            select(ProductVariant.id)
        ).all()
    )

    original_product_ids = set(
        database_session.scalars(
            select(CanonicalProduct.id)
        ).all()
    )

    original_brand_ids = set(
        database_session.scalars(
            select(Brand.id)
        ).all()
    )

    original_category_ids = set(
        database_session.scalars(
            select(Category.id)
        ).all()
    )

    yield

    database_session.rollback()

    if original_listing_ids:
        database_session.execute(
            delete(ProductListing).where(
                ProductListing.id.notin_(
                    original_listing_ids
                )
            )
        )
    else:
        database_session.execute(
            delete(ProductListing)
        )

    if original_seller_ids:
        database_session.execute(
            delete(Seller).where(
                Seller.id.notin_(
                    original_seller_ids
                )
            )
        )
    else:
        database_session.execute(
            delete(Seller)
        )

    if original_variant_ids:
        database_session.execute(
            delete(ProductVariant).where(
                ProductVariant.id.notin_(
                    original_variant_ids
                )
            )
        )
    else:
        database_session.execute(
            delete(ProductVariant)
        )

    if original_product_ids:
        database_session.execute(
            delete(CanonicalProduct).where(
                CanonicalProduct.id.notin_(
                    original_product_ids
                )
            )
        )
    else:
        database_session.execute(
            delete(CanonicalProduct)
        )

    if original_brand_ids:
        database_session.execute(
            delete(Brand).where(
                Brand.id.notin_(
                    original_brand_ids
                )
            )
        )
    else:
        database_session.execute(
            delete(Brand)
        )

    if original_category_ids:
        database_session.execute(
            delete(Category).where(
                Category.id.notin_(
                    original_category_ids
                )
            )
        )
    else:
        database_session.execute(
            delete(Category)
        )

    database_session.commit()


def unique_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


def authorization_header(
    access_token: str,
) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {access_token}",
    }


def create_admin_user(
    database_session: Session,
) -> User:
    admin_role = database_session.scalar(
        select(Role).where(
            Role.name == "admin"
        )
    )

    assert admin_role is not None

    admin_user = User(
        full_name="Catalog Administrator",
        email=(
            f"{unique_value('admin')}"
            "@example.com"
        ),
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


def register_consumer(
    client: TestClient,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "Catalog Consumer",
            "email": (
                f"{unique_value('consumer')}"
                "@example.com"
            ),
            "password": TEST_PASSWORD,
            "account_type": "consumer",
        },
    )

    assert response.status_code == 201

    return response.json()


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
) -> dict[str, str]:
    admin_user = create_admin_user(
        database_session
    )

    tokens = login(
        client,
        email=admin_user.email,
    )

    return authorization_header(
        str(tokens["access_token"])
    )


def create_product(
    database_session: Session,
    *,
    name_prefix: str,
    is_active: bool = True,
) -> tuple[
    CanonicalProduct,
    Category,
    Brand,
]:
    identifier = uuid4().hex

    category = Category(
        name=f"{name_prefix} Category",
        slug=f"category-{identifier}",
        is_active=True,
    )

    brand = Brand(
        name=f"{name_prefix} Brand {identifier}",
        slug=f"brand-{identifier}",
    )

    database_session.add_all([
        category,
        brand,
    ])

    database_session.flush()

    product = CanonicalProduct(
        category_id=category.id,
        brand_id=brand.id,
        name=f"{name_prefix} Product",
        slug=f"product-{identifier}",
        model=f"MODEL-{identifier[:8]}",
        description="Admin catalog test product.",
        specifications={
            "test": True,
        },
        is_active=is_active,
    )

    database_session.add(product)
    database_session.commit()
    database_session.refresh(product)

    return product, category, brand


def create_listing(
    database_session: Session,
    *,
    name_prefix: str,
    platform_code: str = "daraz",
    is_available: bool = True,
) -> tuple[
    ProductListing,
    CanonicalProduct,
    Platform,
    Seller,
]:
    product, _, _ = create_product(
        database_session,
        name_prefix=name_prefix,
    )

    platform = database_session.scalar(
        select(Platform).where(
            Platform.code == platform_code
        )
    )

    assert platform is not None

    identifier = uuid4().hex

    variant = ProductVariant(
        canonical_product_id=product.id,
        sku=f"SKU-{identifier}",
        ram_gb=8,
        storage_gb=256,
        color="Black",
        condition="new",
        variant_attributes={
            "test": True,
        },
        is_active=True,
    )

    seller = Seller(
        platform_id=platform.id,
        external_seller_id=(
            f"seller-{identifier}"
        ),
        name=f"{name_prefix} Seller",
        profile_url=(
            f"https://example.com/sellers/{identifier}"
        ),
        rating=Decimal("4.70"),
        review_count=120,
        is_verified=True,
        is_active=True,
    )

    database_session.add_all([
        variant,
        seller,
    ])

    database_session.flush()

    listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=variant.id,
        seller_id=seller.id,
        external_id=f"listing-{identifier}",
        title=f"{name_prefix} Marketplace Listing",
        product_url=(
            f"https://example.com/products/{identifier}"
        ),
        current_price=Decimal("99999.00"),
        original_price=Decimal("109999.00"),
        currency="PKR",
        rating=Decimal("4.50"),
        review_count=75,
        warranty="1 Year Warranty",
        is_available=is_available,
        raw_payload={
            "test": True,
        },
    )

    database_session.add(listing)
    database_session.commit()
    database_session.refresh(listing)

    return listing, product, platform, seller


def test_admin_products_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/admin/products"
    )

    assert response.status_code == 401


def test_consumer_cannot_list_admin_products(
    client: TestClient,
) -> None:
    consumer = register_consumer(client)

    tokens = login(
        client,
        email=str(consumer["email"]),
    )

    response = client.get(
        "/api/v1/admin/products",
        headers=authorization_header(
            str(tokens["access_token"])
        ),
    )

    assert response.status_code == 403


def test_admin_can_list_paginated_products(
    client: TestClient,
    database_session: Session,
) -> None:
    headers = admin_headers(
        client,
        database_session,
    )

    create_product(
        database_session,
        name_prefix="Pagination One",
    )

    create_product(
        database_session,
        name_prefix="Pagination Two",
    )

    create_product(
        database_session,
        name_prefix="Pagination Three",
    )

    response = client.get(
        "/api/v1/admin/products",
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
    assert len(response_data["items"]) == 2


def test_admin_can_search_and_filter_products(
    client: TestClient,
    database_session: Session,
) -> None:
    headers = admin_headers(
        client,
        database_session,
    )

    product, category, brand = create_product(
        database_session,
        name_prefix="Searchable Galaxy",
        is_active=True,
    )

    response = client.get(
        "/api/v1/admin/products",
        params={
            "q": "Searchable Galaxy",
            "category_id": category.id,
            "brand_id": brand.id,
            "is_active": True,
        },
        headers=headers,
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["total_items"] == 1
    assert len(response_data["items"]) == 1

    returned_product = response_data["items"][0]

    assert returned_product["id"] == product.id
    assert returned_product["is_active"] is True
    assert returned_product["category_id"] == category.id
    assert returned_product["brand_id"] == brand.id
    assert returned_product["variant_count"] == 0
    assert returned_product["listing_count"] == 0


def test_admin_can_deactivate_and_reactivate_product(
    client: TestClient,
    database_session: Session,
) -> None:
    headers = admin_headers(
        client,
        database_session,
    )

    product, _, _ = create_product(
        database_session,
        name_prefix="Status Product",
    )

    deactivate_response = client.patch(
        (
            f"/api/v1/admin/products/"
            f"{product.id}/status"
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

    stored_product = database_session.scalar(
        select(CanonicalProduct).where(
            CanonicalProduct.id == product.id
        )
    )

    assert stored_product is not None
    assert stored_product.is_active is False

    reactivate_response = client.patch(
        (
            f"/api/v1/admin/products/"
            f"{product.id}/status"
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


def test_product_status_rejects_missing_product(
    client: TestClient,
    database_session: Session,
) -> None:
    headers = admin_headers(
        client,
        database_session,
    )

    response = client.patch(
        (
            "/api/v1/admin/products/"
            "999999999/status"
        ),
        json={
            "is_active": False,
        },
        headers=headers,
    )

    assert response.status_code == 404

    assert (
        response.json()["detail"]["code"]
        == "PRODUCT_NOT_FOUND"
    )


def test_admin_products_reject_invalid_page_size(
    client: TestClient,
    database_session: Session,
) -> None:
    headers = admin_headers(
        client,
        database_session,
    )

    response = client.get(
        "/api/v1/admin/products",
        params={
            "page_size": 101,
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_admin_listings_requires_authentication(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/admin/listings"
    )

    assert response.status_code == 401


def test_consumer_cannot_list_admin_listings(
    client: TestClient,
) -> None:
    consumer = register_consumer(client)

    tokens = login(
        client,
        email=str(consumer["email"]),
    )

    response = client.get(
        "/api/v1/admin/listings",
        headers=authorization_header(
            str(tokens["access_token"])
        ),
    )

    assert response.status_code == 403


def test_admin_can_list_paginated_listings(
    client: TestClient,
    database_session: Session,
) -> None:
    headers = admin_headers(
        client,
        database_session,
    )

    create_listing(
        database_session,
        name_prefix="Listing Pagination One",
    )

    create_listing(
        database_session,
        name_prefix="Listing Pagination Two",
    )

    create_listing(
        database_session,
        name_prefix="Listing Pagination Three",
    )

    response = client.get(
        "/api/v1/admin/listings",
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
    assert len(response_data["items"]) == 2


def test_admin_can_search_and_filter_listings(
    client: TestClient,
    database_session: Session,
) -> None:
    headers = admin_headers(
        client,
        database_session,
    )

    listing, product, platform, seller = (
        create_listing(
            database_session,
            name_prefix="Searchable Daraz",
            platform_code="daraz",
            is_available=True,
        )
    )

    create_listing(
        database_session,
        name_prefix="Unavailable PriceOye",
        platform_code="priceoye",
        is_available=False,
    )

    response = client.get(
        "/api/v1/admin/listings",
        params={
            "q": "Searchable Daraz",
            "platform_id": platform.id,
            "product_id": product.id,
            "is_available": True,
        },
        headers=headers,
    )

    assert response.status_code == 200

    response_data = response.json()

    assert response_data["total_items"] == 1
    assert len(response_data["items"]) == 1

    returned_listing = response_data["items"][0]

    assert returned_listing["id"] == listing.id
    assert returned_listing["product_id"] == product.id
    assert (
        returned_listing["platform_id"]
        == platform.id
    )
    assert (
        returned_listing["platform_code"]
        == "daraz"
    )
    assert (
        returned_listing["seller_name"]
        == seller.name
    )
    assert (
        returned_listing["seller_is_verified"]
        is True
    )
    assert returned_listing["is_available"] is True
    assert returned_listing["currency"] == "PKR"


def test_admin_listings_reject_invalid_page_size(
    client: TestClient,
    database_session: Session,
) -> None:
    headers = admin_headers(
        client,
        database_session,
    )

    response = client.get(
        "/api/v1/admin/listings",
        params={
            "page_size": 101,
        },
        headers=headers,
    )

    assert response.status_code == 422