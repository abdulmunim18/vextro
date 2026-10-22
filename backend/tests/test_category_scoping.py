"""Categories are kept apart: in matching, in the catalogue, in retirement."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.platform import Platform
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.services.listing_refresh_service import CATEGORY_SPIDERS, TARGETED_SPIDERS
from tests.test_smartphone_sync import (  # noqa: F401 - shared fixtures
    FIRST_CAPTURE,
    RESOLVE_ENDPOINT,
    RUNS_ENDPOINT,
    configure_ingestion_key,
    discover,
    discovered_products,
    headers,
    ingest,
    listing_payload,
    sync_context,
)


def category_of(session: Session, product_id) -> str:
    return session.scalar(
        select(Category.slug)
        .join(CanonicalProduct, CanonicalProduct.category_id == Category.id)
        .where(CanonicalProduct.id == int(product_id))
    )


def variant(session: Session, variant_id) -> ProductVariant:
    found = session.get(ProductVariant, int(variant_id))
    session.refresh(found)
    return found


def tablet(**overrides):
    payload = {
        "platform_code": "priceoye",
        "brand": "Samsung",
        "color": "Grey",
        "category_slug": "tablets",
        # The crawler sends memory as specifications, as it does for phones.
        "specifications": {"ram": "8GB", "storage_capacity": "128GB"},
        "exact_model_title": True,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# Filing and matching
# --------------------------------------------------------------------------


def test_a_tablet_is_filed_under_tablets(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],  # noqa: F811
) -> None:
    token = uuid4().hex[:6]
    result = discover(
        client,
        discovered_products,
        external_id=f"TAB-{token}",
        title=f"Samsung Galaxy Tab Fl{token} 8GB 128GB WiFi",
        **tablet(),
    )

    assert result["product_created"] is True
    assert category_of(database_session, result["canonical_product_id"]) == "tablets"
    assert variant(database_session, result["product_variant_id"]).configuration_key == (
        "connectivity=wifi|ram_gb=8|storage_gb=128"
    )


def test_a_listing_naming_no_category_is_still_a_phone(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],  # noqa: F811
) -> None:
    token = uuid4().hex[:6]
    result = discover(
        client,
        discovered_products,
        platform_code="priceoye",
        external_id=f"PH-{token}",
        title=f"Samsung Galaxy Ph{token}",
        brand="Samsung",
        color="Black",
        specifications={"ram": "8GB", "storage_capacity": "256GB"},
        exact_model_title=True,
    )

    assert category_of(database_session, result["canonical_product_id"]) == "mobile-phones"


def test_a_tablet_never_joins_a_phone_of_the_same_name(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],  # noqa: F811
) -> None:
    token = uuid4().hex[:6]
    phone = discover(
        client,
        discovered_products,
        platform_code="priceoye",
        external_id=f"SAME-{token}-PH",
        title=f"Samsung Galaxy Sm{token}",
        brand="Samsung",
        color="Grey",
        specifications={"ram": "8GB", "storage_capacity": "128GB"},
        exact_model_title=True,
    )
    pad = discover(
        client,
        discovered_products,
        external_id=f"SAME-{token}-TAB",
        title=f"Samsung Galaxy Sm{token} 8GB 128GB",
        **tablet(),
    )

    assert pad["canonical_product_id"] != phone["canonical_product_id"]
    assert category_of(database_session, pad["canonical_product_id"]) == "tablets"
    assert category_of(database_session, phone["canonical_product_id"]) == "mobile-phones"


def test_wifi_and_cellular_tablets_are_separate_variants_of_one_product(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],  # noqa: F811
) -> None:
    token = uuid4().hex[:6]
    wifi = discover(
        client,
        discovered_products,
        external_id=f"NET-{token}-W",
        title=f"Samsung Galaxy Tab Nt{token} 8GB 128GB Wi-Fi",
        **tablet(),
    )
    cellular = discover(
        client,
        discovered_products,
        external_id=f"NET-{token}-C",
        title=f"Samsung Galaxy Tab Nt{token} 8GB 128GB LTE",
        **tablet(),
    )

    assert cellular["canonical_product_id"] == wifi["canonical_product_id"]
    assert cellular["product_variant_id"] != wifi["product_variant_id"]
    assert variant(database_session, cellular["product_variant_id"]).variant_attributes["identity"] == {
        "connectivity": "cellular",
        "ram_gb": 8,
        "storage_gb": 128,
    }


def test_a_new_colour_keeps_the_matched_variants_connectivity(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],  # noqa: F811
) -> None:
    token = uuid4().hex[:6]
    grey = discover(
        client,
        discovered_products,
        external_id=f"COL-{token}-G",
        title=f"Samsung Galaxy Tab Cl{token} 8GB 128GB 5G",
        **tablet(),
    )
    silver = discover(
        client,
        discovered_products,
        external_id=f"COL-{token}-S",
        title=f"Samsung Galaxy Tab Cl{token} 8GB 128GB 5G",
        **tablet(color="Silver"),
    )

    assert silver["canonical_product_id"] == grey["canonical_product_id"]
    assert silver["product_variant_id"] != grey["product_variant_id"]
    assert variant(database_session, silver["product_variant_id"]).configuration_key == (
        "connectivity=cellular|ram_gb=8|storage_gb=128"
    )


def test_a_watch_of_another_case_size_is_another_variant(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],  # noqa: F811
) -> None:
    token = uuid4().hex[:6]
    small = discover(
        client,
        discovered_products,
        platform_code="priceoye",
        external_id=f"W-{token}-40",
        title=f"Samsung Galaxy Watch Wt{token} 40mm",
        brand="Samsung",
        color="Black",
        category_slug="smart-watches",
        exact_model_title=True,
    )
    large = discover(
        client,
        discovered_products,
        platform_code="priceoye",
        external_id=f"W-{token}-44",
        title=f"Samsung Galaxy Watch Wt{token} 44mm",
        brand="Samsung",
        color="Black",
        category_slug="smart-watches",
        exact_model_title=True,
    )

    assert large["canonical_product_id"] == small["canonical_product_id"]
    assert large["product_variant_id"] != small["product_variant_id"]
    assert category_of(database_session, small["canonical_product_id"]) == "smart-watches"


def test_an_unknown_category_is_refused(client: TestClient) -> None:
    response = client.post(
        RESOLVE_ENDPOINT,
        headers=headers(),
        json={"title": "Some Fashion Item", "category_slug": "fashion"},
    )

    assert response.status_code == 422


# --------------------------------------------------------------------------
# Retirement stays within the crawled category
# --------------------------------------------------------------------------


def test_a_complete_phone_crawl_does_not_retire_tablets(
    client: TestClient,
    database_session: Session,
    sync_context: dict[str, object],  # noqa: F811
    discovered_products: list[int],  # noqa: F811
) -> None:
    database_session.execute(
        ProductListing.__table__.update()
        .where(
            ProductListing.platform_id
            == select(Platform.id).where(Platform.code == "priceoye").scalar_subquery()
        )
        .values(is_available=False)
    )
    database_session.commit()

    token = uuid4().hex[:6]
    pad = discover(
        client,
        discovered_products,
        external_id=f"RET-{token}-TAB",
        title=f"Samsung Galaxy Tab Rt{token} 8GB 128GB WiFi",
        **tablet(),
    )
    ingest(
        client,
        listing_payload(
            sync_context,
            current_price=90000,
            captured_at=FIRST_CAPTURE,
            platform_code="priceoye",
            product_variant_id=int(pad["product_variant_id"]),
            external_id=f"RET-{token}-TAB",
        ),
    )

    def phone(name: str, moment: datetime) -> None:
        ingest(
            client,
            listing_payload(
                sync_context,
                current_price=100000,
                captured_at=moment,
                platform_code="priceoye",
                external_id=f"RET-{token}-{name}",
            ),
        )

    phone("old", FIRST_CAPTURE)
    started = client.post(
        RUNS_ENDPOINT,
        headers=headers(),
        json={
            "platform": "priceoye",
            "spider_name": "priceoye_smartphones",
            "trigger_type": "test",
            "parser_version": "priceoye-test",
            "category": "mobile-phones",
        },
    )
    assert started.status_code == 201, started.text
    assert started.json()["category"] == "mobile-phones"

    later = datetime.now(timezone.utc) + timedelta(seconds=5)
    phone("seen-1", later)
    phone("seen-2", later)

    finished = client.patch(
        f"{RUNS_ENDPOINT}/{started.json()['id']}",
        headers=headers(),
        json={
            "crawl_succeeded": True,
            "full_crawl": True,
            "items_discovered": 2,
            "items_ingested": 2,
            "items_rejected": 0,
            "items_failed": 0,
            "error_count": 0,
        },
    )
    assert finished.status_code == 200, finished.text

    database_session.expire_all()
    availability = dict(
        database_session.execute(
            select(ProductListing.external_id, ProductListing.is_available).where(
                ProductListing.external_id.like(f"RET-{token}-%")
            )
        ).all()
    )

    assert availability[f"RET-{token}-old"] is False      # the phone it lost
    assert availability[f"RET-{token}-TAB"] is True       # a tablet it never looked for


def test_a_run_for_an_unknown_category_is_refused(client: TestClient) -> None:
    response = client.post(
        RUNS_ENDPOINT,
        headers=headers(),
        json={
            "platform": "priceoye",
            "spider_name": "priceoye_fashion",
            "trigger_type": "test",
            "parser_version": "x",
            "category": "fashion",
        },
    )

    assert response.status_code == 422


# --------------------------------------------------------------------------
# Page refresh
# --------------------------------------------------------------------------


def test_only_smartphones_have_page_refresh_spiders_so_far() -> None:
    assert CATEGORY_SPIDERS == {"mobile-phones": TARGETED_SPIDERS}


def test_opening_a_tablet_starts_no_phone_spider(
    client: TestClient,
    database_session: Session,
    sync_context: dict[str, object],  # noqa: F811
    discovered_products: list[int],  # noqa: F811
    monkeypatch,
) -> None:
    from app.core.config import settings
    from app.services.listing_refresh_service import listing_refresh_service

    started: list[object] = []
    monkeypatch.setattr(listing_refresh_service, "launcher", lambda *args: started.append(args))
    monkeypatch.setattr(listing_refresh_service, "_started_at", {})
    monkeypatch.setattr(listing_refresh_service, "_running", [])
    monkeypatch.setattr(settings, "on_demand_refresh_enabled", True)

    token = uuid4().hex[:6]
    pad = discover(
        client,
        discovered_products,
        external_id=f"REF-{token}",
        title=f"Samsung Galaxy Tab Rf{token} 8GB 128GB WiFi",
        **tablet(),
    )
    ingest(
        client,
        listing_payload(
            sync_context,
            current_price=90000,
            captured_at=FIRST_CAPTURE,
            platform_code="priceoye",
            product_variant_id=int(pad["product_variant_id"]),
            external_id=f"REF-{token}",
            product_url=f"https://priceoye.pk/tablets/samsung/tab-rf{token}",
        ),
    )

    result = client.post(f"/api/v1/products/{pad['canonical_product_id']}/refresh").json()

    assert started == []
    assert {item["platform_code"]: item["status"] for item in result["platforms"]} == {
        "priceoye": "scheduled_only",
    }
