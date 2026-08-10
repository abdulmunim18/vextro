from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.platform import Platform
from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.seller import Seller


def unique_value(prefix: str) -> str:
    """Return a unique value for database tests."""

    return f"{prefix}-{uuid4().hex[:12]}"


def create_reference_data(
    database_session: Session,
) -> tuple[Category, Brand, Platform]:
    """Create category, brand, and platform records."""

    category = Category(
        name=unique_value("API Category"),
        slug=unique_value("api-category").lower(),
    )

    brand = Brand(
        name=unique_value("API Brand"),
        slug=unique_value("api-brand").lower(),
    )

    platform_code = unique_value("api-platform").lower()

    platform = Platform(
        name=unique_value("API Platform"),
        code=platform_code,
        base_url=f"https://{platform_code}.example.com",
    )

    database_session.add_all(
        [
            category,
            brand,
            platform,
        ]
    )
    database_session.flush()

    return category, brand, platform


def create_product(
    database_session: Session,
    *,
    category: Category,
    brand: Brand,
    name: str,
    is_active: bool = True,
) -> tuple[CanonicalProduct, ProductVariant]:
    """Create one canonical product with one active variant."""

    product = CanonicalProduct(
        category_id=category.id,
        brand_id=brand.id,
        name=name,
        slug=unique_value("api-product").lower(),
        model=unique_value("MODEL"),
        description=f"API test description for {name}.",
        specifications={
            "display": "6.7 inch",
            "battery": "5000 mAh",
        },
        is_active=is_active,
    )

    database_session.add(product)
    database_session.flush()

    variant = ProductVariant(
        canonical_product_id=product.id,
        sku=unique_value("API-SKU"),
        ram_gb=8,
        storage_gb=256,
        color="Black",
        condition="new",
        variant_attributes={
            "network": "5G",
        },
        is_active=True,
    )

    database_session.add(variant)
    database_session.flush()

    return product, variant


def test_list_products_supports_pagination_search_and_filters(
    client: TestClient,
    database_session: Session,
) -> None:
    """The product list should support pagination, search, and filters."""

    category, brand, _platform = create_reference_data(
        database_session
    )

    first_product, _first_variant = create_product(
        database_session,
        category=category,
        brand=brand,
        name="Alpha Phone X",
    )

    create_product(
        database_session,
        category=category,
        brand=brand,
        name="Alpha Phone Lite",
    )

    create_product(
        database_session,
        category=category,
        brand=brand,
        name="Beta Laptop Pro",
    )

    create_product(
        database_session,
        category=category,
        brand=brand,
        name="Hidden Inactive Product",
        is_active=False,
    )

    database_session.commit()

    paginated_response = client.get(
        "/api/v1/products",
        params={
            "page": 1,
            "page_size": 2,
            "category_slug": category.slug,
            "brand_slug": brand.slug,
        },
    )

    assert paginated_response.status_code == 200

    paginated_body = paginated_response.json()

    assert paginated_body["total"] == 3
    assert paginated_body["page"] == 1
    assert paginated_body["page_size"] == 2
    assert paginated_body["total_pages"] == 2
    assert len(paginated_body["items"]) == 2

    filtered_response = client.get(
        "/api/v1/products",
        params={
            "search": "Alpha Phone X",
            "category_slug": category.slug,
            "brand_slug": brand.slug,
        },
    )

    assert filtered_response.status_code == 200

    filtered_body = filtered_response.json()

    assert filtered_body["total"] == 1
    assert len(filtered_body["items"]) == 1
    assert filtered_body["items"][0]["id"] == first_product.id
    assert filtered_body["items"][0]["name"] == "Alpha Phone X"
def test_get_product_detail_includes_variants_and_images(
    client: TestClient,
    database_session: Session,
) -> None:
    """The detail endpoint should return variants and product images."""

    category, brand, _platform = create_reference_data(
        database_session
    )

    product, variant = create_product(
        database_session,
        category=category,
        brand=brand,
        name="Detail Test Smartphone",
    )

    product_image = ProductImage(
        canonical_product_id=product.id,
        image_url="https://example.com/images/detail-product.jpg",
        alt_text="Detail test smartphone",
        is_primary=True,
        sort_order=0,
    )

    database_session.add(product_image)
    database_session.commit()

    response = client.get(
        f"/api/v1/products/{product.id}"
    )

    assert response.status_code == 200

    body = response.json()

    assert body["id"] == product.id
    assert body["name"] == "Detail Test Smartphone"
    assert body["specifications"]["battery"] == "5000 mAh"

    assert len(body["variants"]) == 1
    assert body["variants"][0]["id"] == variant.id
    assert body["variants"][0]["ram_gb"] == 8
    assert body["variants"][0]["storage_gb"] == 256

    assert len(body["images"]) == 1
    assert body["images"][0]["id"] == product_image.id
    assert body["images"][0]["is_primary"] is True


def test_get_product_listings_returns_available_items_by_price(
    client: TestClient,
    database_session: Session,
) -> None:
    """Listings should be available only and sorted by lowest price."""

    category, brand, platform = create_reference_data(
        database_session
    )

    product, variant = create_product(
        database_session,
        category=category,
        brand=brand,
        name="Listing Test Smartphone",
    )

    seller = Seller(
        platform_id=platform.id,
        external_seller_id=unique_value("api-seller"),
        name="Verified API Seller",
        profile_url="https://example.com/seller",
        rating=Decimal("4.80"),
        review_count=500,
        is_verified=True,
        is_active=True,
    )

    database_session.add(seller)
    database_session.flush()

    cheaper_listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=variant.id,
        seller_id=seller.id,
        external_id=unique_value("cheap-listing"),
        title="Listing Test Smartphone - Lower Price",
        product_url="https://example.com/products/lower-price",
        current_price=Decimal("85000.00"),
        original_price=Decimal("90000.00"),
        currency="PKR",
        rating=Decimal("4.50"),
        review_count=100,
        warranty="1 Year",
        is_available=True,
    )

    expensive_listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=variant.id,
        seller_id=seller.id,
        external_id=unique_value("expensive-listing"),
        title="Listing Test Smartphone - Higher Price",
        product_url="https://example.com/products/higher-price",
        current_price=Decimal("95000.00"),
        currency="PKR",
        rating=Decimal("4.70"),
        review_count=200,
        is_available=True,
    )

    unavailable_listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=variant.id,
        seller_id=seller.id,
        external_id=unique_value("unavailable-listing"),
        title="Listing Test Smartphone - Unavailable",
        product_url="https://example.com/products/unavailable",
        current_price=Decimal("70000.00"),
        currency="PKR",
        is_available=False,
    )

    database_session.add_all(
        [
            cheaper_listing,
            expensive_listing,
            unavailable_listing,
        ]
    )
    database_session.flush()

    listing_image = ProductImage(
        listing_id=cheaper_listing.id,
        image_url="https://example.com/images/cheap-listing.jpg",
        alt_text="Cheaper marketplace listing",
        is_primary=True,
        sort_order=0,
    )

    database_session.add(listing_image)
    database_session.commit()

    response = client.get(
        f"/api/v1/products/{product.id}/listings"
    )

    assert response.status_code == 200

    body = response.json()
    items = body["items"]

    assert body["product_id"] == product.id
    assert body["product_name"] == "Listing Test Smartphone"
    assert body["total"] == 2
    assert len(items) == 2

    assert items[0]["id"] == cheaper_listing.id
    assert items[1]["id"] == expensive_listing.id

    assert Decimal(items[0]["current_price"]) == Decimal("85000.00")
    assert Decimal(items[1]["current_price"]) == Decimal("95000.00")

    returned_ids = {
        item["id"]
        for item in items
    }

    assert unavailable_listing.id not in returned_ids
    assert items[0]["seller"]["name"] == "Verified API Seller"
    assert len(items[0]["images"]) == 1


def test_product_detail_and_listings_return_404_for_missing_product(
    client: TestClient,
) -> None:
    """Missing product IDs should return a consistent 404 response."""

    missing_product_id = 999999999

    detail_response = client.get(
        f"/api/v1/products/{missing_product_id}"
    )

    listings_response = client.get(
        f"/api/v1/products/{missing_product_id}/listings"
    )

    assert detail_response.status_code == 404
    assert detail_response.json() == {
        "detail": "Product not found"
    }

    assert listings_response.status_code == 404
    assert listings_response.json() == {
        "detail": "Product not found"
    }


def test_product_list_rejects_invalid_pagination(
    client: TestClient,
) -> None:
    """FastAPI validation should reject invalid pagination values."""

    invalid_page_response = client.get(
        "/api/v1/products",
        params={
            "page": 0,
        },
    )

    invalid_page_size_response = client.get(
        "/api/v1/products",
        params={
            "page_size": 101,
        },
    )

    assert invalid_page_response.status_code == 422
    assert invalid_page_size_response.status_code == 422

def test_compare_products_returns_selected_product_details(
    client: TestClient,
    database_session: Session,
) -> None:
    """Comparison should return two selected active products."""

    category, brand, _platform = create_reference_data(
        database_session
    )

    first_product, first_variant = create_product(
        database_session,
        category=category,
        brand=brand,
        name="Comparison Phone Alpha",
    )

    second_product, second_variant = create_product(
        database_session,
        category=category,
        brand=brand,
        name="Comparison Phone Beta",
    )

    database_session.commit()

    response = client.get(
        "/api/v1/products/compare",
        params=[
            ("product_ids", first_product.id),
            ("product_ids", second_product.id),
        ],
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total"] == 2
    assert len(body["items"]) == 2
    assert "summary" in body

    summary = body["summary"]

    assert "cheapest_product_id" in summary
    assert "cheapest_product_name" in summary
    assert "lowest_current_price" in summary
    assert "currency" in summary
    assert "price_gap" in summary
    assert "price_gap_percentage" in summary

    returned_ids = {
        item["product"]["id"]
        for item in body["items"]
    }

    assert returned_ids == {
        first_product.id,
        second_product.id,
    }

    first_item = next(
        item
        for item in body["items"]
        if item["product"]["id"] == first_product.id
    )

    assert (
        first_item["product"]["name"]
        == "Comparison Phone Alpha"
    )

    assert (
        first_item["product"]["specifications"]["battery"]
        == "5000 mAh"
    )

    assert len(first_item["product"]["variants"]) == 1
    assert (
        first_item["product"]["variants"][0]["id"]
        == first_variant.id
    )

    second_item = next(
        item
        for item in body["items"]
        if item["product"]["id"] == second_product.id
    )

    assert (
        second_item["product"]["variants"][0]["id"]
        == second_variant.id
    )

    assert "listings" in first_item
    assert "price_history" in first_item
def test_compare_products_rejects_duplicate_product_ids(
    client: TestClient,
    database_session: Session,
) -> None:
    """The same product cannot be compared with itself."""

    category, brand, _platform = create_reference_data(
        database_session
    )

    product, _variant = create_product(
        database_session,
        category=category,
        brand=brand,
        name="Duplicate Comparison Phone",
    )

    database_session.commit()

    response = client.get(
        "/api/v1/products/compare",
        params=[
            ("product_ids", product.id),
            ("product_ids", product.id),
        ],
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"]
        == "Duplicate product IDs are not allowed."
    )


def test_compare_products_requires_at_least_two_products(
    client: TestClient,
) -> None:
    """Comparison requires at least two product IDs."""

    response = client.get(
        "/api/v1/products/compare",
        params=[
            ("product_ids", 1),
        ],
    )

    assert response.status_code == 422


def test_compare_products_rejects_more_than_three_products(
    client: TestClient,
) -> None:
    """Comparison supports a maximum of three products."""

    response = client.get(
        "/api/v1/products/compare",
        params=[
            ("product_ids", 1),
            ("product_ids", 2),
            ("product_ids", 3),
            ("product_ids", 4),
        ],
    )

    assert response.status_code == 422


def test_compare_products_returns_404_when_product_is_missing(
    client: TestClient,
    database_session: Session,
) -> None:
    """Missing products should make the comparison fail safely."""

    category, brand, _platform = create_reference_data(
        database_session
    )

    product, _variant = create_product(
        database_session,
        category=category,
        brand=brand,
        name="Existing Comparison Phone",
    )

    database_session.commit()

    response = client.get(
        "/api/v1/products/compare",
        params=[
            ("product_ids", product.id),
            ("product_ids", 999999999),
        ],
    )

    assert response.status_code == 404
    assert (
        response.json()["detail"]
        == "One or more products were not found."
    )
def test_compare_products_calculates_price_summary(
    client: TestClient,
    database_session: Session,
) -> None:
    """Comparison should summarize the cheapest current offers."""

    category, brand, platform = create_reference_data(
        database_session
    )

    samsung, samsung_variant = create_product(
        database_session,
        category=category,
        brand=brand,
        name="Samsung Comparison Phone",
    )

    xiaomi, xiaomi_variant = create_product(
        database_session,
        category=category,
        brand=brand,
        name="Xiaomi Comparison Phone",
    )

    seller = Seller(
        platform_id=platform.id,
        external_seller_id=unique_value("comparison-seller"),
        name="Comparison Seller",
        profile_url="https://example.com/comparison-seller",
        rating=Decimal("4.80"),
        review_count=500,
        is_verified=True,
        is_active=True,
    )

    database_session.add(seller)
    database_session.flush()

    samsung_listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=samsung_variant.id,
        seller_id=seller.id,
        external_id=unique_value("samsung-comparison"),
        title="Samsung Comparison Listing",
        product_url="https://example.com/samsung-comparison",
        current_price=Decimal("114999.00"),
        currency="PKR",
        rating=Decimal("4.80"),
        review_count=300,
        warranty="1 Year",
        is_available=True,
    )

    xiaomi_listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=xiaomi_variant.id,
        seller_id=seller.id,
        external_id=unique_value("xiaomi-comparison"),
        title="Xiaomi Comparison Listing",
        product_url="https://example.com/xiaomi-comparison",
        current_price=Decimal("76499.00"),
        currency="PKR",
        rating=Decimal("4.70"),
        review_count=250,
        warranty="1 Year",
        is_available=True,
    )

    database_session.add_all(
        [
            samsung_listing,
            xiaomi_listing,
        ]
    )

    database_session.commit()

    response = client.get(
        "/api/v1/products/compare",
        params=[
            ("product_ids", samsung.id),
            ("product_ids", xiaomi.id),
        ],
    )

    assert response.status_code == 200

    summary = response.json()["summary"]

    assert summary["cheapest_product_id"] == xiaomi.id

    assert (
        summary["cheapest_product_name"]
        == "Xiaomi Comparison Phone"
    )

    assert Decimal(
        summary["lowest_current_price"]
    ) == Decimal("76499.00")

    assert summary["currency"] == "PKR"

    assert Decimal(
        summary["price_gap"]
    ) == Decimal("38500.00")

    assert Decimal(
        summary["price_gap_percentage"]
    ) == Decimal("50.33")