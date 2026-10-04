"""Keep shops and accessories out of the phone catalog.

Daraz publishes the selling store in its brand field and serves cables,
chargers and covers from the same category page as phones. Both reached the
catalog: the brand filter listed "Carrefour" and "OPPO Pakistan Official"
beside Samsung, one phone existed twice under two store brands, and a 45W
charger sat in the product list as if shoppers could compare it with a
handset.
"""

from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.price_history import PriceHistory
from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.services.smartphone_normalization import (
    infer_brand_name,
    is_accessory_product_name,
    is_accessory_title,
    looks_like_reseller,
)


RESOLVE_ENDPOINT = "/api/v1/internal/acquisition/resolve-product"

TEST_INGESTION_KEY = "VextroHygieneTestIngestionKey2026"


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


# --------------------------------------------------------------------------
# Brands
# --------------------------------------------------------------------------


def test_the_brand_is_the_maker_not_the_shop() -> None:
    assert infer_brand_name(
        "Carrefour Samsung Galaxy A07 4+128GB Green",
        "Carrefour",
    ) == "Samsung"
    assert infer_brand_name("Oppo A6 8+256GB", "OPPO Pakistan Official") == (
        "Oppo"
    )
    assert infer_brand_name("Redmi 15 4G", "Redmi") == "Xiaomi"
    assert infer_brand_name("Vivo Y29 5G", "vivo .") == "Vivo"
    assert infer_brand_name("Faywa F1", "FAYWA TRADING (PVT) LTD") == "Faywa"


def test_an_unknown_maker_survives_but_a_shop_name_does_not() -> None:
    # A real low-cost brand VEXTRO has no alias for is kept as published.
    assert infer_brand_name("me Mobile L109", "me Mobile") == "me Mobile"
    assert infer_brand_name("E-Tachi iPro", "E-Tachi") == "E-Tachi"

    # A shop on a phone VEXTRO cannot recognise is no brand at all.
    assert infer_brand_name("Mystery Device X1", "Al Fatah Store") is None
    assert infer_brand_name("Some Phone", ".No Brand.") is None

    assert looks_like_reseller("OPPO Pakistan Official") is True
    assert looks_like_reseller("me Mobile") is False


def test_a_store_branded_listing_lands_under_the_maker(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],
) -> None:
    """The reported duplicate: one phone, two brands, two products."""

    token = uuid4().hex[:8]

    result = resolve(
        client,
        discovered_products,
        platform_code="daraz",
        external_id=f"BRAND-{token}",
        title=f"Carrefour Samsung Galaxy TX{token} 4+128GB Green-303662",
        brand="Carrefour",
        seller_name="Carrefour Pakistan",
        specifications={"ram": "4GB", "storage_capacity": "128GB"},
    )

    assert result["matched"] is True
    assert result["brand_name"] == "Samsung"

    product = database_session.get(
        CanonicalProduct,
        int(result["canonical_product_id"]),
    )
    brand = database_session.get(Brand, product.brand_id)

    assert brand is not None
    assert brand.name == "Samsung"


# --------------------------------------------------------------------------
# Accessories
# --------------------------------------------------------------------------


def test_accessory_titles_are_recognised() -> None:
    assert is_accessory_title("2 in 1 OTG CABLE TYPE C & MICRO") is True
    assert is_accessory_title(
        "Original Samsung 45W GaN Charger UK Plug for GALAXY S25"
    ) is True
    assert is_accessory_title(
        "ALL Mobile Phone Dustproof Net Stickers Pack Of 10"
    ) is True

    assert is_accessory_title("Samsung Galaxy A07 4+128GB Green") is False
    assert is_accessory_title(
        "Infinix Hot 50 8GB 256GB 5000mAh Battery 50MP Camera"
    ) is False


def test_a_phone_that_advertises_its_free_charger_is_still_a_phone() -> None:
    """Marketing copy lists what is in the box; that is not the product."""

    assert is_accessory_title(
        "Original Vivo Y85 Smartphone | 4GB 64GB | PTA Approved | "
        "FREE Charger Included"
    ) is False
    assert is_accessory_product_name("Vivo Y85") is False
    assert is_accessory_product_name("ZTE Nubia V80 Max") is False


def test_phones_that_list_bundled_or_supported_accessories_survive(
) -> None:
    """Real Daraz phones a first version of this rule threw away.

    A phone's copy says what comes in the box and which accessories it
    supports; neither makes the listing an accessory.
    """

    survivors = (
        "Infinix Note 60 Pro 8GB / 256GB with Free Powerbank",
        "Sharp Aquos R7 - 12GB RAM - 256GB ROM +SD Card Supported - "
        "(Phone Only - Box Charger Accessoires Not Included)",
        "Vivo Y17 Phone | 4GB RAM 128GB Storage | Memory Card Support | "
        "Box Charger & Phone",
        "Vivo Y66 | Memory Card Suppirt | Vivo Box , Charger Sim Injector "
        "Tool & Phone",
        "Vivo Y71 | 6GB Ram | Dual Sim + Memory Card | With Free Gift Box",
    )

    for title in survivors:
        assert is_accessory_title(title) is False, title


def test_a_charger_is_recognised_from_its_catalog_name() -> None:
    """Shortening a title can cut the word "charger" off the end.

    What remains still names a charger - wattage and charging standards -
    which no phone is named after.
    """

    assert is_accessory_product_name(
        "Original Samsung 45W PD UK Pin PPS Super Fast GaN"
    ) is True
    assert is_accessory_product_name(
        "ZTE Nubia V80 Max - 6.9 Inches Display - 8GB RAM 256GB ROM - "
        "USB Type-C - Octa Core"
    ) is False


def test_an_accessory_never_becomes_a_catalog_product(
    client: TestClient,
    discovered_products: list[int],
) -> None:
    token = uuid4().hex[:8]

    result = resolve(
        client,
        discovered_products,
        platform_code="daraz",
        external_id=f"ACCESSORY-{token}",
        title=(
            f"Original Samsung {token} 45W PD UK Pin Super Fast GaN "
            "Charger for GALAXY S25"
        ),
        brand="Samsung",
    )

    assert result["matched"] is False
    assert result["product_created"] is False
    assert result["product_variant_id"] is None
