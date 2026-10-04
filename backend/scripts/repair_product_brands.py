"""Re-point catalog products at the manufacturer that actually made them.

Daraz publishes the selling store in its ``brandName`` field, so the catalog
collected brands such as "Carrefour", "OPPO Pakistan Official" and "FAYWA
TRADING (PVT) LTD". Each of those became its own brand row, which split one
phone into several canonical products — "Oppo A6K" under the store sat
beside "Oppo A6k" under Oppo — and filled the public brand filter with shops.

The script re-infers every product's brand from its own name and its current
brand value, moves the product to the correct brand, and deactivates brand
rows that end up with nothing but their store name.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import func

from app.core.database import SessionLocal
from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.seller import Seller
from app.services.smartphone_normalization import (
    infer_brand_name,
    looks_like_reseller,
    normalize_text,
)
from scripts.merge_cross_marketplace_products import (
    direct_reference_count,
    merge_product,
)


def slugify(value: str) -> str:
    """Return a compact URL-safe slug for a brand name."""

    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "brand"


def get_or_create_brand(database_session, name: str, created: list[str]):
    """Resolve a brand case-insensitively, creating it only when new."""

    existing = (
        database_session.query(Brand)
        .filter(Brand.name.ilike(name))
        .order_by(Brand.id)
        .first()
    )

    if existing is not None:
        if not existing.is_active:
            existing.is_active = True
        return existing

    slug_base = slugify(name)
    slug = slug_base
    suffix = 2

    while (
        database_session.query(Brand).filter(Brand.slug == slug).first()
        is not None
    ):
        slug = f"{slug_base}-{suffix}"
        suffix += 1

    brand = Brand(name=name[:120], slug=slug, is_active=True)
    database_session.add(brand)
    database_session.flush()
    created.append(name)

    return brand


def run(*, apply_changes: bool) -> dict[str, object]:
    database_session = SessionLocal()
    moved: list[str] = []
    cleared: list[str] = []
    created: list[str] = []
    merged: list[str] = []
    blocked: list[str] = []

    try:
        products = (
            database_session.query(CanonicalProduct)
            .order_by(CanonicalProduct.id)
            .all()
        )
        brands = {
            brand.id: brand
            for brand in database_session.query(Brand).all()
        }

        for product in products:
            current = brands.get(product.brand_id)
            current_name = current.name if current is not None else None

            resolved = infer_brand_name(product.name, current_name)

            if resolved is None:
                # Nothing but a shop name: better no brand than a fake one.
                if product.brand_id is not None:
                    cleared.append(
                        f"{product.id} {product.name[:48]!r} "
                        f"({current_name} -> none)"
                    )
                    product.brand_id = None
                continue

            if current_name is not None and resolved.lower() == (
                current_name.lower()
            ):
                continue

            brand = get_or_create_brand(database_session, resolved, created)

            if brand.id == product.brand_id:
                continue

            # The store-named brand is exactly what split one phone into
            # several products, so the real brand often already holds this
            # model. Moving the row would collide with it; merging is what
            # the data actually needs.
            twin = (
                database_session.query(CanonicalProduct)
                .filter(
                    CanonicalProduct.brand_id == brand.id,
                    func.lower(CanonicalProduct.model)
                    == (product.model or "").lower(),
                    CanonicalProduct.id != product.id,
                )
                .order_by(CanonicalProduct.id)
                .first()
            )

            if twin is not None:
                if direct_reference_count(database_session, product.id):
                    blocked.append(
                        f"{product.id} {product.name[:48]!r} duplicates "
                        f"{twin.id}; kept (business data references it)"
                    )
                    continue

                merge_product(database_session, twin, product)
                merged.append(
                    f"{product.id} -> {twin.id} {product.name[:48]!r} "
                    f"({current_name} -> {brand.name})"
                )
                database_session.flush()
                continue

            moved.append(
                f"{product.id} {product.name[:48]!r} "
                f"({current_name} -> {brand.name})"
            )
            product.brand_id = brand.id
            brands[brand.id] = brand
            database_session.flush()

        # A brand with no products left is a leftover. Whether it is a shop
        # rather than a manufacturer is decided by the marketplace's own
        # seller records, not by guessing from the name: a brand nobody
        # makes phones under, which a marketplace seller is named after,
        # is that seller.
        seller_keys = {
            normalize_text(name)
            for (name,) in database_session.query(Seller.name).all()
            if name
        }
        seller_keys.discard("")

        retired: list[str] = []
        for brand in database_session.query(Brand).order_by(Brand.id).all():
            if not brand.is_active:
                continue

            product_count = (
                database_session.query(CanonicalProduct)
                .filter(CanonicalProduct.brand_id == brand.id)
                .count()
            )

            if product_count:
                continue

            brand_key = normalize_text(brand.name)

            is_seller_name = any(
                seller_key == brand_key
                or seller_key.startswith(f"{brand_key} ")
                for seller_key in seller_keys
            )

            if (
                is_seller_name
                or looks_like_reseller(brand.name)
                or infer_brand_name(brand.name, brand.name) != brand.name
            ):
                brand.is_active = False
                retired.append(f"{brand.id} {brand.name}")

        if apply_changes:
            database_session.commit()
        else:
            database_session.rollback()

        return {
            "products": len(products),
            "moved": moved,
            "merged": merged,
            "cleared": cleared,
            "created": created,
            "retired": retired,
            "blocked": blocked,
        }
    except Exception:
        database_session.rollback()
        raise
    finally:
        database_session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Replace seller names in catalog brands with makers.",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print every product that changes brand.",
    )
    args = parser.parse_args()

    result = run(apply_changes=args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(
        f"[{mode}] products={result['products']} "
        f"moved={len(result['moved'])} merged={len(result['merged'])} "
        f"cleared={len(result['cleared'])} "
        f"brands_created={len(result['created'])} "
        f"brands_retired={len(result['retired'])} "
        f"blocked={len(result['blocked'])}"
    )

    if args.verbose:
        for line in result["moved"]:
            print(f"MOVED {line}")
        for line in result["merged"]:
            print(f"MERGED {line}")
        for line in result["cleared"]:
            print(f"CLEARED {line}")
        for line in result["retired"]:
            print(f"RETIRED BRAND {line}")
    for line in result["blocked"]:
        print(f"BLOCKED {line}")


if __name__ == "__main__":
    main()
