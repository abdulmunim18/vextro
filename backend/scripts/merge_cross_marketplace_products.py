from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.models.business_product import BusinessProduct
from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.notification import Notification
from app.models.price_alert import PriceAlert
from app.models.price_forecast import PriceForecast
from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.services.cross_marketplace_matching import cross_marketplace_product_key


def platform_ids(database_session, product_id: int) -> set[int]:
    rows = (
        database_session.query(ProductListing.platform_id)
        .join(
            ProductVariant,
            ProductVariant.id == ProductListing.product_variant_id,
        )
        .filter(ProductVariant.canonical_product_id == product_id)
        .distinct()
        .all()
    )
    return {row[0] for row in rows}


def direct_reference_count(database_session, product_id: int) -> int:
    return sum((
        database_session.query(BusinessProduct).filter(
            BusinessProduct.canonical_product_id == product_id
        ).count(),
        database_session.query(Notification).filter(
            Notification.canonical_product_id == product_id
        ).count(),
        database_session.query(PriceAlert).filter(
            PriceAlert.canonical_product_id == product_id
        ).count(),
    ))


def merge_product(database_session, target, source) -> None:
    target.specifications = {
        **(source.specifications or {}),
        **(target.specifications or {}),
    }
    if not target.description and source.description:
        target.description = source.description

    target_images = database_session.query(ProductImage).filter(
        ProductImage.canonical_product_id == target.id
    ).all()
    target_urls = {image.image_url for image in target_images}
    target_has_primary = any(image.is_primary for image in target_images)

    source_images = database_session.query(ProductImage).filter(
        ProductImage.canonical_product_id == source.id
    ).all()
    for image in source_images:
        if image.image_url in target_urls:
            database_session.delete(image)
            continue
        image.canonical_product_id = target.id
        if target_has_primary:
            image.is_primary = False
        elif image.is_primary:
            target_has_primary = True
        target_urls.add(image.image_url)

    source_variants = database_session.query(ProductVariant).filter(
        ProductVariant.canonical_product_id == source.id
    ).all()
    for source_variant in source_variants:
        target_variant = database_session.query(ProductVariant).filter(
            ProductVariant.canonical_product_id == target.id,
            ProductVariant.ram_gb == source_variant.ram_gb,
            ProductVariant.storage_gb == source_variant.storage_gb,
            ProductVariant.color == source_variant.color,
            ProductVariant.condition == source_variant.condition,
        ).first()

        if target_variant is None:
            source_variant.canonical_product_id = target.id
            continue

        database_session.query(ProductListing).filter(
            ProductListing.product_variant_id == source_variant.id
        ).update(
            {ProductListing.product_variant_id: target_variant.id},
            synchronize_session=False,
        )
        database_session.query(PriceForecast).filter(
            PriceForecast.product_variant_id == source_variant.id
        ).update(
            {PriceForecast.product_variant_id: target_variant.id},
            synchronize_session=False,
        )
        database_session.delete(source_variant)

    database_session.flush()
    database_session.delete(source)


def run(*, apply_changes: bool) -> tuple[int, int, list[str]]:
    database_session = SessionLocal()
    merged = 0
    blocked: list[str] = []

    try:
        products = database_session.query(CanonicalProduct).filter(
            CanonicalProduct.is_active.is_(True)
        ).order_by(CanonicalProduct.id).all()
        grouped = defaultdict(list)
        brand_names = dict(database_session.query(Brand.id, Brand.name).all())

        for product in products:
            identity = cross_marketplace_product_key(
                product.name,
                brand_names.get(product.brand_id),
            )
            if identity and product.brand_id is not None:
                grouped[(product.brand_id, identity)].append(product)

        for (_, identity), candidates in grouped.items():
            if len(candidates) < 2:
                continue

            product_platforms = {
                product.id: platform_ids(database_session, product.id)
                for product in candidates
            }
            all_platforms = set().union(*product_platforms.values())
            if len(all_platforms) < 2:
                continue

            target = min(
                candidates,
                key=lambda product: (
                    -len(product_platforms[product.id]),
                    product.id,
                ),
            )

            for source in candidates:
                if source.id == target.id:
                    continue
                if direct_reference_count(database_session, source.id):
                    blocked.append(
                        f"{source.id}->{target.id} {identity}: direct references"
                    )
                    continue
                merge_product(database_session, target, source)
                merged += 1

        if apply_changes:
            database_session.commit()
        else:
            database_session.rollback()

        return len(products), merged, blocked
    except Exception:
        database_session.rollback()
        raise
    finally:
        database_session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge unambiguous Daraz/PriceOye product duplicates.",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    total, merged, blocked = run(apply_changes=args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"[{mode}] products={total} merges={merged} blocked={len(blocked)}")
    for item in blocked:
        print(f"BLOCKED {item}")


if __name__ == "__main__":
    main()
