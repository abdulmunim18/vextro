from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

# Allow running this file directly:
# python scripts/seed_demo_catalog.py
BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.platform import Platform
from app.models.price_history import PriceHistory
from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.seller import Seller


def money(value: int | float | str) -> Decimal:
    """Convert a normal value into a database-safe Decimal."""
    return Decimal(str(value))


HISTORY_DATES = [
    datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc),
    datetime(2026, 7, 8, 10, 0, tzinfo=timezone.utc),
    datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc),
    datetime(2026, 7, 22, 10, 0, tzinfo=timezone.utc),
    datetime(2026, 7, 29, 10, 0, tzinfo=timezone.utc),
]


PRODUCTS: list[dict[str, Any]] = [
    {
        "name": "Samsung Galaxy A55 5G",
        "slug": "samsung-galaxy-a55-5g-demo",
        "model": "SM-A556E",
        "brand_slug": "samsung",
        "image_url": (
            "https://placehold.co/900x900/F5F7FB/3157D5"
            "?text=Samsung+Galaxy+A55+5G"
        ),
        "description": (
            "Samsung Galaxy A55 5G demo product with a Super AMOLED "
            "display, multi-camera system and all-day battery."
        ),
        "specifications": {
            "display": "6.6-inch Super AMOLED",
            "processor": "Exynos 1480",
            "battery": "5000 mAh",
            "main_camera": "50 MP",
            "operating_system": "Android",
            "network": "5G",
        },
        "variant": {
            "sku": "VEXTRO-SAM-A55-8-256-ICE",
            "ram_gb": 8,
            "storage_gb": 256,
            "color": "Iceblue",
            "condition": "new",
            "variant_attributes": {
                "sim": "Dual SIM",
                "official_warranty": True,
            },
        },
        "listings": [
            {
                "platform_code": "daraz",
                "seller_code": "daraz-demo",
                "external_id": "daraz-demo-samsung-a55",
                "title": "Samsung Galaxy A55 5G 8GB 256GB Official Warranty",
                "product_url": "https://www.daraz.pk/",
                "current_price": 118999,
                "original_price": 124999,
                "rating": 4.6,
                "review_count": 384,
                "warranty": "1 Year Official Warranty",
                "history": [124999, 123499, 121999, 119999, 118999],
            },
            {
                "platform_code": "priceoye",
                "seller_code": "priceoye-demo",
                "external_id": "priceoye-demo-samsung-a55",
                "title": "Samsung Galaxy A55 5G 8GB 256GB",
                "product_url": "https://priceoye.pk/",
                "current_price": 114999,
                "original_price": 119999,
                "rating": 4.8,
                "review_count": 241,
                "warranty": "1 Year Brand Warranty",
                "history": [119999, 118499, 117999, 115999, 114999],
            },
        ],
    },
    {
        "name": "Apple iPhone 15",
        "slug": "apple-iphone-15-demo",
        "model": "A3090",
        "brand_slug": "apple",
        "image_url": (
            "https://placehold.co/900x900/F5F7FB/3157D5"
            "?text=Apple+iPhone+15"
        ),
        "description": (
            "Apple iPhone 15 demo product featuring the A16 Bionic chip, "
            "Super Retina XDR display and advanced dual-camera system."
        ),
        "specifications": {
            "display": "6.1-inch Super Retina XDR",
            "processor": "Apple A16 Bionic",
            "main_camera": "48 MP",
            "charging": "USB-C",
            "operating_system": "iOS",
            "network": "5G",
        },
        "variant": {
            "sku": "VEXTRO-APL-IP15-6-128-BLK",
            "ram_gb": 6,
            "storage_gb": 128,
            "color": "Black",
            "condition": "new",
            "variant_attributes": {
                "pta_status": "PTA Approved",
                "sim": "Dual SIM",
            },
        },
        "listings": [
            {
                "platform_code": "daraz",
                "seller_code": "daraz-demo",
                "external_id": "daraz-demo-iphone-15",
                "title": "Apple iPhone 15 128GB PTA Approved",
                "product_url": "https://www.daraz.pk/",
                "current_price": 324999,
                "original_price": 339999,
                "rating": 4.7,
                "review_count": 122,
                "warranty": "1 Year Seller Warranty",
                "history": [339999, 336999, 332999, 328999, 324999],
            },
            {
                "platform_code": "priceoye",
                "seller_code": "priceoye-demo",
                "external_id": "priceoye-demo-iphone-15",
                "title": "Apple iPhone 15 128GB",
                "product_url": "https://priceoye.pk/",
                "current_price": 319999,
                "original_price": 329999,
                "rating": 4.9,
                "review_count": 178,
                "warranty": "1 Year Warranty",
                "history": [329999, 327999, 324999, 321999, 319999],
            },
        ],
    },
    {
        "name": "Xiaomi Redmi Note 13 Pro",
        "slug": "xiaomi-redmi-note-13-pro-demo",
        "model": "23090RA98G",
        "brand_slug": "xiaomi",
        "image_url": (
            "https://placehold.co/900x900/F5F7FB/3157D5"
            "?text=Redmi+Note+13+Pro"
        ),
        "description": (
            "Redmi Note 13 Pro demo product with a high-resolution camera, "
            "AMOLED display and fast charging support."
        ),
        "specifications": {
            "display": "6.67-inch AMOLED",
            "processor": "MediaTek Helio G99 Ultra",
            "battery": "5000 mAh",
            "main_camera": "200 MP",
            "charging": "67W Fast Charging",
            "network": "4G",
        },
        "variant": {
            "sku": "VEXTRO-XIA-RN13P-8-256-BLK",
            "ram_gb": 8,
            "storage_gb": 256,
            "color": "Midnight Black",
            "condition": "new",
            "variant_attributes": {
                "sim": "Dual SIM",
                "official_warranty": True,
            },
        },
        "listings": [
            {
                "platform_code": "daraz",
                "seller_code": "daraz-demo",
                "external_id": "daraz-demo-redmi-note-13-pro",
                "title": "Xiaomi Redmi Note 13 Pro 8GB 256GB",
                "product_url": "https://www.daraz.pk/",
                "current_price": 78999,
                "original_price": 84999,
                "rating": 4.5,
                "review_count": 617,
                "warranty": "1 Year Official Warranty",
                "history": [84999, 82999, 81499, 79999, 78999],
            },
            {
                "platform_code": "priceoye",
                "seller_code": "priceoye-demo",
                "external_id": "priceoye-demo-redmi-note-13-pro",
                "title": "Redmi Note 13 Pro 8GB RAM 256GB Storage",
                "product_url": "https://priceoye.pk/",
                "current_price": 76499,
                "original_price": 80999,
                "rating": 4.7,
                "review_count": 402,
                "warranty": "1 Year Brand Warranty",
                "history": [80999, 79999, 78999, 77499, 76499],
            },
        ],
    },
    {
        "name": "Infinix Note 40 Pro",
        "slug": "infinix-note-40-pro-demo",
        "model": "X6851",
        "brand_slug": "infinix",
        "image_url": (
            "https://placehold.co/900x900/F5F7FB/3157D5"
            "?text=Infinix+Note+40+Pro"
        ),
        "description": (
            "Infinix Note 40 Pro demo product with an AMOLED display, "
            "large battery and fast wired charging."
        ),
        "specifications": {
            "display": "6.78-inch AMOLED",
            "processor": "MediaTek Helio G99 Ultimate",
            "battery": "5000 mAh",
            "main_camera": "108 MP",
            "charging": "70W Fast Charging",
            "operating_system": "Android",
        },
        "variant": {
            "sku": "VEXTRO-INF-N40P-12-256-GRN",
            "ram_gb": 12,
            "storage_gb": 256,
            "color": "Vintage Green",
            "condition": "new",
            "variant_attributes": {
                "sim": "Dual SIM",
                "wireless_charging": True,
            },
        },
        "listings": [
            {
                "platform_code": "daraz",
                "seller_code": "daraz-demo",
                "external_id": "daraz-demo-infinix-note-40-pro",
                "title": "Infinix Note 40 Pro 12GB 256GB",
                "product_url": "https://www.daraz.pk/",
                "current_price": 74999,
                "original_price": 79999,
                "rating": 4.4,
                "review_count": 295,
                "warranty": "1 Year Official Warranty",
                "history": [79999, 78999, 77499, 75999, 74999],
            },
            {
                "platform_code": "priceoye",
                "seller_code": "priceoye-demo",
                "external_id": "priceoye-demo-infinix-note-40-pro",
                "title": "Infinix Note 40 Pro 256GB",
                "product_url": "https://priceoye.pk/",
                "current_price": 72499,
                "original_price": 77999,
                "rating": 4.6,
                "review_count": 219,
                "warranty": "1 Year Brand Warranty",
                "history": [77999, 76499, 74999, 73499, 72499],
            },
        ],
    },
    {
        "name": "Tecno Camon 30",
        "slug": "tecno-camon-30-demo",
        "model": "CL6",
        "brand_slug": "tecno",
        "image_url": (
            "https://placehold.co/900x900/F5F7FB/3157D5"
            "?text=Tecno+Camon+30"
        ),
        "description": (
            "Tecno Camon 30 demo product with a smooth AMOLED display, "
            "high-resolution camera and fast charging."
        ),
        "specifications": {
            "display": "6.78-inch AMOLED",
            "processor": "MediaTek Helio G99 Ultimate",
            "battery": "5000 mAh",
            "main_camera": "50 MP",
            "charging": "70W Fast Charging",
            "operating_system": "Android",
        },
        "variant": {
            "sku": "VEXTRO-TEC-CAM30-8-256-BLU",
            "ram_gb": 8,
            "storage_gb": 256,
            "color": "Iceland Basaltic Dark",
            "condition": "new",
            "variant_attributes": {
                "sim": "Dual SIM",
                "official_warranty": True,
            },
        },
        "listings": [
            {
                "platform_code": "daraz",
                "seller_code": "daraz-demo",
                "external_id": "daraz-demo-tecno-camon-30",
                "title": "Tecno Camon 30 8GB 256GB Official Warranty",
                "product_url": "https://www.daraz.pk/",
                "current_price": 59999,
                "original_price": 64999,
                "rating": 4.3,
                "review_count": 341,
                "warranty": "1 Year Official Warranty",
                "history": [64999, 63499, 61999, 60999, 59999],
            },
            {
                "platform_code": "priceoye",
                "seller_code": "priceoye-demo",
                "external_id": "priceoye-demo-tecno-camon-30",
                "title": "Tecno Camon 30 256GB",
                "product_url": "https://priceoye.pk/",
                "current_price": 57999,
                "original_price": 61999,
                "rating": 4.5,
                "review_count": 187,
                "warranty": "1 Year Brand Warranty",
                "history": [61999, 60999, 59999, 58999, 57999],
            },
        ],
    },
]


def get_or_create_category(database: Session) -> Category:
    category = database.scalar(
        select(Category).where(Category.slug == "mobile-phones")
    )

    if category is not None:
        return category

    parent = database.scalar(
        select(Category).where(Category.slug == "electronics")
    )

    if parent is None:
        parent = Category(
            name="Electronics",
            slug="electronics",
            is_active=True,
        )
        database.add(parent)
        database.flush()

    category = Category(
        parent_id=parent.id,
        name="Mobile Phones",
        slug="mobile-phones",
        is_active=True,
    )
    database.add(category)
    database.flush()

    return category


def get_or_create_brand(
    database: Session,
    name: str,
    slug: str,
) -> Brand:
    brand = database.scalar(
        select(Brand).where(Brand.slug == slug)
    )

    if brand is None:
        brand = Brand(
            name=name,
            slug=slug,
            is_active=True,
        )
        database.add(brand)
        database.flush()

    return brand


def get_or_create_platform(
    database: Session,
    name: str,
    code: str,
    base_url: str,
) -> Platform:
    platform = database.scalar(
        select(Platform).where(Platform.code == code)
    )

    if platform is None:
        platform = Platform(
            name=name,
            code=code,
            base_url=base_url,
            is_active=True,
        )
        database.add(platform)
        database.flush()

    return platform


def get_or_create_seller(
    database: Session,
    platform: Platform,
    external_seller_id: str,
    name: str,
    profile_url: str,
    rating: str,
    review_count: int,
) -> Seller:
    seller = database.scalar(
        select(Seller).where(
            Seller.platform_id == platform.id,
            Seller.external_seller_id == external_seller_id,
        )
    )

    if seller is None:
        seller = Seller(
            platform_id=platform.id,
            external_seller_id=external_seller_id,
            name=name,
            profile_url=profile_url,
            rating=money(rating),
            review_count=review_count,
            is_verified=True,
            is_active=True,
        )
        database.add(seller)
        database.flush()
    else:
        seller.name = name
        seller.profile_url = profile_url
        seller.rating = money(rating)
        seller.review_count = review_count
        seller.is_verified = True
        seller.is_active = True

    return seller


def upsert_product(
    database: Session,
    category: Category,
    brand: Brand,
    product_data: dict[str, Any],
) -> CanonicalProduct:
    product = database.scalar(
        select(CanonicalProduct).where(
            CanonicalProduct.slug == product_data["slug"]
        )
    )

    if product is None:
        product = CanonicalProduct(
            category_id=category.id,
            brand_id=brand.id,
            name=product_data["name"],
            slug=product_data["slug"],
            model=product_data["model"],
            description=product_data["description"],
            specifications=product_data["specifications"],
            is_active=True,
        )
        database.add(product)
        database.flush()
    else:
        product.category_id = category.id
        product.brand_id = brand.id
        product.name = product_data["name"]
        product.model = product_data["model"]
        product.description = product_data["description"]
        product.specifications = product_data["specifications"]
        product.is_active = True

    return product


def upsert_variant(
    database: Session,
    product: CanonicalProduct,
    variant_data: dict[str, Any],
) -> ProductVariant:
    variant = database.scalar(
        select(ProductVariant).where(
            ProductVariant.sku == variant_data["sku"]
        )
    )

    if variant is None:
        variant = ProductVariant(
            canonical_product_id=product.id,
            sku=variant_data["sku"],
            ram_gb=variant_data["ram_gb"],
            storage_gb=variant_data["storage_gb"],
            color=variant_data["color"],
            condition=variant_data["condition"],
            variant_attributes=variant_data["variant_attributes"],
            is_active=True,
        )
        database.add(variant)
        database.flush()
    else:
        variant.canonical_product_id = product.id
        variant.ram_gb = variant_data["ram_gb"]
        variant.storage_gb = variant_data["storage_gb"]
        variant.color = variant_data["color"]
        variant.condition = variant_data["condition"]
        variant.variant_attributes = variant_data["variant_attributes"]
        variant.is_active = True

    return variant


def upsert_listing(
    database: Session,
    variant: ProductVariant,
    platform: Platform,
    seller: Seller,
    listing_data: dict[str, Any],
) -> ProductListing:
    listing = database.scalar(
        select(ProductListing).where(
            ProductListing.platform_id == platform.id,
            ProductListing.external_id == listing_data["external_id"],
        )
    )

    if listing is None:
        listing = ProductListing(
            platform_id=platform.id,
            product_variant_id=variant.id,
            seller_id=seller.id,
            external_id=listing_data["external_id"],
            title=listing_data["title"],
            product_url=listing_data["product_url"],
            current_price=money(listing_data["current_price"]),
            original_price=money(listing_data["original_price"]),
            currency="PKR",
            rating=money(listing_data["rating"]),
            review_count=listing_data["review_count"],
            warranty=listing_data["warranty"],
            is_available=True,
            raw_payload={
                "source": "vextro_demo_seed",
                "demo": True,
            },
            first_seen_at=HISTORY_DATES[0],
            last_seen_at=HISTORY_DATES[-1],
        )
        database.add(listing)
        database.flush()
    else:
        listing.product_variant_id = variant.id
        listing.seller_id = seller.id
        listing.title = listing_data["title"]
        listing.product_url = listing_data["product_url"]
        listing.current_price = money(listing_data["current_price"])
        listing.original_price = money(listing_data["original_price"])
        listing.currency = "PKR"
        listing.rating = money(listing_data["rating"])
        listing.review_count = listing_data["review_count"]
        listing.warranty = listing_data["warranty"]
        listing.is_available = True
        listing.raw_payload = {
            "source": "vextro_demo_seed",
            "demo": True,
        }
        listing.last_seen_at = HISTORY_DATES[-1]

    return listing


def ensure_product_image(
    database: Session,
    product: CanonicalProduct,
    image_url: str,
) -> None:
    existing_image = database.scalar(
        select(ProductImage).where(
            ProductImage.canonical_product_id == product.id,
            ProductImage.image_url == image_url,
        )
    )

    if existing_image is None:
        database.add(
            ProductImage(
                canonical_product_id=product.id,
                listing_id=None,
                image_url=image_url,
                alt_text=product.name,
                is_primary=True,
                sort_order=0,
            )
        )


def ensure_price_history(
    database: Session,
    listing: ProductListing,
    listing_data: dict[str, Any],
) -> None:
    prices = listing_data["history"]

    if len(prices) != len(HISTORY_DATES):
        raise ValueError(
            f"History points mismatch for {listing_data['external_id']}."
        )

    for captured_at, price in zip(
        HISTORY_DATES,
        prices,
        strict=True,
    ):
        existing_point = database.scalar(
            select(PriceHistory).where(
                PriceHistory.listing_id == listing.id,
                PriceHistory.captured_at == captured_at,
            )
        )

        if existing_point is None:
            database.add(
                PriceHistory(
                    listing_id=listing.id,
                    price=money(price),
                    original_price=money(
                        listing_data["original_price"]
                    ),
                    currency="PKR",
                    is_available=True,
                    source="demo_seed",
                    captured_at=captured_at,
                )
            )
        else:
            existing_point.price = money(price)
            existing_point.original_price = money(
                listing_data["original_price"]
            )
            existing_point.currency = "PKR"
            existing_point.is_available = True
            existing_point.source = "demo_seed"


def seed_demo_catalog() -> None:
    database = SessionLocal()

    try:
        category = get_or_create_category(database)

        brand_details = {
            "apple": "Apple",
            "samsung": "Samsung",
            "xiaomi": "Xiaomi",
            "infinix": "Infinix",
            "tecno": "Tecno",
        }

        brands = {
            slug: get_or_create_brand(
                database,
                name=name,
                slug=slug,
            )
            for slug, name in brand_details.items()
        }

        platforms = {
            "daraz": get_or_create_platform(
                database,
                name="Daraz",
                code="daraz",
                base_url="https://www.daraz.pk",
            ),
            "priceoye": get_or_create_platform(
                database,
                name="PriceOye",
                code="priceoye",
                base_url="https://priceoye.pk",
            ),
        }

        sellers = {
            "daraz-demo": get_or_create_seller(
                database,
                platform=platforms["daraz"],
                external_seller_id="vextro-daraz-demo-seller",
                name="Daraz Mall Demo Seller",
                profile_url="https://www.daraz.pk/",
                rating="4.70",
                review_count=12600,
            ),
            "priceoye-demo": get_or_create_seller(
                database,
                platform=platforms["priceoye"],
                external_seller_id="vextro-priceoye-demo-seller",
                name="PriceOye Verified Demo",
                profile_url="https://priceoye.pk/",
                rating="4.80",
                review_count=9100,
            ),
        }

        for product_data in PRODUCTS:
            product = upsert_product(
                database,
                category=category,
                brand=brands[product_data["brand_slug"]],
                product_data=product_data,
            )

            variant = upsert_variant(
                database,
                product=product,
                variant_data=product_data["variant"],
            )

            ensure_product_image(
                database,
                product=product,
                image_url=product_data["image_url"],
            )

            for listing_data in product_data["listings"]:
                platform = platforms[
                    listing_data["platform_code"]
                ]

                seller = sellers[
                    listing_data["seller_code"]
                ]

                listing = upsert_listing(
                    database,
                    variant=variant,
                    platform=platform,
                    seller=seller,
                    listing_data=listing_data,
                )

                ensure_price_history(
                    database,
                    listing=listing,
                    listing_data=listing_data,
                )

        database.commit()

        product_count = database.scalar(
            select(func.count()).select_from(CanonicalProduct)
        )

        variant_count = database.scalar(
            select(func.count()).select_from(ProductVariant)
        )

        listing_count = database.scalar(
            select(func.count()).select_from(ProductListing)
        )

        history_count = database.scalar(
            select(func.count()).select_from(PriceHistory)
        )

        print()
        print("VEXTRO demo catalog seeded successfully.")
        print("----------------------------------------")
        print(f"Canonical products : {product_count}")
        print(f"Product variants   : {variant_count}")
        print(f"Marketplace offers : {listing_count}")
        print(f"Price snapshots    : {history_count}")
        print("----------------------------------------")
        print("The script is idempotent and can be run again safely.")

    except Exception:
        database.rollback()
        print()
        print("Demo catalog seeding failed. Transaction rolled back.")
        raise

    finally:
        database.close()


if __name__ == "__main__":
    seed_demo_catalog()