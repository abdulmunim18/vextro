from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing
from app.models.brand import Brand


PLACEHOLDER_IMAGE_URL = (
    "https://placehold.co/900x900/F5F7FB/3157D5?text=Phone"
)


def test_scraper_ingest_persists_listing_and_product_images(
    client: TestClient,
    database_session: Session,
) -> None:
    """Scraped galleries should be available to catalog API consumers."""

    external_id = f"daraz-image-{uuid4().hex[:12]}"
    image_urls = [
        "https://static-01.daraz.pk/images/test-front.jpg",
        "https://static-01.daraz.pk/images/test-back.jpg",
    ]

    model_name = f"Samsung Image Test Phone {external_id} 8GB RAM 256GB ROM"
    response = client.post(
        "/api/v1/ingest/daraz",
        json={
            "platform": "Daraz",
            "external_id": external_id,
            "model": model_name,
            "product_url": (
                f"https://www.daraz.pk/products/{external_id}.html"
            ),
            "price": 54999,
            "availability": "In Stock",
            "is_available": True,
            "image_urls": image_urls,
            "specifications": {
                "ram": "8GB",
                "storage_capacity": "256GB",
                "battery_capacity": "5000 mAh",
            },
        },
    )

    assert response.status_code == 201

    database_session.expire_all()
    listing = database_session.query(ProductListing).filter(
        ProductListing.external_id == external_id
    ).one()
    listing_images = database_session.query(ProductImage).filter(
        ProductImage.listing_id == listing.id
    ).order_by(ProductImage.sort_order).all()
    canonical_images = database_session.query(ProductImage).filter(
        ProductImage.canonical_product_id
        == listing.product_variant.canonical_product_id
    ).order_by(ProductImage.sort_order).all()

    assert [image.image_url for image in listing_images] == image_urls
    assert listing_images[0].is_primary is True
    assert [image.image_url for image in canonical_images] == image_urls
    assert canonical_images[0].is_primary is True
    assert (
        listing.product_variant.canonical_product.specifications["ram"]
        == "8GB"
    )
    assert (
        listing.product_variant.canonical_product.specifications[
            "battery_capacity"
        ]
        == "5000 mAh"
    )
    assert listing.product_variant.ram_gb == 8
    assert listing.product_variant.storage_gb == 256
    brand = database_session.get(
        Brand,
        listing.product_variant.canonical_product.brand_id,
    )
    assert brand is not None
    assert brand.name == "Samsung"


def test_real_scraper_image_replaces_canonical_placeholder(
    client: TestClient,
    database_session: Session,
) -> None:
    """A real marketplace image must become the canonical primary image."""

    external_id = f"priceoye-real-image-{uuid4().hex[:12]}"
    model_name = f"Placeholder Replacement Phone {external_id}"

    create_response = client.post(
        "/api/v1/ingest/priceoye",
        json={
            "platform": "PriceOye",
            "external_id": external_id,
            "model": model_name,
            "product_url": f"https://priceoye.pk/mobiles/{external_id}",
            "price": 49999,
            "availability": "In Stock",
            "is_available": True,
            "image_urls": [PLACEHOLDER_IMAGE_URL],
        },
    )
    assert create_response.status_code == 201

    real_image_url = (
        "https://images.priceoye.pk/test-real-phone-500x500.webp"
    )
    update_response = client.post(
        "/api/v1/ingest/priceoye",
        json={
            "platform": "PriceOye",
            "external_id": external_id,
            "model": model_name,
            "product_url": f"https://priceoye.pk/mobiles/{external_id}",
            "price": 49999,
            "availability": "In Stock",
            "is_available": True,
            "image_urls": [real_image_url],
        },
    )
    assert update_response.status_code == 201

    database_session.expire_all()
    listing = database_session.query(ProductListing).filter(
        ProductListing.external_id == external_id
    ).one()
    canonical_images = database_session.query(ProductImage).filter(
        ProductImage.canonical_product_id
        == listing.product_variant.canonical_product_id
    ).all()

    assert [image.image_url for image in canonical_images] == [
        real_image_url
    ]
    assert canonical_images[0].is_primary is True


def test_ingest_matches_same_product_across_marketplace_title_variants(
    client: TestClient,
    database_session: Session,
) -> None:
    """Brand prefixes and offer details must not split one product."""

    suffix = uuid4().hex[:10]
    base_title = f"Samsung Galaxy Match {suffix}"

    priceoye_response = client.post(
        "/api/v1/ingest/priceoye",
        json={
            "platform": "PriceOye",
            "external_id": f"priceoye-match-{suffix}",
            "model": base_title,
            "brand": "Samsung",
            "product_url": (
                f"https://priceoye.pk/mobiles/samsung/match-{suffix}"
            ),
            "price": 100000,
            "availability": "In Stock",
            "is_available": True,
        },
    )
    assert priceoye_response.status_code == 201

    daraz_response = client.post(
        "/api/v1/ingest/daraz",
        json={
            "platform": "Daraz",
            "external_id": f"daraz-match-{suffix}",
            "model": (
                f"Samsung Match {suffix} 8GB RAM 256GB ROM "
                "PTA Approved Official Warranty"
            ),
            "brand": "Samsung",
            "product_url": (
                f"https://www.daraz.pk/products/match-{suffix}.html"
            ),
            "price": 99000,
            "availability": "In Stock",
            "is_available": True,
        },
    )
    assert daraz_response.status_code == 201

    database_session.expire_all()
    listings = database_session.query(ProductListing).filter(
        ProductListing.external_id.in_({
            f"priceoye-match-{suffix}",
            f"daraz-match-{suffix}",
        })
    ).all()

    assert len(listings) == 2
    assert {
        listing.product_variant.canonical_product_id
        for listing in listings
    } == {
        listings[0].product_variant.canonical_product_id,
    }
