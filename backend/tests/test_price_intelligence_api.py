from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.platform import Platform
from app.models.price_history import PriceHistory
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.seller import Seller


def unique_value(prefix: str) -> str:
    """Generate a unique value for database tests."""

    return f"{prefix}-{uuid4().hex[:12]}"


def create_price_history_catalog(
    database_session: Session,
) -> tuple[
    CanonicalProduct,
    ProductListing,
    ProductListing,
    Platform,
    Seller,
]:
    """Create a product with two marketplace listings."""

    category = Category(
        name=unique_value("Price API Category"),
        slug=unique_value("price-api-category").lower(),
        is_active=True,
    )

    brand = Brand(
        name=unique_value("Price API Brand"),
        slug=unique_value("price-api-brand").lower(),
        is_active=True,
    )

    platform_code = unique_value("price-api-platform").lower()

    platform = Platform(
        name=unique_value("Price API Platform"),
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
        name=unique_value("Price API Smartphone"),
        slug=unique_value("price-api-smartphone").lower(),
        model=unique_value("PRICE-API-MODEL"),
        description="Product used for price intelligence API tests.",
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
        sku=unique_value("PRICE-API-SKU"),
        ram_gb=8,
        storage_gb=256,
        color="Black",
        condition="new",
        variant_attributes={
            "network": "5G",
        },
        is_active=True,
    )

    seller = Seller(
        platform_id=platform.id,
        external_seller_id=unique_value("price-api-seller"),
        name=unique_value("Price API Seller"),
        profile_url="https://example.com/price-api-seller",
        rating=Decimal("4.70"),
        review_count=250,
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

    cheaper_listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=variant.id,
        seller_id=seller.id,
        external_id=unique_value("cheaper-price-listing"),
        title="Price API Smartphone - Lower Current Price",
        product_url="https://example.com/products/lower-current-price",
        current_price=Decimal("90000.00"),
        original_price=Decimal("105000.00"),
        currency="PKR",
        rating=Decimal("4.50"),
        review_count=120,
        warranty="1 Year",
        is_available=True,
    )

    expensive_listing = ProductListing(
        platform_id=platform.id,
        product_variant_id=variant.id,
        seller_id=seller.id,
        external_id=unique_value("expensive-price-listing"),
        title="Price API Smartphone - Higher Current Price",
        product_url="https://example.com/products/higher-current-price",
        current_price=Decimal("120000.00"),
        original_price=Decimal("125000.00"),
        currency="PKR",
        rating=Decimal("4.60"),
        review_count=80,
        warranty="1 Year",
        is_available=True,
    )

    database_session.add_all(
        [
            cheaper_listing,
            expensive_listing,
        ]
    )
    database_session.flush()

    return (
        product,
        cheaper_listing,
        expensive_listing,
        platform,
        seller,
    )


def test_product_price_history_returns_chart_ready_statistics(
    client: TestClient,
    database_session: Session,
) -> None:
    """Return ordered listings, chart points, and calculated statistics."""

    (
        product,
        cheaper_listing,
        expensive_listing,
        platform,
        seller,
    ) = create_price_history_catalog(database_session)

    snapshots = [
        PriceHistory(
            listing_id=cheaper_listing.id,
            price=Decimal("100000.00"),
            original_price=Decimal("105000.00"),
            currency="PKR",
            source="automated-test",
            captured_at=datetime(
                2026,
                1,
                1,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        ),
        PriceHistory(
            listing_id=cheaper_listing.id,
            price=Decimal("95000.00"),
            original_price=Decimal("105000.00"),
            currency="PKR",
            source="automated-test",
            captured_at=datetime(
                2026,
                1,
                2,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        ),
        PriceHistory(
            listing_id=cheaper_listing.id,
            price=Decimal("85000.00"),
            original_price=Decimal("105000.00"),
            currency="PKR",
            source="automated-test",
            captured_at=datetime(
                2026,
                1,
                3,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        ),
    ]

    database_session.add_all(snapshots)
    database_session.commit()

    response = client.get(
        f"/api/v1/products/{product.id}/price-history"
    )

    assert response.status_code == 200

    body = response.json()
    listings = body["listings"]

    assert body["product_id"] == product.id
    assert body["product_name"] == product.name
    assert body["total_listings"] == 2
    assert body["total_points"] == 3

    # Listings must be ordered by current price.
    assert listings[0]["listing_id"] == cheaper_listing.id
    assert listings[1]["listing_id"] == expensive_listing.id

    cheaper_result = listings[0]
    cheaper_summary = cheaper_result["summary"]

    assert cheaper_result["platform_name"] == platform.name
    assert cheaper_result["seller_name"] == seller.name

    assert Decimal(
        str(cheaper_summary["current_price"])
    ) == Decimal("90000.00")

    assert Decimal(
        str(cheaper_summary["lowest_price"])
    ) == Decimal("85000.00")

    assert Decimal(
        str(cheaper_summary["highest_price"])
    ) == Decimal("100000.00")

    assert Decimal(
        str(cheaper_summary["average_price"])
    ) == Decimal("93333.33")

    assert Decimal(
        str(cheaper_summary["price_change"])
    ) == Decimal("-10000.00")

    assert Decimal(
        str(cheaper_summary["price_change_percentage"])
    ) == Decimal("-10.00")

    returned_prices = [
        Decimal(str(point["price"]))
        for point in cheaper_result["points"]
    ]

    assert returned_prices == [
        Decimal("100000.00"),
        Decimal("95000.00"),
        Decimal("85000.00"),
    ]

    # A listing without snapshots should still return its current price.
    expensive_result = listings[1]
    expensive_summary = expensive_result["summary"]

    assert expensive_result["points"] == []

    assert Decimal(
        str(expensive_summary["current_price"])
    ) == Decimal("120000.00")

    assert expensive_summary["lowest_price"] is None
    assert expensive_summary["highest_price"] is None
    assert expensive_summary["average_price"] is None
    assert expensive_summary["price_change"] is None
    assert expensive_summary["price_change_percentage"] is None


def test_product_price_history_supports_date_range_filtering(
    client: TestClient,
    database_session: Session,
) -> None:
    """Only snapshots inside the requested date range should be returned."""

    (
        product,
        listing,
        _second_listing,
        _platform,
        _seller,
    ) = create_price_history_catalog(database_session)

    snapshots = [
        PriceHistory(
            listing_id=listing.id,
            price=Decimal("100000.00"),
            currency="PKR",
            source="automated-test",
            captured_at=datetime(
                2026,
                1,
                1,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        ),
        PriceHistory(
            listing_id=listing.id,
            price=Decimal("95000.00"),
            currency="PKR",
            source="automated-test",
            captured_at=datetime(
                2026,
                1,
                15,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        ),
        PriceHistory(
            listing_id=listing.id,
            price=Decimal("90000.00"),
            currency="PKR",
            source="automated-test",
            captured_at=datetime(
                2026,
                2,
                1,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        ),
    ]

    database_session.add_all(snapshots)
    database_session.commit()

    response = client.get(
        f"/api/v1/products/{product.id}/price-history",
        params={
            "date_from": "2026-01-10T00:00:00Z",
            "date_to": "2026-01-31T23:59:59Z",
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["total_listings"] == 2
    assert body["total_points"] == 1

    filtered_listing = next(
        item
        for item in body["listings"]
        if item["listing_id"] == listing.id
    )

    assert len(filtered_listing["points"]) == 1

    assert Decimal(
        str(filtered_listing["points"][0]["price"])
    ) == Decimal("95000.00")

    summary = filtered_listing["summary"]

    assert Decimal(
        str(summary["lowest_price"])
    ) == Decimal("95000.00")

    assert Decimal(
        str(summary["highest_price"])
    ) == Decimal("95000.00")

    assert Decimal(
        str(summary["average_price"])
    ) == Decimal("95000.00")

    assert Decimal(
        str(summary["price_change"])
    ) == Decimal("-5000.00")

    assert Decimal(
        str(summary["price_change_percentage"])
    ) == Decimal("-5.26")


def test_product_price_history_returns_404_for_missing_product(
    client: TestClient,
) -> None:
    """A missing product should return a consistent 404 response."""

    response = client.get(
        "/api/v1/products/999999999/price-history"
    )

    assert response.status_code == 404
    assert response.json() == {
        "detail": "Product not found"
    }


def test_product_price_history_rejects_invalid_parameters(
    client: TestClient,
) -> None:
    """Invalid IDs and reversed date ranges should return 422."""

    invalid_id_response = client.get(
        "/api/v1/products/0/price-history"
    )

    reversed_range_response = client.get(
        "/api/v1/products/1/price-history",
        params={
            "date_from": "2026-02-01T00:00:00Z",
            "date_to": "2026-01-01T00:00:00Z",
        },
    )

    assert invalid_id_response.status_code == 422

    assert reversed_range_response.status_code == 422
    assert reversed_range_response.json() == {
        "detail": "date_from cannot be later than date_to"
    }