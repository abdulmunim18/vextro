"""Legacy ingestion API retained for compatibility.

The active Daraz and PriceOye scraper uses the authenticated internal
acquisition routes instead. New acquisition clients must not use this module.
"""

from fastapi import APIRouter, Depends, HTTPException, status
import re
from sqlalchemy import func
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import urlparse

from app.core.database import get_db
from app.models.product_listing import ProductListing
from app.models.canonical_product import CanonicalProduct
from app.models.product_variant import ProductVariant
from app.models.platform import Platform
from app.models.category import Category
from app.models.price_history import PriceHistory
from app.models.product_image import ProductImage
from app.models.brand import Brand
from app.services.cross_marketplace_matching import (
    clean_product_display_name,
    find_cross_platform_canonical,
)

# Create the router for the ingestion URL
router = APIRouter(
    prefix="/ingest",
    tags=["Data Ingestion"],
    deprecated=True,
)

# Define the exact data structure we expect from Scrapy
class ScrapedItemPayload(BaseModel):
    platform: str
    external_id: str
    model: str
    brand: Optional[str] = None
    product_url: str
    price: float = Field(gt=0, allow_inf_nan=False)
    currency: str = "PKR"
    color: Optional[str] = "N/A"
    variant: Optional[str] = "Standard"
    availability: str
    is_available: bool
    warranty: Optional[str] = "Official Brand Warranty"
    image_urls: list[str] = Field(default_factory=list, max_length=12)
    specifications: dict[str, Any] = Field(default_factory=dict)

    @field_validator("image_urls")
    @classmethod
    def validate_image_urls(cls, value: list[str]) -> list[str]:
        """Keep unique absolute HTTP image URLs in scraper order."""

        normalized_urls: list[str] = []

        for image_url in value:
            normalized_url = image_url.strip()
            parsed_url = urlparse(normalized_url)

            if (
                parsed_url.scheme not in {"http", "https"}
                or not parsed_url.netloc
            ):
                raise ValueError(
                    "image_urls must contain absolute HTTP URLs"
                )

            if normalized_url not in normalized_urls:
                normalized_urls.append(normalized_url)

        return normalized_urls

    @field_validator("specifications")
    @classmethod
    def validate_specifications(
        cls,
        value: dict[str, Any],
    ) -> dict[str, str]:
        """Limit scraper data to compact, display-safe label/value pairs."""

        normalized: dict[str, str] = {}

        for raw_key, raw_value in list(value.items())[:80]:
            key = str(raw_key).strip().lower().replace(" ", "_")[:80]
            if not key or raw_value is None:
                continue

            if isinstance(raw_value, list):
                display_value = ", ".join(
                    str(item).strip()
                    for item in raw_value
                    if str(item).strip()
                )
            else:
                display_value = str(raw_value).strip()

            if display_value:
                normalized[key] = display_value[:2000]

        return normalized


BRAND_ALIASES = (
    ("Samsung", ("samsung", "galaxy")),
    ("Apple", ("apple", "iphone")),
    ("Xiaomi", ("xiaomi", "redmi", "poco")),
    ("Infinix", ("infinix",)),
    ("Tecno", ("tecno",)),
    ("Oppo", ("oppo",)),
    ("Vivo", ("vivo",)),
    ("Realme", ("realme",)),
    ("OnePlus", ("oneplus", "one plus")),
    ("Huawei", ("huawei",)),
    ("Honor", ("honor",)),
    ("Nokia", ("nokia",)),
    ("Google", ("google pixel", "pixel")),
    ("Motorola", ("motorola", "moto")),
    ("Itel", ("itel",)),
    ("Sparx", ("sparx",)),
    ("Dcode", ("dcode", "d-code")),
    ("QMobile", ("qmobile", "q mobile")),
    ("Faywa", ("faywa",)),
    ("Nothing", ("nothing", "cmf phone")),
    ("Sego", ("sego",)),
    ("Villaon", ("villaon",)),
    ("LG", ("lg",)),
    ("Balmuda", ("balmuda",)),
    ("Sony", ("sony", "xperia")),
    ("Sharp", ("sharp", "aquos")),
    ("ZTE", ("zte", "nubia")),
    ("VGOTEL", ("vgotel",)),
)


def infer_brand_name(model: str, provided_brand: str | None = None) -> str | None:
    """Normalize an explicit brand or infer a known brand from a title."""

    if provided_brand:
        cleaned_brand = provided_brand.strip()
        if cleaned_brand.lower() not in {
            "n/a", "na", "none", "no brand", "unbranded",
        }:
            return cleaned_brand[:120]

    normalized_model = f" {model.lower()} "
    for canonical_name, aliases in BRAND_ALIASES:
        if any(
            re.search(
                rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
                normalized_model,
            )
            for alias in aliases
        ):
            return canonical_name

    return None


def infer_title_specifications(model: str) -> dict[str, str]:
    """Extract common technical values embedded in marketplace titles."""

    inferred: dict[str, str] = {}
    patterns = (
        ("ram", (
            r"\b(\d{1,2})\s*GB\s*RAM\b",
            r"\bRAM\s*[:\-]?\s*(\d{1,2})\s*GB\b",
        ), "GB"),
        ("storage_capacity", (
            r"\b(\d{2,4})\s*GB\s*(?:ROM|Storage|Memory)\b",
            r"\b(?:ROM|Storage|Memory)\s*[:\-]?\s*(\d{2,4})\s*GB\b",
        ), "GB"),
        ("battery_capacity", (r"\b(\d{3,5})\s*mAh\b",), " mAh"),
        ("display", (
            r"\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:inches|inch|\")\s*(?:display|screen)?",
        ), " inches"),
        ("front_camera", (
            r"\b(\d{1,3})\s*MP\s*Front\s*Camera\b",
            r"\bFront\s*Camera\s*[:\-]?\s*(\d{1,3})\s*MP\b",
        ), "MP"),
    )

    for key, key_patterns, suffix in patterns:
        for pattern in key_patterns:
            match = re.search(pattern, model, re.I)
            if match:
                inferred[key] = f"{match.group(1)}{suffix}"
                break

    capacity_pair = re.search(
        r"\b(\d{1,2})\s*(?:GB)?\s*[/+|]\s*(\d{2,4})\s*GB\b",
        model,
        re.I,
    )
    if capacity_pair:
        inferred.setdefault("ram", f"{capacity_pair.group(1)}GB")
        inferred.setdefault(
            "storage_capacity",
            f"{capacity_pair.group(2)}GB",
        )

    storage_options = list(dict.fromkeys(
        match.group(1)
        for match in re.finditer(r"\b(\d{2,4})\s*GB\b", model, re.I)
        if int(match.group(1)) >= 32
    ))
    if storage_options:
        inferred.setdefault(
            "storage_options",
            ", ".join(f"{value}GB" for value in storage_options),
        )
    if re.search(r"\bPTA\s*Approved\b", model, re.I):
        inferred.setdefault("pta_status", "PTA Approved")
    if re.search(r"\bDual\s*SIM\b|\b2\s*SIM\b", model, re.I):
        inferred.setdefault("sim", "Dual SIM")
    if re.search(r"\bType[ -]?C\b|\bUSB[ -]?C\b", model, re.I):
        inferred.setdefault("charging", "USB Type-C")
    if re.search(r"\bBluetooth\b", model, re.I):
        inferred.setdefault("connectivity", "Bluetooth")
    warranty = re.search(r"\b(\d+\s*Year\s*Warranty)\b", model, re.I)
    if warranty:
        inferred.setdefault("warranty", warranty.group(1))

    return inferred


def resolve_brand(db: Session, payload: ScrapedItemPayload) -> Brand | None:
    """Find or create a safe canonical brand for an ingested product."""

    brand_name = infer_brand_name(payload.model, payload.brand)
    if not brand_name:
        return None

    brand = db.query(Brand).filter(
        func.lower(Brand.name) == brand_name.lower()
    ).first()
    if brand:
        return brand

    slug_base = re.sub(r"[^a-z0-9]+", "-", brand_name.lower()).strip("-")
    slug = slug_base or "brand"
    suffix = 2
    while db.query(Brand).filter(Brand.slug == slug).first():
        slug = f"{slug_base}-{suffix}"
        suffix += 1

    brand = Brand(name=brand_name, slug=slug, is_active=True)
    db.add(brand)
    db.flush()
    return brand


def merged_product_specifications(
    payload: ScrapedItemPayload,
    existing: dict | None = None,
) -> dict[str, str]:
    """Merge technical specs while retaining useful variant fallbacks."""

    specifications = infer_title_specifications(payload.model)
    specifications.update(existing or {})
    specifications.update(payload.specifications)

    if payload.color and payload.color != "N/A":
        specifications["color"] = payload.color
    if payload.variant and payload.variant != "Standard":
        specifications["variant"] = payload.variant

    return specifications


def extract_memory_capacities(
    payload: ScrapedItemPayload,
) -> tuple[int | None, int | None]:
    """Derive RAM/storage values for variant filters and display."""

    def first_number(*keys: str) -> int | None:
        for key in keys:
            value = payload.specifications.get(key)
            match = re.search(r"\b(\d{1,4})\s*(?:GB|G)\b", value or "", re.I)
            if match:
                return int(match.group(1))
        return None

    ram_gb = first_number("ram", "memory_ram")
    storage_gb = first_number(
        "storage_capacity",
        "internal_memory",
        "storage",
        "rom",
    )

    combined_text = f"{payload.variant or ''} {payload.model}"
    capacity_pair = re.search(
        r"\b(\d{1,3})\s*GB\s*(?:RAM)?\s*[-/+|]\s*(\d{2,4})\s*GB\b",
        combined_text,
        re.I,
    )
    if capacity_pair:
        ram_gb = ram_gb or int(capacity_pair.group(1))
        storage_gb = storage_gb or int(capacity_pair.group(2))

    return ram_gb, storage_gb


def sync_product_images(
    db: Session,
    *,
    listing: ProductListing,
    canonical_product: CanonicalProduct,
    image_urls: list[str],
    alt_text: str,
) -> None:
    """Persist one listing gallery and seed canonical product images."""

    if not image_urls:
        return

    listing_images = db.query(ProductImage).filter(
        ProductImage.listing_id == listing.id
    ).all()
    listing_images_by_url = {
        image.image_url: image for image in listing_images
    }

    for existing_image in listing_images:
        if existing_image.image_url not in image_urls:
            db.delete(existing_image)

    for sort_order, image_url in enumerate(image_urls):
        listing_image = listing_images_by_url.get(image_url)

        if listing_image is None:
            listing_image = ProductImage(
                listing_id=listing.id,
                image_url=image_url,
            )
            db.add(listing_image)

        listing_image.alt_text = alt_text[:255]
        listing_image.is_primary = sort_order == 0
        listing_image.sort_order = sort_order

    canonical_images = db.query(ProductImage).filter(
        ProductImage.canonical_product_id == canonical_product.id
    ).all()

    placeholder_hosts = {
        "placehold.co",
        "via.placeholder.com",
        "placeholder.com",
    }
    incoming_has_real_image = any(
        urlparse(image_url).netloc.lower() not in placeholder_hosts
        for image_url in image_urls
    )

    if incoming_has_real_image:
        retained_canonical_images: list[ProductImage] = []

        for canonical_image in canonical_images:
            image_host = urlparse(
                canonical_image.image_url
            ).netloc.lower()

            if image_host in placeholder_hosts:
                db.delete(canonical_image)
            else:
                retained_canonical_images.append(canonical_image)

        canonical_images = retained_canonical_images

    canonical_urls = {
        image.image_url for image in canonical_images
    }
    canonical_has_primary = any(
        image.is_primary for image in canonical_images
    )

    if canonical_images and not canonical_has_primary:
        min(
            canonical_images,
            key=lambda image: (image.sort_order, image.id),
        ).is_primary = True
        canonical_has_primary = True

    for sort_order, image_url in enumerate(image_urls):
        if image_url in canonical_urls:
            continue

        db.add(
            ProductImage(
                canonical_product_id=canonical_product.id,
                image_url=image_url,
                alt_text=alt_text[:255],
                is_primary=(
                    not canonical_has_primary and sort_order == 0
                ),
                sort_order=len(canonical_images) + sort_order,
            )
        )

@router.post("/{platform_code}", status_code=status.HTTP_201_CREATED)
def ingest_listing(platform_code: str, payload: ScrapedItemPayload, db: Session = Depends(get_db)):
    try:
        normalized_platform_code = platform_code.strip().lower()

        if normalized_platform_code not in {"daraz", "priceoye"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only Daraz and PriceOye ingestion is supported.",
            )

        platform = db.query(Platform).filter(
            Platform.code == normalized_platform_code
        ).first()
        if not platform:
            platform_info = {
                "priceoye": {
                    "name": "PriceOye",
                    "base_url": "https://priceoye.pk",
                },
                "daraz": {
                    "name": "Daraz",
                    "base_url": "https://daraz.pk",
                },
            }[normalized_platform_code]

            platform = Platform(
                name=platform_info["name"],
                code=normalized_platform_code,
                base_url=platform_info["base_url"],
                is_active=True,
            )
            db.add(platform)
            db.flush()

        brand = resolve_brand(db, payload)

        # 1. Search within the source marketplace for an existing listing.
        listing = db.query(ProductListing).filter(
            ProductListing.platform_id == platform.id,
            ProductListing.external_id == payload.external_id,
        ).first()

        if listing:
            # 2. Update price and stock if the product already exists
            old_price = float(listing.current_price)
            listing.current_price = Decimal(str(payload.price))
            listing.is_available = payload.is_available
            listing.title = payload.model
            listing.product_url = payload.product_url
            listing.warranty = payload.warranty
            listing.raw_payload = payload.model_dump(mode="json")
            listing.last_seen_at = datetime.now(timezone.utc)

            canonical_product = (
                listing.product_variant.canonical_product
            )
            if brand and canonical_product.brand_id is None:
                canonical_product.brand_id = brand.id
            canonical_product.specifications = (
                merged_product_specifications(
                    payload,
                    canonical_product.specifications,
                )
            )
            ram_gb, storage_gb = extract_memory_capacities(payload)
            if ram_gb is not None:
                listing.product_variant.ram_gb = ram_gb
            if storage_gb is not None:
                listing.product_variant.storage_gb = storage_gb

            sync_product_images(
                db,
                listing=listing,
                canonical_product=canonical_product,
                image_urls=payload.image_urls,
                alt_text=payload.model,
            )

            # Record a price history snapshot if the price went up or down
            if old_price != payload.price:
                history_entry = PriceHistory(
                    listing_id=listing.id,
                    price=Decimal(str(payload.price)),
                    captured_at=datetime.now(timezone.utc)
                )
                db.add(history_entry)

            db.commit()
            return {"status": "success", "action": "updated", "listing_id": listing.id}

        else:
            # 4. Ensure Category exists
            category = db.query(Category).filter(Category.slug == "smartphones").first()
            if not category:
                category = Category(
                    name="Smartphones",
                    slug="smartphones",
                    is_active=True
                )
                db.add(category)
                db.flush()

            # 5. Get or Create a Canonical Product
            # Daraz and PriceOye might have the same model name, or Daraz might have multiple items with same model.
            # Truncate to match database schema limits (model=120, name=255)
            display_name = (
                clean_product_display_name(payload.model)
                or payload.model
            )
            model_clean = display_name[:120]
            name_clean = display_name[:255]
            
            canonical = find_cross_platform_canonical(
                db,
                title=payload.model,
                brand_id=brand.id if brand else None,
                incoming_platform_id=platform.id,
            )

            if canonical is None:
                canonical_query = db.query(CanonicalProduct).filter(
                    CanonicalProduct.model == model_clean,
                )
                if brand:
                    canonical_query = canonical_query.filter(
                        CanonicalProduct.brand_id == brand.id,
                    )
                canonical = canonical_query.first()
            
            if not canonical:
                # Ensure slug uniqueness by prefixing platform code if needed, 
                # but external_id is usually unique enough. Let's use platform_code + external_id
                unique_slug = f"{normalized_platform_code}-{payload.external_id}"
                canonical = CanonicalProduct(
                    category_id=category.id,
                    brand_id=brand.id if brand else None,
                    name=name_clean,
                    slug=unique_slug,
                    model=model_clean,
                    specifications=merged_product_specifications(payload)
                )
                db.add(canonical)
                db.flush()
            else:
                canonical.specifications = merged_product_specifications(
                    payload,
                    canonical.specifications,
                )
                if brand and canonical.brand_id is None:
                    canonical.brand_id = brand.id

            # 6. Get or Create the Product Variant configuration
            # A canonical product might already have this variant
            ram_gb, storage_gb = extract_memory_capacities(payload)
            normalized_color = (
                payload.color
                if payload.color and payload.color != "N/A"
                else None
            )
            variant = db.query(ProductVariant).filter(
                ProductVariant.canonical_product_id == canonical.id,
                ProductVariant.ram_gb == ram_gb,
                ProductVariant.storage_gb == storage_gb,
                ProductVariant.color == normalized_color,
                ProductVariant.condition == "new",
            ).first()

            if not variant:
                variant = ProductVariant(
                    canonical_product_id=canonical.id,
                    color=normalized_color,
                    ram_gb=ram_gb,
                    storage_gb=storage_gb,
                    condition="new",
                    variant_attributes={"raw_variant": payload.variant}
                )
                db.add(variant)
                db.flush()

            # 7. Create the attached Product Listing for PriceOye
            new_listing = ProductListing(
                platform_id=platform.id,
                product_variant_id=variant.id,
                external_id=payload.external_id,
                title=payload.model,
                product_url=payload.product_url,
                current_price=Decimal(str(payload.price)),
                currency=payload.currency,
                warranty=payload.warranty,
                is_available=payload.is_available,
                raw_payload=payload.model_dump(mode="json")
            )
            db.add(new_listing)
            db.flush()

            sync_product_images(
                db,
                listing=new_listing,
                canonical_product=canonical,
                image_urls=payload.image_urls,
                alt_text=payload.model,
            )

            # 8. Record initial price history entry
            history_entry = PriceHistory(
                listing_id=new_listing.id,
                price=Decimal(str(payload.price)),
                captured_at=datetime.now(timezone.utc)
            )
            db.add(history_entry)
            db.commit()
            
            return {"status": "success", "action": "created", "listing_id": new_listing.id}

    except HTTPException:
        db.rollback()
        raise

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database insertion failed: {str(e)}"
        )
