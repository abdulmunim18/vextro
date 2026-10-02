"""Accuracy guarantees for marketplace data shown to shoppers.

Covers the behaviours that keep the catalog honest across crawls:
look-alike models never merge, a known marketplace id keeps its
mapping, structured sources can add new phones, variant-level ids
inherit the history of the product-level row they replace, and a
complete crawl retires offers the marketplace no longer lists.
"""

from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.platform import Platform
from app.models.price_history import PriceHistory
from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.scrape_error import ScrapeError
from app.models.scrape_run import ScrapeRun
from app.services.product_matching_service import (
    MIN_COLOR_IDENTITY_SCORE,
    _color_similarity,
    _model_identity_conflict,
)
from app.services.review_normalization import build_review_fingerprint


LISTINGS_ENDPOINT = "/api/v1/internal/acquisition/listings"
MATCH_ENDPOINT = "/api/v1/internal/acquisition/match-product"
RUNS_ENDPOINT = "/api/v1/internal/acquisition/runs"
TEST_INGESTION_KEY = "VextroAccuracyTestKey2026Secure"


@pytest.fixture(autouse=True)
def configure_ingestion_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "ingestion_api_key", TEST_INGESTION_KEY)


def headers() -> dict[str, str]:
    return {"X-Ingestion-Key": TEST_INGESTION_KEY}


@pytest.fixture
def catalog(
    database_session: Session,
) -> Generator[dict[str, object], None, None]:
    """Provide an isolated brand namespace and clean it up afterwards."""

    token = uuid4().hex[:8]
    brand = Brand(
        name=f"Zeta{token}",
        slug=f"zeta{token}",
        is_active=True,
    )
    database_session.add(brand)
    database_session.commit()

    yield {"token": token, "brand": brand}

    database_session.rollback()
    brand_ids = list(
        database_session.scalars(
            select(Brand.id).where(Brand.name.ilike(f"%{token}%"))
        )
    )
    product_ids = list(
        database_session.scalars(
            select(CanonicalProduct.id).where(
                CanonicalProduct.brand_id.in_(brand_ids)
            )
        )
    )
    variant_ids = list(
        database_session.scalars(
            select(ProductVariant.id).where(
                ProductVariant.canonical_product_id.in_(product_ids)
            )
        )
    )
    listing_ids = list(
        database_session.scalars(
            select(ProductListing.id).where(
                ProductListing.product_variant_id.in_(variant_ids)
            )
        )
    )
    for statement in (
        delete(PriceHistory).where(PriceHistory.listing_id.in_(listing_ids)),
        delete(ProductImage).where(ProductImage.listing_id.in_(listing_ids)),
        delete(ProductImage).where(
            ProductImage.canonical_product_id.in_(product_ids)
        ),
        delete(ProductListing).where(ProductListing.id.in_(listing_ids)),
        delete(ProductVariant).where(ProductVariant.id.in_(variant_ids)),
        delete(CanonicalProduct).where(CanonicalProduct.id.in_(product_ids)),
        delete(Brand).where(Brand.id.in_(brand_ids)),
    ):
        database_session.execute(
            statement.execution_options(synchronize_session=False)
        )
    database_session.commit()


def add_product(
    database_session: Session,
    catalog: dict[str, object],
    name: str,
    *,
    color: str | None = None,
    ram_gb: int | None = None,
    storage_gb: int | None = None,
) -> tuple[CanonicalProduct, ProductVariant]:
    category = database_session.scalar(
        select(Category).where(Category.slug == "mobile-phones")
    )
    assert category is not None
    brand = catalog["brand"]
    product = CanonicalProduct(
        category_id=category.id,
        brand_id=brand.id,
        name=name,
        slug=f"accuracy-{uuid4().hex[:12]}",
        model=name[:120],
        specifications={},
        is_active=True,
    )
    database_session.add(product)
    database_session.flush()
    variant = ProductVariant(
        canonical_product_id=product.id,
        ram_gb=ram_gb,
        storage_gb=storage_gb,
        color=color,
        condition="new",
        variant_attributes={},
        is_active=True,
    )
    database_session.add(variant)
    database_session.commit()
    return product, variant


def listing_payload(
    variant_id: int,
    external_id: str,
    *,
    price: float,
    captured_at: datetime,
    platform_code: str = "priceoye",
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "platform_code": platform_code,
        "product_variant_id": variant_id,
        "external_id": external_id,
        "title": "Accuracy Test Listing",
        "product_url": "https://priceoye.pk/mobiles/test/accuracy",
        "current_price": price,
        "currency": "PKR",
        "is_available": True,
        "scraped_at": captured_at.isoformat(),
        "raw_payload": {},
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------
# Model identity
# --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "catalog_name"),
    [
        ("Apple iPhone 17 White", "Apple Iphone 17 Air"),
        ("Apple iPhone 17 Pro Max 256GB", "Apple Iphone 17"),
        ("Apple iPhone 17", "Apple Iphone 17e"),
        ("Infinix Hot 60i", "Infinix Hot 60"),
        ("Samsung Galaxy S25", "Samsung Galaxy S25 Ultra"),
        ("Xiaomi Redmi Note 14", "Xiaomi Redmi 14"),
    ],
)
def test_lookalike_models_are_reported_as_conflicts(
    title: str,
    catalog_name: str,
) -> None:
    assert _model_identity_conflict(title, catalog_name) is not None


@pytest.mark.parametrize(
    ("title", "catalog_name"),
    [
        (
            "Infinix GT 50 Pro - 6.78 Inches Display - 12GB RAM 256GB "
            "ROM - 13MP Front Camera - 50MP+8MP Rear Camera",
            "Infinix GT 50 Pro",
        ),
        # Sellers routinely drop the network edition from a title.
        ("Samsung Galaxy A56 8/256GB - PTA APPROVED", "Samsung Galaxy A56 5G"),
        ("Infinix Hot60 Pro 8GB 256GB", "Infinix Hot 60 Pro"),
        # A qualifier word in the descriptive tail is not the model.
        ("Tecno Spark 40 - 50MP Pro Camera - 5000mAh", "Tecno Spark 40"),
    ],
)
def test_same_model_titles_are_not_flagged(
    title: str,
    catalog_name: str,
) -> None:
    assert _model_identity_conflict(title, catalog_name) is None


def test_network_edition_must_agree_for_structured_sources() -> None:
    assert (
        _model_identity_conflict(
            "Xiaomi Redmi 15C",
            "Xiaomi Redmi 15C 5G",
            strict_network=True,
        )
        is not None
    )
    assert (
        _model_identity_conflict(
            "Xiaomi Redmi 15C 5G",
            "Xiaomi Redmi 15C 5G",
            strict_network=True,
        )
        is None
    )


def test_colour_similarity_separates_shared_prefix_colours() -> None:
    assert (
        _color_similarity("Titanium Blue", "Titanium Black")
        < MIN_COLOR_IDENTITY_SCORE
    )
    assert _color_similarity("Awesome Black", "Black") == 1.0
    assert _color_similarity("Grey", "Gray") >= MIN_COLOR_IDENTITY_SCORE
    assert _color_similarity("Sage", "Lavender") < MIN_COLOR_IDENTITY_SCORE


def test_new_colour_lands_on_its_own_model_not_a_lookalike(
    client: TestClient,
    database_session: Session,
    catalog: dict[str, object],
) -> None:
    """'<phone> White' must not be absorbed by '<phone> Air (Cloud White)'."""

    token = catalog["token"]
    base, _ = add_product(
        database_session, catalog, f"Zeta {token} 17", color="Black",
    )
    air, air_variant = add_product(
        database_session, catalog, f"Zeta {token} 17 Air",
        color="Cloud White",
    )

    response = client.post(
        MATCH_ENDPOINT,
        headers=headers(),
        json={
            "title": f"Zeta {token} 17",
            "brand": f"Zeta{token}",
            "color": "White",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["matched"] is True
    assert body["canonical_product_id"] == base.id
    assert body["canonical_product_id"] != air.id
    assert body["product_variant_id"] != air_variant.id
    assert body["color"] == "White"


def test_pro_listing_is_not_matched_to_the_base_model(
    client: TestClient,
    database_session: Session,
    catalog: dict[str, object],
) -> None:
    token = catalog["token"]
    add_product(database_session, catalog, f"Zeta {token} 17")

    response = client.post(
        MATCH_ENDPOINT,
        headers=headers(),
        json={
            "title": f"Zeta {token} 17 Pro 8GB 256GB",
            "brand": f"Zeta{token}",
        },
    )
    body = response.json()

    assert body["matched"] is False
    assert "different model" in body["reason"].lower()


# --------------------------------------------------------------------
# Stable mapping and catalog growth
# --------------------------------------------------------------------


def test_known_marketplace_id_keeps_its_mapping(
    client: TestClient,
    database_session: Session,
    catalog: dict[str, object],
) -> None:
    """A re-crawled listing is refreshed even if its title turns vague."""

    token = catalog["token"]
    _, variant = add_product(
        database_session, catalog, f"Zeta {token} 30", ram_gb=8,
        storage_gb=256,
    )
    external_id = f"daraz-{token}"
    created = client.post(
        LISTINGS_ENDPOINT,
        headers=headers(),
        json=listing_payload(
            variant.id,
            external_id,
            price=50000,
            captured_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
            platform_code="daraz",
            product_url="https://www.daraz.pk/products/accuracy.html",
        ),
    )
    assert created.status_code == 201

    response = client.post(
        MATCH_ENDPOINT,
        headers=headers(),
        json={
            "platform_code": "daraz",
            "external_id": external_id,
            # Nothing in this title identifies the phone any more.
            "title": "Brand new smartphone best price PTA approved",
        },
    )
    body = response.json()

    assert body["matched"] is True
    assert body["product_variant_id"] == variant.id
    assert "existing marketplace listing" in body["reason"].lower()


def test_structured_source_adds_a_new_phone_and_its_configurations(
    client: TestClient,
    database_session: Session,
    catalog: dict[str, object],
) -> None:
    token = catalog["token"]
    brand_name = f"Zeta{token}"
    title = f"Zeta {token} X9"

    def match(color: str, storage: int, external_suffix: str) -> dict:
        response = client.post(
            MATCH_ENDPOINT,
            headers=headers(),
            json={
                "platform_code": "priceoye",
                "external_id": f"zeta-{token}-x9--{external_suffix}",
                "title": title,
                "brand": brand_name,
                "ram_gb": 8,
                "storage_gb": storage,
                "color": color,
                "allow_catalog_create": True,
                "specifications": {"Screen Size": "6.7 inches"},
            },
        )
        assert response.status_code == 200
        return response.json()

    first = match("Red", 128, "red--128gb-8gb-ram")
    assert first["matched"] is True
    assert first["product_name"] == title
    assert (first["ram_gb"], first["storage_gb"], first["color"]) == (
        8, 128, "Red",
    )

    blue = match("Blue", 128, "blue--128gb-8gb-ram")
    bigger = match("Red", 256, "red--256gb-8gb-ram")
    repeat = match("Red", 128, "red--128gb-8gb-ram")

    # Every configuration belongs to the one new product...
    product_ids = {
        first["canonical_product_id"],
        blue["canonical_product_id"],
        bigger["canonical_product_id"],
        repeat["canonical_product_id"],
    }
    assert len(product_ids) == 1
    # ...each on its own variant, and asking twice changes nothing.
    assert len(
        {
            first["product_variant_id"],
            blue["product_variant_id"],
            bigger["product_variant_id"],
        }
    ) == 3
    assert repeat["product_variant_id"] == first["product_variant_id"]
    assert bigger["storage_gb"] == 256

    product = database_session.get(
        CanonicalProduct, first["canonical_product_id"],
    )
    assert product is not None
    assert product.slug == f"priceoye-zeta-{token}-x9"
    assert product.specifications == {"Screen Size": "6.7 inches"}
    assert product.brand_id == catalog["brand"].id


def test_free_text_source_cannot_add_products(
    client: TestClient,
    catalog: dict[str, object],
) -> None:
    token = catalog["token"]

    response = client.post(
        MATCH_ENDPOINT,
        headers=headers(),
        json={
            "platform_code": "daraz",
            "external_id": f"unknown-{token}",
            "title": f"Zeta {token} Mystery 99",
            "brand": f"Zeta{token}",
        },
    )

    assert response.json()["matched"] is False


# --------------------------------------------------------------------
# Listing continuity
# --------------------------------------------------------------------


def test_variant_level_listing_inherits_the_product_level_row(
    client: TestClient,
    database_session: Session,
    catalog: dict[str, object],
) -> None:
    """Re-keying keeps price history instead of leaving a stale twin."""

    token = catalog["token"]
    _, variant = add_product(database_session, catalog, f"Zeta {token} 40")
    base_id = f"zeta-{token}-40"
    first_capture = datetime(2026, 9, 1, tzinfo=timezone.utc)

    legacy = client.post(
        LISTINGS_ENDPOINT,
        headers=headers(),
        json=listing_payload(
            variant.id, base_id, price=100000, captured_at=first_capture,
        ),
    ).json()
    assert legacy["status"] == "created"

    adopted = client.post(
        LISTINGS_ENDPOINT,
        headers=headers(),
        json=listing_payload(
            variant.id,
            f"{base_id}--black--256gb",
            price=110000,
            captured_at=first_capture + timedelta(days=30),
        ),
    ).json()
    assert adopted["status"] == "updated"
    assert adopted["listing_id"] == legacy["listing_id"]

    sibling = client.post(
        LISTINGS_ENDPOINT,
        headers=headers(),
        json=listing_payload(
            variant.id,
            f"{base_id}--blue--256gb",
            price=110000,
            captured_at=first_capture + timedelta(days=30),
        ),
    ).json()
    assert sibling["status"] == "created"
    assert sibling["listing_id"] != legacy["listing_id"]

    database_session.expire_all()
    listing = database_session.get(ProductListing, legacy["listing_id"])
    assert listing is not None
    assert listing.external_id == f"{base_id}--black--256gb"
    assert listing.current_price == Decimal("110000.00")
    history_points = database_session.scalar(
        select(func.count(PriceHistory.id)).where(
            PriceHistory.listing_id == listing.id,
        )
    )
    assert history_points == 2
    # No product-level twin is left behind.
    assert (
        database_session.scalar(
            select(ProductListing.id).where(
                ProductListing.external_id == base_id,
            )
        )
        is None
    )


def test_capture_stores_images_and_never_wipes_a_review_aggregate(
    client: TestClient,
    database_session: Session,
    catalog: dict[str, object],
) -> None:
    token = catalog["token"]
    product, variant = add_product(
        database_session, catalog, f"Zeta {token} 50",
    )
    external_id = f"zeta-{token}-50--black"
    images = [
        "https://images.priceoye.pk/zeta-a-500x500.webp",
        "https://images.priceoye.pk/zeta-b-500x500.webp",
    ]
    first_capture = datetime(2026, 9, 1, tzinfo=timezone.utc)

    created = client.post(
        LISTINGS_ENDPOINT,
        headers=headers(),
        json=listing_payload(
            variant.id,
            external_id,
            price=90000,
            captured_at=first_capture,
            rating=4.6,
            review_count=210,
            raw_payload={"image_urls": images},
        ),
    ).json()

    # A later capture that says nothing about reviews.
    client.post(
        LISTINGS_ENDPOINT,
        headers=headers(),
        json=listing_payload(
            variant.id,
            external_id,
            price=91000,
            captured_at=first_capture + timedelta(hours=12),
            raw_payload={"image_urls": images},
        ),
    )

    database_session.expire_all()
    listing = database_session.get(ProductListing, created["listing_id"])
    assert listing is not None
    assert listing.rating == Decimal("4.60")
    assert listing.review_count == 210

    listing_images = list(
        database_session.scalars(
            select(ProductImage)
            .where(ProductImage.listing_id == listing.id)
            .order_by(ProductImage.sort_order)
        )
    )
    assert [image.image_url for image in listing_images] == images
    assert [image.is_primary for image in listing_images] == [True, False]

    product_images = list(
        database_session.scalars(
            select(ProductImage.image_url).where(
                ProductImage.canonical_product_id == product.id,
            )
        )
    )
    # Seeded once from the first capture, not duplicated by the second.
    assert sorted(product_images) == sorted(images)


def test_review_identity_is_shared_by_every_variant_of_a_product() -> None:
    def fingerprint(listing_external_id: str) -> str:
        return build_review_fingerprint(
            platform_code="priceoye",
            listing_external_id=listing_external_id,
            external_review_id=None,
            reviewer_external_id=None,
            reviewer_display_name="Ali Anwar",
            rating=5,
            review_text="Good Product",
            reviewed_at=datetime(2026, 9, 21, tzinfo=timezone.utc),
        )

    assert fingerprint("sego-epicx") == fingerprint(
        "sego-epicx--stellar_blue--128gb-8gb-ram"
    )
    assert fingerprint("sego-epicx") != fingerprint("sego-epicy")


# --------------------------------------------------------------------
# Retiring offers the marketplace no longer lists
# --------------------------------------------------------------------


@pytest.fixture
def clean_runs(database_session: Session) -> Generator[None, None, None]:
    yield
    database_session.rollback()
    database_session.execute(delete(ScrapeError))
    database_session.execute(delete(ScrapeRun))
    database_session.commit()


def _retirement_setup(
    client: TestClient,
    database_session: Session,
    catalog: dict[str, object],
    *,
    stale_listings: int,
    refreshed_listings: int,
) -> tuple[int, list[int], list[int]]:
    """Create old listings, start a run, refresh some of them."""

    token = catalog["token"]
    _, variant = add_product(database_session, catalog, f"Zeta {token} 60")
    platform = database_session.scalar(
        select(Platform).where(Platform.code == "priceoye")
    )
    assert platform is not None

    # Leftover rows from other tests would skew the half-the-catalogue
    # guard, so park them as unavailable for this scenario.
    database_session.execute(
        update(ProductListing)
        .where(ProductListing.platform_id == platform.id)
        .values(is_available=False)
        .execution_options(synchronize_session=False)
    )
    database_session.commit()

    long_ago = datetime(2026, 8, 1, tzinfo=timezone.utc)
    total = stale_listings + refreshed_listings
    listing_ids = [
        client.post(
            LISTINGS_ENDPOINT,
            headers=headers(),
            json=listing_payload(
                variant.id,
                f"zeta-{token}-60--c{index}",
                price=70000,
                captured_at=long_ago,
            ),
        ).json()["listing_id"]
        for index in range(total)
    ]

    run = client.post(
        RUNS_ENDPOINT,
        headers=headers(),
        json={
            "platform": "priceoye",
            "spider_name": "priceoye_smartphones",
            "trigger_type": "test",
            "parser_version": "priceoye-test",
        },
    ).json()

    for index in range(refreshed_listings):
        client.post(
            LISTINGS_ENDPOINT,
            headers=headers(),
            json=listing_payload(
                variant.id,
                f"zeta-{token}-60--c{index}",
                price=71000,
                captured_at=datetime.now(timezone.utc)
                + timedelta(seconds=5),
            ),
        )

    return (
        run["id"],
        listing_ids[:refreshed_listings],
        listing_ids[refreshed_listings:],
    )


def _finish(client: TestClient, run_id: int, *, full_crawl: bool) -> None:
    response = client.patch(
        f"{RUNS_ENDPOINT}/{run_id}",
        headers=headers(),
        json={
            "crawl_succeeded": True,
            "full_crawl": full_crawl,
            "items_discovered": 5,
            "items_ingested": 5,
            "items_rejected": 0,
            "items_failed": 0,
            "error_count": 0,
        },
    )
    assert response.status_code == 200, response.text


def _availability(
    database_session: Session,
    listing_ids: list[int],
) -> list[bool]:
    database_session.expire_all()
    return [
        database_session.get(ProductListing, listing_id).is_available
        for listing_id in listing_ids
    ]


def test_full_crawl_retires_listings_it_did_not_see(
    client: TestClient,
    database_session: Session,
    catalog: dict[str, object],
    clean_runs: None,
) -> None:
    run_id, refreshed, unseen = _retirement_setup(
        client, database_session, catalog,
        stale_listings=1, refreshed_listings=2,
    )

    _finish(client, run_id, full_crawl=True)

    assert _availability(database_session, refreshed) == [True, True]
    assert _availability(database_session, unseen) == [False]


def test_capped_crawl_never_retires_listings(
    client: TestClient,
    database_session: Session,
    catalog: dict[str, object],
    clean_runs: None,
) -> None:
    run_id, _, unseen = _retirement_setup(
        client, database_session, catalog,
        stale_listings=1, refreshed_listings=2,
    )

    _finish(client, run_id, full_crawl=False)

    assert _availability(database_session, unseen) == [True]


def test_thin_crawl_is_treated_as_a_scraper_problem_not_a_stockout(
    client: TestClient,
    database_session: Session,
    catalog: dict[str, object],
    clean_runs: None,
) -> None:
    """Refreshing 1 listing while 3 go unseen means the crawl was blocked."""

    run_id, _, unseen = _retirement_setup(
        client, database_session, catalog,
        stale_listings=3, refreshed_listings=1,
    )

    _finish(client, run_id, full_crawl=True)

    assert _availability(database_session, unseen) == [True, True, True]


def test_successful_capture_clears_its_manual_review_entry(
    client: TestClient,
    database_session: Session,
    catalog: dict[str, object],
) -> None:
    """Ingesting an offer removes it from the administrator's queue."""

    from app.models.pending_product_match import PendingProductMatch

    token = catalog["token"]
    _, variant = add_product(database_session, catalog, f"Zeta {token} 70")
    product_level_id = f"zeta-{token}-70"

    def queue(external_id: str, status: str) -> None:
        database_session.add(
            PendingProductMatch(
                platform_code="priceoye",
                external_id=external_id,
                title=f"Zeta {token} 70",
                product_url="https://priceoye.pk/mobiles/test/accuracy",
                match_payload={},
                listing_payload={},
                match_confidence=50,
                match_reason="Parked by an earlier crawl.",
                status=status,
            )
        )

    queue(product_level_id, "pending")
    queue(f"zeta-{token}-other", "pending")
    database_session.commit()

    client.post(
        LISTINGS_ENDPOINT,
        headers=headers(),
        json=listing_payload(
            variant.id,
            f"{product_level_id}--black--128gb",
            price=45000,
            captured_at=datetime(2026, 10, 1, tzinfo=timezone.utc),
        ),
    )

    database_session.expire_all()
    remaining = set(
        database_session.scalars(
            select(PendingProductMatch.external_id).where(
                PendingProductMatch.external_id.like(f"zeta-{token}-%"),
            )
        )
    )
    # The answered entry is gone; an unrelated one is untouched.
    assert remaining == {f"zeta-{token}-other"}

    database_session.execute(
        delete(PendingProductMatch).where(
            PendingProductMatch.external_id.like(f"zeta-{token}-%"),
        )
    )
    database_session.commit()


def test_colourless_title_lands_on_the_phone_despite_colour_variants(
    client: TestClient,
    database_session: Session,
    catalog: dict[str, object],
) -> None:
    """Several colour variants must not push a known phone into review.

    A seller title without a colour ties between a phone's colour
    variants. They are all the same phone, so the listing belongs on
    that phone with its colour left unknown.
    """

    token = catalog["token"]
    product, black = add_product(
        database_session, catalog, f"Zeta {token} 80",
        color="Black", ram_gb=8, storage_gb=256,
    )
    white = ProductVariant(
        canonical_product_id=product.id,
        ram_gb=8,
        storage_gb=256,
        color="White",
        condition="new",
        variant_attributes={},
        is_active=True,
    )
    database_session.add(white)
    database_session.commit()

    response = client.post(
        MATCH_ENDPOINT,
        headers=headers(),
        json={
            "platform_code": "daraz",
            "external_id": f"daraz-colourless-{token}",
            "title": f"Zeta {token} 80 - 8GB RAM 256GB ROM - PTA Approved",
            "brand": f"Zeta{token}",
        },
    )
    body = response.json()

    assert body["matched"] is True
    assert body["canonical_product_id"] == product.id
    assert (body["ram_gb"], body["storage_gb"]) == (8, 256)
    assert body["color"] is None
    assert body["product_variant_id"] not in {black.id, white.id}


# --------------------------------------------------------------------
# Word-level product identity
# --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "catalog_name", "brand"),
    [
        # Each pair was merged by character similarity on a live crawl.
        ("Digit D1", "Digit Nova", "Digit"),
        ("QMobile QCrystal", "QMobile QHero", "QMobile"),
        ("Club Mobile Grace", "Club Mobile Super Hit", "Club Mobile"),
        ("Memobile Bouncer Pro", "Memobile iPower pro", "Memobile"),
        ("Calme C150i", "Calme iMax", "Calme"),
        ("E-Tachi i17 Pro Max", "Apple Iphone 17 Pro Max", "E-Tachi"),
        ("Sego Smart 20 HD", "Sego Smart 20", "Sego"),
        ("Itel It2165 Eco", "Itel It2165", "Itel"),
        ("Apple Iphone 17", "Apple Iphone 17 Air", "Apple"),
        ("Apple Iphone 17 Air", "Apple Iphone 17", "Apple"),
    ],
)
def test_clean_titles_only_match_the_identical_model(
    title: str,
    catalog_name: str,
    brand: str,
) -> None:
    from app.services.product_matching_service import _names_same_product

    assert (
        _names_same_product(title, catalog_name, (brand,), exact=True)
        is False
    )


@pytest.mark.parametrize(
    ("title", "catalog_name", "brand", "exact"),
    [
        ("Infinix GT 50 Pro", "Infinix GT 50 Pro", "Infinix", True),
        ("Samsung Galaxy A56 5G", "Samsung Galaxy A56 5G", "Samsung", True),
        ("Apple iPhone 17", "Apple Iphone 17", "Apple", True),
        (
            "Infinix GT 50 Pro - 6.78 Inches Display - 12GB RAM 256GB ROM",
            "Infinix GT 50 Pro",
            "Infinix",
            False,
        ),
        # Seller dropped the brand marker and ran the model together.
        ("Galaxy A56 8/256GB PTA Approved", "Samsung Galaxy A56 5G", "Samsung", False),
        ("Infinix Hot60 Pro 8GB 256GB", "Infinix Hot 60 Pro", "Infinix", False),
    ],
)
def test_titles_naming_the_catalog_model_are_recognised(
    title: str,
    catalog_name: str,
    brand: str,
    exact: bool,
) -> None:
    from app.services.product_matching_service import _names_same_product

    assert (
        _names_same_product(title, catalog_name, (brand,), exact=exact)
        is True
    )


def test_structured_source_never_merges_sibling_models(
    client: TestClient,
    database_session: Session,
    catalog: dict[str, object],
) -> None:
    """A different model of the same brand becomes its own product."""

    token = catalog["token"]
    brand_name = f"Zeta{token}"
    hero, _ = add_product(database_session, catalog, f"{brand_name} QHero")

    response = client.post(
        MATCH_ENDPOINT,
        headers=headers(),
        json={
            "platform_code": "priceoye",
            "external_id": f"zeta{token}-qcrystal--black--standard",
            "title": f"{brand_name} QCrystal",
            "brand": brand_name,
            "color": "Black",
            "allow_catalog_create": True,
        },
    )
    body = response.json()

    assert body["matched"] is True
    assert body["canonical_product_id"] != hero.id
    assert body["product_name"] == f"{brand_name} QCrystal"
