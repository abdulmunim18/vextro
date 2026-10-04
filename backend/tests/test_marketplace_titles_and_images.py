"""Regression tests for marketplace titles that carry the seller's store.

A Daraz store publishes every phone under its own name and glues a stock
code onto the end ("Carrefour Samsung Galaxy A07 4+128GB Green-303662").
Taken literally, that text registers a second canonical product that the
same phone on PriceOye can never match, and the catalog shows a shop name
where a phone should be. These tests pin the cleaning, the cross-marketplace
resolution it enables, and the gallery the catalog needs to render a card.
"""

from collections.abc import Generator
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.canonical_product import CanonicalProduct
from app.models.price_history import PriceHistory
from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.services.smartphone_normalization import clean_marketplace_title


LISTINGS_ENDPOINT = "/api/v1/internal/acquisition/listings"
RESOLVE_ENDPOINT = "/api/v1/internal/acquisition/resolve-product"

TEST_INGESTION_KEY = "VextroTitleTestIngestionKey2026"

CAPTURE_TIME = datetime(2026, 10, 4, 6, 30, tzinfo=timezone.utc)

DARAZ_GALLERY = [
    "https://img.drz.lazcdn.com/a07-green-1.jpg",
    "https://img.drz.lazcdn.com/a07-green-2.jpg",
]


@pytest.fixture(autouse=True)
def configure_ingestion_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "ingestion_api_key",
        TEST_INGESTION_KEY,
    )


def headers() -> dict[str, str]:
    return {"X-Ingestion-Key": TEST_INGESTION_KEY}


@pytest.fixture
def discovered_products(
    database_session: Session,
) -> Generator[list[int], None, None]:
    """Remove whatever catalog records a test registers."""

    created: list[int] = []

    yield created

    database_session.rollback()

    if not created:
        return

    variant_ids = list(
        database_session.scalars(
            select(ProductVariant.id).where(
                ProductVariant.canonical_product_id.in_(created)
            )
        )
    )
    listing_ids = (
        list(
            database_session.scalars(
                select(ProductListing.id).where(
                    ProductListing.product_variant_id.in_(variant_ids)
                )
            )
        )
        if variant_ids
        else []
    )

    statements = [
        delete(ProductImage).where(
            ProductImage.canonical_product_id.in_(created)
        ),
    ]
    if listing_ids:
        statements.extend(
            [
                delete(ProductImage).where(
                    ProductImage.listing_id.in_(listing_ids)
                ),
                delete(PriceHistory).where(
                    PriceHistory.listing_id.in_(listing_ids)
                ),
                delete(ProductListing).where(
                    ProductListing.id.in_(listing_ids)
                ),
            ]
        )
    if variant_ids:
        statements.append(
            delete(ProductVariant).where(ProductVariant.id.in_(variant_ids))
        )
    statements.append(
        delete(CanonicalProduct).where(CanonicalProduct.id.in_(created))
    )

    for statement in statements:
        database_session.execute(
            statement.execution_options(synchronize_session=False)
        )

    database_session.commit()


def resolve(
    client: TestClient,
    discovered_products: list[int],
    **payload: object,
) -> dict[str, object]:
    """Resolve one scraped product and track the catalog records created."""

    response = client.post(
        RESOLVE_ENDPOINT,
        headers=headers(),
        json=payload,
    )

    assert response.status_code == 200, response.text

    result = response.json()

    if result.get("canonical_product_id"):
        product_id = int(result["canonical_product_id"])
        if product_id not in discovered_products:
            discovered_products.append(product_id)

    return result


def ingest(
    client: TestClient,
    **payload: object,
) -> dict[str, object]:
    response = client.post(
        LISTINGS_ENDPOINT,
        headers=headers(),
        json=payload,
    )

    assert response.status_code in {200, 201}, response.text

    return response.json()


# --------------------------------------------------------------------------
# Title cleaning
# --------------------------------------------------------------------------


def test_store_name_and_stock_code_leave_the_title() -> None:
    assert clean_marketplace_title(
        "Carrefour Samsung Galaxy A07 4+128GB Green-303662",
        "Carrefour Pakistan",
    ) == "Samsung Galaxy A07 4+128GB Green"
    assert clean_marketplace_title(
        "Carrefour Official Store Samsung Galaxy A07 6+128GB Black-303666",
        "Carrefour",
    ) == "Samsung Galaxy A07 6+128GB Black"
    assert clean_marketplace_title(
        "AL-Fatah Samsung Galaxy A07",
        "AL Fatah Electronics",
    ) == "Samsung Galaxy A07"


def test_a_stock_code_goes_but_a_model_year_stays() -> None:
    """A six-digit shop code is noise; a model year identifies the phone."""

    assert clean_marketplace_title(
        "Carrefour | Oppo Mobile A6 8+256GB Gold (306237)",
        "Carrefour Pakistan",
    ) == "Oppo Mobile A6 8+256GB Gold"
    assert clean_marketplace_title(
        "Samsung Galaxy A07 [SKU: 303662]",
    ) == "Samsung Galaxy A07"
    assert clean_marketplace_title("Nokia 130 (2023)") == "Nokia 130 (2023)"


def test_cleaning_is_idempotent_and_leaves_clean_titles_alone() -> None:
    cleaned = clean_marketplace_title(
        "Samsung Galaxy A07 4+128GB Green",
        "Carrefour Pakistan",
    )

    assert cleaned == "Samsung Galaxy A07 4+128GB Green"
    assert clean_marketplace_title(cleaned, "Carrefour Pakistan") == cleaned


def test_a_brand_is_never_mistaken_for_the_store_that_sells_it() -> None:
    """A store named after the brand must not eat the brand."""

    assert clean_marketplace_title(
        "Samsung Galaxy A07 128GB",
        "Samsung Official Store",
    ) == "Samsung Galaxy A07 128GB"
    assert clean_marketplace_title(
        "Apple iPhone 15 Pro Max 256GB",
        "Apple Store Pakistan",
    ) == "Apple iPhone 15 Pro Max 256GB"


def test_shop_words_only_go_when_a_phone_follows_them() -> None:
    assert clean_marketplace_title(
        "Official Store Infinix Hot 50 8GB 256GB",
    ) == "Infinix Hot 50 8GB 256GB"
    assert clean_marketplace_title("Carrefour", "Carrefour") == "Carrefour"


# --------------------------------------------------------------------------
# Cross-marketplace resolution
# --------------------------------------------------------------------------


def test_a_store_prefixed_daraz_phone_is_the_same_product_on_priceoye(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],
) -> None:
    """The reported bug: one phone registered twice, matched never.

    Daraz sells the phone through Carrefour, PriceOye sells it under its
    own name. Both must land on one canonical product, named after the
    phone rather than after the shop.
    """

    token = uuid4().hex[:8]
    model_name = f"Galaxy TX{token}"

    daraz = resolve(
        client,
        discovered_products,
        platform_code="daraz",
        external_id=f"CARREFOUR-{token}",
        title=f"Carrefour Samsung {model_name} 4+128GB Green-303662",
        seller_name="Carrefour Pakistan",
        specifications={"ram": "4GB", "storage_capacity": "128GB"},
    )

    assert daraz["product_created"] is True

    product = database_session.get(
        CanonicalProduct,
        int(daraz["canonical_product_id"]),
    )

    assert product is not None
    assert product.name == f"Samsung {model_name}"
    assert product.model == f"Samsung {model_name}"

    ingest(
        client,
        platform_code="daraz",
        product_variant_id=int(daraz["product_variant_id"]),
        external_id=f"CARREFOUR-{token}",
        title=f"Carrefour Samsung {model_name} 4+128GB Green-303662",
        product_url=f"https://www.daraz.pk/products/i{token}.html",
        current_price=62500.0,
        currency="PKR",
        is_available=True,
        scraped_at=CAPTURE_TIME.isoformat(),
        seller={"name": "Carrefour Pakistan"},
        image_urls=DARAZ_GALLERY,
    )

    priceoye = resolve(
        client,
        discovered_products,
        platform_code="priceoye",
        external_id=f"priceoye-{token}",
        title=f"Samsung {model_name}",
        brand="Samsung",
        specifications={"ram": "4GB", "storage_capacity": "128GB"},
    )

    assert priceoye["matched"] is True
    assert priceoye["product_created"] is False
    assert (
        priceoye["canonical_product_id"]
        == daraz["canonical_product_id"]
    )


def test_a_cleaned_title_still_matches_the_listing_it_belongs_to(
    client: TestClient,
    discovered_products: list[int],
) -> None:
    """A second crawl of the same store listing reuses its own variant."""

    token = uuid4().hex[:8]
    payload = {
        "platform_code": "daraz",
        "external_id": f"REFRESH-{token}",
        "title": f"Carrefour Samsung Galaxy TX{token} 4+128GB Green-303662",
        "seller_name": "Carrefour Pakistan",
        "specifications": {"ram": "4GB", "storage_capacity": "128GB"},
    }

    first = resolve(client, discovered_products, **payload)
    second = resolve(client, discovered_products, **payload)

    assert first["product_created"] is True
    assert second["product_created"] is False
    assert second["product_variant_id"] == first["product_variant_id"]


# --------------------------------------------------------------------------
# Galleries
# --------------------------------------------------------------------------


def test_an_ingested_listing_keeps_its_marketplace_gallery(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],
) -> None:
    """Images reach the catalog, which is what renders the product card."""

    token = uuid4().hex[:8]
    resolved = resolve(
        client,
        discovered_products,
        platform_code="daraz",
        external_id=f"GALLERY-{token}",
        title=f"Carrefour Samsung Galaxy TX{token} 4+128GB Green-303662",
        seller_name="Carrefour Pakistan",
        specifications={"ram": "4GB", "storage_capacity": "128GB"},
    )

    result = ingest(
        client,
        platform_code="daraz",
        product_variant_id=int(resolved["product_variant_id"]),
        external_id=f"GALLERY-{token}",
        title=f"Carrefour Samsung Galaxy TX{token} 4+128GB Green-303662",
        product_url=f"https://www.daraz.pk/products/i{token}.html",
        current_price=62500.0,
        currency="PKR",
        is_available=True,
        scraped_at=CAPTURE_TIME.isoformat(),
        seller={"name": "Carrefour Pakistan"},
        image_urls=DARAZ_GALLERY,
    )

    database_session.expire_all()
    listing = database_session.get(ProductListing, int(result["listing_id"]))

    assert listing is not None
    # The shopper sees the phone, not the shop that sells it.
    assert listing.title == f"Samsung Galaxy TX{token} 4+128GB Green"

    listing_images = list(
        database_session.scalars(
            select(ProductImage)
            .where(ProductImage.listing_id == listing.id)
            .order_by(ProductImage.sort_order)
        )
    )

    assert [image.image_url for image in listing_images] == DARAZ_GALLERY
    assert listing_images[0].is_primary is True

    product_id = int(resolved["canonical_product_id"])
    detail = client.get(f"/api/v1/products/{product_id}")

    assert detail.status_code == 200, detail.text
    assert [
        image["image_url"] for image in detail.json()["images"]
    ] == DARAZ_GALLERY


def test_a_scrape_without_images_keeps_the_gallery_it_had(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],
) -> None:
    """A failed image read must not blank a product card that worked."""

    token = uuid4().hex[:8]
    resolved = resolve(
        client,
        discovered_products,
        platform_code="daraz",
        external_id=f"NOIMAGE-{token}",
        title=f"Samsung Galaxy TX{token} 4+128GB Green",
        specifications={"ram": "4GB", "storage_capacity": "128GB"},
    )

    listing_payload: dict[str, object] = {
        "platform_code": "daraz",
        "product_variant_id": int(resolved["product_variant_id"]),
        "external_id": f"NOIMAGE-{token}",
        "title": f"Samsung Galaxy TX{token} 4+128GB Green",
        "product_url": f"https://www.daraz.pk/products/i{token}.html",
        "current_price": 62500.0,
        "currency": "PKR",
        "is_available": True,
        "scraped_at": CAPTURE_TIME.isoformat(),
        "image_urls": DARAZ_GALLERY,
    }

    first = ingest(client, **listing_payload)

    second_payload = dict(listing_payload)
    second_payload["image_urls"] = []
    second_payload["current_price"] = 61000.0
    second_payload["scraped_at"] = datetime(
        2026, 10, 4, 18, 30, tzinfo=timezone.utc
    ).isoformat()

    ingest(client, **second_payload)

    database_session.expire_all()
    stored = list(
        database_session.scalars(
            select(ProductImage.image_url).where(
                ProductImage.listing_id == int(first["listing_id"])
            )
        )
    )

    assert sorted(stored) == sorted(DARAZ_GALLERY)


def test_a_relative_image_url_is_rejected_by_the_listing_contract(
    client: TestClient,
    discovered_products: list[int],
) -> None:
    """Only absolute URLs can be rendered, so only those are accepted."""

    token = uuid4().hex[:8]
    resolved = resolve(
        client,
        discovered_products,
        platform_code="daraz",
        external_id=f"BADIMAGE-{token}",
        title=f"Samsung Galaxy TX{token} 4+128GB Green",
        specifications={"ram": "4GB", "storage_capacity": "128GB"},
    )

    response = client.post(
        LISTINGS_ENDPOINT,
        headers=headers(),
        json={
            "platform_code": "daraz",
            "product_variant_id": int(resolved["product_variant_id"]),
            "external_id": f"BADIMAGE-{token}",
            "title": f"Samsung Galaxy TX{token} 4+128GB Green",
            "product_url": f"https://www.daraz.pk/products/i{token}.html",
            "current_price": 62500.0,
            "currency": "PKR",
            "is_available": True,
            "scraped_at": CAPTURE_TIME.isoformat(),
            "image_urls": ["/static/a07.jpg"],
        },
    )

    assert response.status_code == 422, response.text
