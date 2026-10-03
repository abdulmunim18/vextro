"""Regression tests for the smartphone price-synchronisation pipeline.

These cover the failures that let Daraz and PriceOye prices go stale inside
VEXTRO: an existing listing being re-matched from its title on every refresh,
a scrape without a rating resetting the stored review aggregate, flat
duplicate price-history rows, and newly discovered phones never entering the
catalog at all.
"""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.platform import Platform
from app.models.price_history import PriceHistory
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.raw_review import RawReview
from app.repositories.product_matching_repository import (
    ProductMatchCandidate,
)
from app.services.product_matching_service import _model_numbers_conflict


LISTINGS_ENDPOINT = "/api/v1/internal/acquisition/listings"
RESOLVE_ENDPOINT = "/api/v1/internal/acquisition/resolve-product"
MATCH_ENDPOINT = "/api/v1/internal/acquisition/match-product"
REVIEWS_ENDPOINT = "/api/v1/internal/acquisition/reviews"

TEST_INGESTION_KEY = "VextroSyncTestIngestionKey2026"

FIRST_CAPTURE = datetime(2026, 9, 1, 6, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def configure_ingestion_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Use a predictable ingestion key for every test in this module."""

    monkeypatch.setattr(
        settings,
        "ingestion_api_key",
        TEST_INGESTION_KEY,
    )


def headers() -> dict[str, str]:
    return {"X-Ingestion-Key": TEST_INGESTION_KEY}


def iso(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


@pytest.fixture
def sync_context(
    database_session: Session,
) -> Generator[dict[str, object], None, None]:
    """Create one catalog phone with a single 8GB/256GB Black variant."""

    token = uuid4().hex[:10]

    category_id = database_session.scalar(
        select(Category.id).where(Category.slug == "mobile-phones")
    )
    brand_id = database_session.scalar(
        select(Brand.id).where(Brand.slug == "samsung")
    )

    assert category_id is not None
    assert brand_id is not None

    product = CanonicalProduct(
        category_id=category_id,
        brand_id=brand_id,
        name=f"Samsung Sync Phone {token}",
        slug=f"samsung-sync-phone-{token}",
        model=f"Sync Phone {token}",
        specifications={"ram": "8GB", "storage_capacity": "256GB"},
        is_active=True,
    )
    database_session.add(product)
    database_session.flush()

    variant = ProductVariant(
        canonical_product_id=product.id,
        ram_gb=8,
        storage_gb=256,
        color="Black",
        condition="new",
        variant_attributes={},
        is_active=True,
    )
    database_session.add(variant)
    database_session.commit()

    context = {
        "token": token,
        "product_id": product.id,
        "variant_id": variant.id,
        "product_name": product.name,
        "external_id": f"SYNC-{token}",
    }

    yield context

    _cleanup_products(database_session, [product.id])


def _cleanup_products(
    database_session: Session,
    product_ids: list[int],
) -> None:
    """Remove the products a test created, children first."""

    database_session.rollback()

    variant_ids = list(
        database_session.scalars(
            select(ProductVariant.id).where(
                ProductVariant.canonical_product_id.in_(product_ids)
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

    for statement in (
        delete(RawReview).where(
            RawReview.product_listing_id.in_(listing_ids)
        )
        if listing_ids
        else None,
        delete(PriceHistory).where(
            PriceHistory.listing_id.in_(listing_ids)
        )
        if listing_ids
        else None,
        delete(ProductListing).where(ProductListing.id.in_(listing_ids))
        if listing_ids
        else None,
        delete(ProductVariant).where(ProductVariant.id.in_(variant_ids))
        if variant_ids
        else None,
        delete(CanonicalProduct).where(
            CanonicalProduct.id.in_(product_ids)
        ),
    ):
        if statement is None:
            continue

        database_session.execute(
            statement.execution_options(synchronize_session=False)
        )

    database_session.commit()


def listing_payload(
    context: dict[str, object],
    *,
    current_price: float,
    captured_at: datetime,
    platform_code: str = "daraz",
    **overrides: object,
) -> dict[str, object]:
    """Build a normalized listing capture for one platform."""

    token = str(context["token"])

    payload: dict[str, object] = {
        "platform_code": platform_code,
        "product_variant_id": int(context["variant_id"]),
        "external_id": f"{platform_code}-{context['external_id']}",
        "title": f"Samsung Sync Phone {token} 8GB 256GB Black",
        "product_url": (
            f"https://www.{platform_code}.pk/products/sync-{token}"
        ),
        "current_price": current_price,
        "currency": "PKR",
        "is_available": True,
        "scraped_at": iso(captured_at),
        "raw_payload": {"source": platform_code},
    }
    payload.update(overrides)

    return payload


def ingest(
    client: TestClient,
    payload: dict[str, object],
) -> dict[str, object]:
    """Deliver one listing capture and return the parsed response."""

    response = client.post(
        LISTINGS_ENDPOINT,
        headers=headers(),
        json=payload,
    )

    assert response.status_code in {200, 201}, response.text

    return response.json()


def read_listings(
    client: TestClient,
    product_id: int,
) -> list[dict[str, object]]:
    """Read the public product-detail listings the frontend renders."""

    response = client.get(f"/api/v1/products/{product_id}/listings")

    assert response.status_code == 200, response.text

    return response.json()["items"]


# --------------------------------------------------------------------------
# Part 1 - current price synchronisation
# --------------------------------------------------------------------------


def test_existing_listing_refreshes_to_the_latest_price(
    client: TestClient,
    database_session: Session,
    sync_context: dict[str, object],
) -> None:
    """A cheaper second scrape updates the same listing, in place."""

    first = ingest(
        client,
        listing_payload(
            sync_context,
            current_price=120000.0,
            captured_at=FIRST_CAPTURE,
        ),
    )
    second = ingest(
        client,
        listing_payload(
            sync_context,
            current_price=115000.0,
            captured_at=FIRST_CAPTURE + timedelta(hours=12),
        ),
    )

    assert first["status"] == "created"
    assert second["status"] == "updated"
    assert second["listing_id"] == first["listing_id"]
    assert second["price_changed"] is True
    assert Decimal(str(second["previous_price"])) == Decimal("120000.00")

    database_session.expire_all()
    listing = database_session.get(ProductListing, first["listing_id"])

    assert listing is not None
    assert listing.current_price == Decimal("115000.00")
    assert listing.last_seen_at == FIRST_CAPTURE + timedelta(hours=12)

    # No duplicate listing was created for the new price.
    assert (
        database_session.scalar(
            select(func.count(ProductListing.id)).where(
                ProductListing.product_variant_id
                == int(sync_context["variant_id"])
            )
        )
        == 1
    )

    # The price history now carries both observations.
    assert (
        database_session.scalar(
            select(func.count(PriceHistory.id)).where(
                PriceHistory.listing_id == first["listing_id"]
            )
        )
        == 2
    )


@pytest.mark.parametrize("platform_code", ["daraz", "priceoye"])
def test_api_returns_the_latest_marketplace_price(
    client: TestClient,
    sync_context: dict[str, object],
    platform_code: str,
) -> None:
    """The product page reads the freshest listing price, not the first."""

    ingest(
        client,
        listing_payload(
            sync_context,
            current_price=119999.0,
            captured_at=FIRST_CAPTURE,
            platform_code=platform_code,
        ),
    )
    ingest(
        client,
        listing_payload(
            sync_context,
            current_price=114999.0,
            captured_at=FIRST_CAPTURE + timedelta(hours=12),
            platform_code=platform_code,
        ),
    )

    items = read_listings(client, int(sync_context["product_id"]))
    listings = [
        item
        for item in items
        if item["external_id"].startswith(platform_code)
    ]

    assert len(listings) == 1
    assert Decimal(listings[0]["current_price"]) == Decimal("114999.00")
    assert listings[0]["updated_at"] is not None


def test_a_scrape_without_optional_fields_keeps_stored_values(
    client: TestClient,
    database_session: Session,
    sync_context: dict[str, object],
) -> None:
    """A thinner scrape must not blank data VEXTRO already holds."""

    created = ingest(
        client,
        listing_payload(
            sync_context,
            current_price=120000.0,
            captured_at=FIRST_CAPTURE,
            original_price=132000.0,
            rating=4.6,
            review_count=210,
            warranty="1 Year Brand Warranty",
        ),
    )

    # The same listing, re-scraped by a parser that read only the price.
    ingest(
        client,
        listing_payload(
            sync_context,
            current_price=118000.0,
            captured_at=FIRST_CAPTURE + timedelta(hours=12),
        ),
    )

    database_session.expire_all()
    listing = database_session.get(ProductListing, created["listing_id"])

    assert listing is not None
    assert listing.current_price == Decimal("118000.00")
    assert listing.original_price == Decimal("132000.00")
    assert listing.rating == Decimal("4.60")
    assert listing.review_count == 210
    assert listing.warranty == "1 Year Brand Warranty"


def test_a_stale_list_price_below_the_selling_price_is_dropped(
    client: TestClient,
    database_session: Session,
    sync_context: dict[str, object],
) -> None:
    """A list price the selling price overtook must not fake a discount."""

    created = ingest(
        client,
        listing_payload(
            sync_context,
            current_price=100000.0,
            captured_at=FIRST_CAPTURE,
            original_price=110000.0,
        ),
    )
    ingest(
        client,
        listing_payload(
            sync_context,
            current_price=125000.0,
            captured_at=FIRST_CAPTURE + timedelta(hours=12),
        ),
    )

    database_session.expire_all()
    listing = database_session.get(ProductListing, created["listing_id"])

    assert listing is not None
    assert listing.original_price is None


# --------------------------------------------------------------------------
# Part 4 - price history
# --------------------------------------------------------------------------


def test_repeating_the_same_price_does_not_duplicate_history(
    client: TestClient,
    database_session: Session,
    sync_context: dict[str, object],
) -> None:
    """An unchanged price extends its observation instead of cloning it."""

    created = ingest(
        client,
        listing_payload(
            sync_context,
            current_price=115000.0,
            captured_at=FIRST_CAPTURE,
        ),
    )
    repeated = ingest(
        client,
        listing_payload(
            sync_context,
            current_price=115000.0,
            captured_at=FIRST_CAPTURE + timedelta(hours=12),
        ),
    )

    assert created["price_history_created"] is True
    assert repeated["price_history_created"] is False
    assert repeated["price_changed"] is False
    assert repeated["price_history_id"] == created["price_history_id"]

    database_session.expire_all()
    points = list(
        database_session.scalars(
            select(PriceHistory)
            .where(PriceHistory.listing_id == created["listing_id"])
            .order_by(PriceHistory.captured_at.asc())
        )
    )

    assert len(points) == 1
    assert points[0].captured_at == FIRST_CAPTURE + timedelta(hours=12)


def test_price_progression_is_recorded_point_by_point(
    client: TestClient,
    sync_context: dict[str, object],
) -> None:
    """120k, 118k, 118k, 115k yields three points and a 115k current price."""

    for offset, price in enumerate(
        (120000.0, 118000.0, 118000.0, 115000.0)
    ):
        ingest(
            client,
            listing_payload(
                sync_context,
                current_price=price,
                captured_at=FIRST_CAPTURE + timedelta(hours=12 * offset),
            ),
        )

    response = client.get(
        f"/api/v1/products/{sync_context['product_id']}/price-history"
    )

    assert response.status_code == 200, response.text

    listing_history = response.json()["listings"][0]
    prices = [Decimal(point["price"]) for point in listing_history["points"]]

    assert prices == [
        Decimal("120000.00"),
        Decimal("118000.00"),
        Decimal("115000.00"),
    ]
    assert Decimal(
        listing_history["summary"]["current_price"]
    ) == Decimal("115000.00")
    assert Decimal(
        listing_history["summary"]["lowest_price"]
    ) == Decimal("115000.00")


# --------------------------------------------------------------------------
# Part 23/24 - marketplace identity
# --------------------------------------------------------------------------


def test_each_marketplace_keeps_its_own_price_and_history(
    client: TestClient,
    sync_context: dict[str, object],
) -> None:
    """Daraz and PriceOye share a product but never share an offer."""

    ingest(
        client,
        listing_payload(
            sync_context,
            current_price=119999.0,
            captured_at=FIRST_CAPTURE,
            platform_code="daraz",
        ),
    )
    ingest(
        client,
        listing_payload(
            sync_context,
            current_price=113500.0,
            captured_at=FIRST_CAPTURE,
            platform_code="priceoye",
        ),
    )
    # A later Daraz move must not touch the PriceOye offer.
    ingest(
        client,
        listing_payload(
            sync_context,
            current_price=109999.0,
            captured_at=FIRST_CAPTURE + timedelta(hours=12),
            platform_code="daraz",
        ),
    )

    prices = {
        item["external_id"].split("-", 1)[0]: Decimal(item["current_price"])
        for item in read_listings(client, int(sync_context["product_id"]))
    }

    assert prices == {
        "daraz": Decimal("109999.00"),
        "priceoye": Decimal("113500.00"),
    }

    history = client.get(
        f"/api/v1/products/{sync_context['product_id']}/price-history"
    ).json()

    assert history["total_listings"] == 2
    point_counts = sorted(
        len(listing["points"]) for listing in history["listings"]
    )
    assert point_counts == [1, 2]


# --------------------------------------------------------------------------
# Part 10/12 - matching
# --------------------------------------------------------------------------


def resolve(
    client: TestClient,
    **payload: object,
) -> dict[str, object]:
    """Resolve one scraped product through the crawler's own endpoint."""

    response = client.post(
        RESOLVE_ENDPOINT,
        headers=headers(),
        json=payload,
    )

    assert response.status_code == 200, response.text

    return response.json()


def test_an_existing_listing_resolves_by_its_marketplace_id(
    client: TestClient,
    sync_context: dict[str, object],
) -> None:
    """A known listing reuses its mapping even when the title turns vague.

    This is the stale-price root cause: catalog growth made title matching
    ambiguous, the item was rejected before the listing update ran, and the
    price froze. The marketplace's own ID settles the question instead.
    """

    created = ingest(
        client,
        listing_payload(
            sync_context,
            current_price=120000.0,
            captured_at=FIRST_CAPTURE,
        ),
    )
    external_id = f"daraz-{sync_context['external_id']}"

    result = resolve(
        client,
        platform_code="daraz",
        external_id=external_id,
        title="Phone",
        allow_create=False,
    )

    assert result["matched"] is True
    assert result["match_tier"] == "EXACT"
    assert result["confidence"] == 100
    assert result["product_variant_id"] == int(sync_context["variant_id"])
    assert "Existing marketplace listing" in result["reason"]
    assert created["listing_id"] is not None


def test_sibling_variants_no_longer_block_a_product_match(
    client: TestClient,
    database_session: Session,
    sync_context: dict[str, object],
) -> None:
    """Two colours of one phone are not a dangerous ambiguity."""

    sibling = ProductVariant(
        canonical_product_id=int(sync_context["product_id"]),
        ram_gb=8,
        storage_gb=256,
        color="Blue",
        condition="new",
        variant_attributes={},
        is_active=True,
    )
    database_session.add(sibling)
    database_session.commit()

    result = resolve(
        client,
        title=f"Samsung Sync Phone {sync_context['token']} 8GB 256GB",
        brand="Samsung",
        allow_create=False,
    )

    assert result["matched"] is True
    assert result["canonical_product_id"] == int(
        sync_context["product_id"]
    )
    assert result["product_variant_id"] in {
        int(sync_context["variant_id"]),
        sibling.id,
    }


def test_a_different_brand_never_matches(
    client: TestClient,
    sync_context: dict[str, object],
) -> None:
    """A conflicting manufacturer eliminates a candidate outright."""

    response = client.post(
        MATCH_ENDPOINT,
        headers=headers(),
        json={
            "title": f"Oppo Sync Phone {sync_context['token']} 8GB 256GB",
            "brand": "Oppo",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["matched"] is False
    assert body["canonical_product_id"] is None


def test_a_conflicting_memory_configuration_never_matches(
    client: TestClient,
    sync_context: dict[str, object],
) -> None:
    """8/128 must not be filed under the 8/256 variant."""

    response = client.post(
        MATCH_ENDPOINT,
        headers=headers(),
        json={
            "title": (
                f"Samsung Sync Phone {sync_context['token']} "
                "8GB RAM 128GB ROM"
            ),
            "brand": "Samsung",
            "ram_gb": 8,
            "storage_gb": 128,
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["matched"] is False


# --------------------------------------------------------------------------
# Part 9/11/13 - discovery
# --------------------------------------------------------------------------


@pytest.fixture
def discovered_products(
    database_session: Session,
) -> Generator[list[int], None, None]:
    """Track canonical products a discovery test creates, then remove them."""

    created: list[int] = []

    yield created

    if created:
        _cleanup_products(database_session, created)


def discover(
    client: TestClient,
    discovered_products: list[int],
    **payload: object,
) -> dict[str, object]:
    """Resolve a payload with creation enabled and track what it creates."""

    result = resolve(client, **payload)

    if result.get("canonical_product_id"):
        product_id = int(result["canonical_product_id"])
        if product_id not in discovered_products:
            discovered_products.append(product_id)

    return result


def test_a_new_marketplace_phone_is_registered(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],
) -> None:
    """Case C: an unknown phone becomes a product, variant and specs."""

    token = uuid4().hex[:8]
    result = discover(
        client,
        discovered_products,
        platform_code="daraz",
        external_id=f"DISCOVERY-{token}",
        title=(
            f"Infinix Discovery {token} - 8GB RAM 256GB ROM "
            "5000mAh Battery"
        ),
        brand="Infinix",
        specifications={
            "ram": "8 GB",
            "internal_memory": "256GB",
            "battery": "5000 mAh",
        },
    )

    assert result["matched"] is True
    assert result["product_created"] is True
    assert result["variant_created"] is True
    assert result["match_tier"] == "EXACT"

    product = database_session.get(
        CanonicalProduct,
        int(result["canonical_product_id"]),
    )
    variant = database_session.get(
        ProductVariant,
        int(result["product_variant_id"]),
    )

    assert product is not None
    assert variant is not None
    assert variant.ram_gb == 8
    assert variant.storage_gb == 256

    # "8 GB" and "256GB" normalize to one display form.
    assert product.specifications["ram"] == "8GB"
    assert product.specifications["storage_capacity"] == "256GB"
    assert product.specifications["battery_capacity"] == "5000 mAh"


def test_a_new_configuration_becomes_a_variant_not_a_product(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],
) -> None:
    """Case B: a second memory option joins the phone it belongs to."""

    token = uuid4().hex[:8]
    base = dict(
        platform_code="daraz",
        title=f"Realme Discovery {token}",
        brand="Realme",
    )

    first = discover(
        client,
        discovered_products,
        external_id=f"DISCOVERY-{token}-A",
        specifications={"ram": "8GB", "storage_capacity": "128GB"},
        **base,
    )
    second = discover(
        client,
        discovered_products,
        external_id=f"DISCOVERY-{token}-B",
        specifications={"ram": "8GB", "storage_capacity": "256GB"},
        **base,
    )

    assert first["product_created"] is True
    assert second["product_created"] is False
    assert second["variant_created"] is True
    assert (
        second["canonical_product_id"] == first["canonical_product_id"]
    )
    assert second["product_variant_id"] != first["product_variant_id"]

    variants = list(
        database_session.scalars(
            select(ProductVariant).where(
                ProductVariant.canonical_product_id
                == int(first["canonical_product_id"])
            )
        )
    )

    assert sorted(variant.storage_gb for variant in variants) == [128, 256]


def test_colours_stay_variants_of_one_product(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],
) -> None:
    """Blue and Black are the same phone, recorded as two variants."""

    token = uuid4().hex[:8]
    base = dict(
        platform_code="daraz",
        title=f"Vivo Discovery {token} 8GB 256GB",
        brand="Vivo",
        specifications={"ram": "8GB", "storage_capacity": "256GB"},
    )

    blue = discover(
        client,
        discovered_products,
        external_id=f"DISCOVERY-{token}-BLUE",
        color="Blue",
        **base,
    )
    black = discover(
        client,
        discovered_products,
        external_id=f"DISCOVERY-{token}-BLACK",
        color="Black",
        **base,
    )

    assert blue["canonical_product_id"] == black["canonical_product_id"]
    assert blue["product_variant_id"] != black["product_variant_id"]

    colours = sorted(
        database_session.scalars(
            select(ProductVariant.color).where(
                ProductVariant.canonical_product_id
                == int(blue["canonical_product_id"])
            )
        )
    )

    assert colours == ["Black", "Blue"]


def test_two_marketplaces_share_one_canonical_product(
    client: TestClient,
    discovered_products: list[int],
) -> None:
    """Daraz "8GB/256GB" and PriceOye "8/256" are the same phone."""

    token = uuid4().hex[:8]

    daraz = discover(
        client,
        discovered_products,
        platform_code="daraz",
        external_id=f"CROSS-{token}-DARAZ",
        title=f"Samsung Galaxy Cross{token} 8GB/256GB PTA Approved",
        brand="Samsung",
        specifications={"ram": "8GB", "storage_capacity": "256GB"},
    )
    priceoye = discover(
        client,
        discovered_products,
        platform_code="priceoye",
        external_id=f"CROSS-{token}-PRICEOYE",
        title=f"Samsung Galaxy Cross{token} 8/256",
        brand="Samsung",
        specifications={"ram": "8GB", "storage_capacity": "256GB"},
    )

    assert daraz["canonical_product_id"] == (
        priceoye["canonical_product_id"]
    )


def test_two_different_models_are_never_merged(
    client: TestClient,
    discovered_products: list[int],
) -> None:
    """An A55 and an A35 stay separate products."""

    token = uuid4().hex[:8]

    a55 = discover(
        client,
        discovered_products,
        platform_code="daraz",
        external_id=f"MODELS-{token}-A55",
        title=f"Samsung Galaxy A55x{token} 8GB 256GB",
        brand="Samsung",
        specifications={"ram": "8GB", "storage_capacity": "256GB"},
    )
    a35 = discover(
        client,
        discovered_products,
        platform_code="daraz",
        external_id=f"MODELS-{token}-A35",
        title=f"Samsung Galaxy A35x{token} 8GB 256GB",
        brand="Samsung",
        specifications={"ram": "8GB", "storage_capacity": "256GB"},
    )

    assert a55["canonical_product_id"] != a35["canonical_product_id"]


def test_a_vague_title_is_still_queued_for_review(
    client: TestClient,
    discovered_products: list[int],
) -> None:
    """Creation needs a real brand and model, never a bare title."""

    result = discover(
        client,
        discovered_products,
        platform_code="daraz",
        external_id=f"VAGUE-{uuid4().hex[:8]}",
        title="Mobile Phone",
    )

    assert result["matched"] is False
    assert result["product_created"] is False


# --------------------------------------------------------------------------
# Part 6/7 - reviews
# --------------------------------------------------------------------------


def review(
    *,
    external_review_id: str | None,
    rating: int = 5,
    text: str = "Fast delivery and the phone is original.",
    reviewed_at: str = "2026-09-20T00:00:00Z",
) -> dict[str, object]:
    return {
        "external_review_id": external_review_id,
        "reviewer_display_name": "Bushra",
        "rating": rating,
        "review_text": text,
        "reviewed_at": reviewed_at,
        "verified_purchase": True,
    }


def test_reviews_reach_an_existing_listing_and_never_duplicate(
    client: TestClient,
    database_session: Session,
    sync_context: dict[str, object],
) -> None:
    """Existing listings collect new reviews and keep the old ones."""

    created = ingest(
        client,
        listing_payload(
            sync_context,
            current_price=120000.0,
            captured_at=FIRST_CAPTURE,
        ),
    )
    external_id = f"daraz-{sync_context['external_id']}"
    source_url = f"https://www.daraz.pk/products/sync-{sync_context['token']}"

    first = client.post(
        REVIEWS_ENDPOINT,
        headers=headers(),
        json={
            "platform_code": "daraz",
            "external_listing_id": external_id,
            "source_url": source_url,
            "reviews": [review(external_review_id="daraz-review-1")],
        },
    )

    assert first.status_code == 200, first.text
    assert first.json()["created_count"] == 1

    # The same review again, plus one genuinely new review.
    second = client.post(
        REVIEWS_ENDPOINT,
        headers=headers(),
        json={
            "platform_code": "daraz",
            "external_listing_id": external_id,
            "source_url": source_url,
            "reviews": [
                review(external_review_id="daraz-review-1"),
                review(
                    external_review_id="daraz-review-2",
                    rating=4,
                    text="Good value, packaging could be better.",
                ),
            ],
        },
    )

    assert second.status_code == 200, second.text
    body = second.json()

    assert body["created_count"] == 1
    assert body["duplicate_count"] == 1

    database_session.expire_all()
    stored = list(
        database_session.scalars(
            select(RawReview).where(
                RawReview.product_listing_id == created["listing_id"]
            )
        )
    )

    assert len(stored) == 2

    listing = database_session.get(ProductListing, created["listing_id"])
    assert listing is not None
    assert listing.review_count == 2
    assert listing.rating == Decimal("4.50")


def test_a_later_scrape_keeps_the_review_aggregate(
    client: TestClient,
    database_session: Session,
    sync_context: dict[str, object],
) -> None:
    """A price refresh must not reset rating and review_count to empty.

    The scraper's listing payload carries the marketplace's own aggregate,
    which is often absent. Overwriting the stored aggregate with it is what
    left listings showing no reviews despite holding real ones.
    """

    created = ingest(
        client,
        listing_payload(
            sync_context,
            current_price=120000.0,
            captured_at=FIRST_CAPTURE,
        ),
    )
    external_id = f"daraz-{sync_context['external_id']}"

    client.post(
        REVIEWS_ENDPOINT,
        headers=headers(),
        json={
            "platform_code": "daraz",
            "external_listing_id": external_id,
            "source_url": (
                f"https://www.daraz.pk/products/sync-"
                f"{sync_context['token']}"
            ),
            "reviews": [review(external_review_id="daraz-review-9")],
        },
    )

    ingest(
        client,
        listing_payload(
            sync_context,
            current_price=118000.0,
            captured_at=FIRST_CAPTURE + timedelta(hours=12),
        ),
    )

    database_session.expire_all()
    listing = database_session.get(ProductListing, created["listing_id"])

    assert listing is not None
    assert listing.current_price == Decimal("118000.00")
    assert listing.review_count == 1
    assert listing.rating == Decimal("5.00")


def test_review_ingestion_rejects_an_unknown_listing(
    client: TestClient,
) -> None:
    """Reviews for a listing VEXTRO has never seen are refused, not guessed."""

    response = client.post(
        REVIEWS_ENDPOINT,
        headers=headers(),
        json={
            "platform_code": "daraz",
            "external_listing_id": f"UNKNOWN-{uuid4().hex[:8]}",
            "source_url": "https://www.daraz.pk/products/unknown.html",
            "reviews": [review(external_review_id="x-1")],
        },
    )

    assert response.status_code == 404


def test_every_platform_is_registered_for_acquisition(
    database_session: Session,
) -> None:
    """Both in-scope marketplaces exist and are active."""

    codes = set(
        database_session.scalars(
            select(Platform.code).where(Platform.is_active.is_(True))
        )
    )

    assert {"daraz", "priceoye"} <= codes

# --------------------------------------------------------------------------
# Part 10 - the model-code veto, against real catalog data
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scraped_title", "product_name", "product_model", "conflicts"),
    [
        # These three are false merges found in the development database:
        # Camon 50 listings had been filed under the Camon 30, and an
        # iPhone 16 under the iPhone 15, purely on title similarity.
        (
            "Tecno Camon 50 Pro = 8GB RAM = 256GB ROM = 6500mAh BATTERY",
            "Tecno Camon 30",
            "CL6",
            True,
        ),
        (
            "Tecno Camon 50 - 6.78 Inches Display - 8GB RAM 256GB ROM",
            "Tecno Camon 30",
            "CL6",
            True,
        ),
        ("Apple iPhone 16 - 128GB", "Apple iPhone 15", "A3090", True),
        ("Samsung Galaxy A35 8GB 256GB", "Samsung Galaxy A55 5G", "SM-A556E", True),
        ("Realme C110i 6GB/128GB", "Realme C100i", "Realme C100i", True),
        (
            "Samsung Galaxy S24 Ultra 12GB 256GB",
            "Samsung Galaxy S25 Ultra",
            "Samsung Galaxy S25 Ultra",
            True,
        ),
        # A shorter marketing code prefixing the catalog's full code is the
        # same phone written at different precision.
        (
            "Samsung Galaxy A55 5G 8GB/256GB PTA Approved",
            "Samsung Galaxy A55 5G",
            "SM-A556E",
            False,
        ),
        (
            "Infinix Note 60 Pro (8GB-256GB)",
            "Infinix Note 60 Pro",
            "Infinix Note 60 Pro",
            False,
        ),
        ("Realme C100i 6GB/128GB", "Realme C100i", "Realme C100i", False),
        # No model code on one side is not evidence of a conflict.
        ("Mobile Phone", "Samsung Galaxy A55 5G", "SM-A556E", False),
    ],
)
def test_model_codes_veto_only_genuine_conflicts(
    scraped_title: str,
    product_name: str,
    product_model: str,
    conflicts: bool,
) -> None:
    """A differing model code eliminates a candidate; a vaguer one does not."""

    candidate = ProductMatchCandidate(
        canonical_product_id=1,
        product_variant_id=1,
        product_name=product_name,
        brand_name=None,
        model=product_model,
        sku=None,
        ram_gb=8,
        storage_gb=256,
        color=None,
        condition="new",
    )

    assert _model_numbers_conflict(scraped_title, candidate) is conflicts
