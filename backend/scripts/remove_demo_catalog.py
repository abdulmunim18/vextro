"""Remove only catalog artifacts created by ``seed_demo_catalog.py``.

The default mode is a dry run. Use ``--apply`` to commit. Dedicated demo login
accounts and SME workspaces are intentionally preserved for local evaluation.
"""

from __future__ import annotations

import argparse

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.core.database import SessionLocal
from app.models.canonical_product import CanonicalProduct
from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.seller import Seller


DEMO_PRODUCT_SLUGS = {
    "samsung-galaxy-a55-5g-demo",
    "apple-iphone-15-demo",
    "xiaomi-redmi-note-13-pro-demo",
    "infinix-note-40-pro-demo",
    "tecno-camon-30-demo",
}
DEMO_SELLER_IDS = {
    "vextro-daraz-demo-seller",
    "vextro-priceoye-demo-seller",
}
DEMO_EXTERNAL_PREFIXES = (
    "daraz-demo-",
    "priceoye-demo-",
)


def is_demo_listing(listing: ProductListing) -> bool:
    payload = listing.raw_payload or {}
    return bool(
        payload.get("demo") is True
        or payload.get("source") == "vextro_demo_seed"
        or listing.external_id.startswith(DEMO_EXTERNAL_PREFIXES)
    )


def remove_demo_catalog(*, apply_changes: bool) -> dict[str, int]:
    session = SessionLocal()
    counts = {
        "listings": 0,
        "products": 0,
        "images": 0,
        "sellers": 0,
        "preserved_products": 0,
    }

    try:
        products = list(
            session.scalars(
                select(CanonicalProduct)
                .options(
                    selectinload(CanonicalProduct.variants).selectinload(
                        ProductVariant.listings
                    ),
                    selectinload(CanonicalProduct.images),
                )
                .where(CanonicalProduct.slug.in_(DEMO_PRODUCT_SLUGS))
            ).all()
        )

        for product in products:
            for variant in product.variants:
                for listing in list(variant.listings):
                    if is_demo_listing(listing):
                        session.delete(listing)
                        counts["listings"] += 1

            for image in list(product.images):
                if "placehold.co" in image.image_url:
                    session.delete(image)
                    counts["images"] += 1

        session.flush()

        for product in products:
            remaining_listing = session.scalar(
                select(ProductListing.id)
                .join(
                    ProductVariant,
                    ProductListing.product_variant_id == ProductVariant.id,
                )
                .where(ProductVariant.canonical_product_id == product.id)
                .limit(1)
            )
            if remaining_listing is None:
                session.execute(
                    delete(CanonicalProduct)
                    .where(CanonicalProduct.id == product.id)
                    .execution_options(synchronize_session=False)
                )
                counts["products"] += 1
                continue

            clean_slug = product.slug.removesuffix("-demo")
            slug_conflict = session.scalar(
                select(CanonicalProduct.id).where(
                    CanonicalProduct.slug == clean_slug,
                    CanonicalProduct.id != product.id,
                )
            )
            if slug_conflict is None:
                product.slug = clean_slug
            if product.description and "demo product" in product.description.lower():
                product.description = None
            counts["preserved_products"] += 1

        session.flush()

        sellers = list(
            session.scalars(
                select(Seller)
                .options(selectinload(Seller.listings))
                .where(Seller.external_seller_id.in_(DEMO_SELLER_IDS))
            ).all()
        )
        for seller in sellers:
            if not seller.listings:
                session.delete(seller)
                counts["sellers"] += 1

        if apply_changes:
            session.commit()
        else:
            session.rollback()
        return counts
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the cleanup. Without this flag the script rolls back.",
    )
    args = parser.parse_args()
    counts = remove_demo_catalog(apply_changes=args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(f"Demo catalog cleanup: {mode}")
    for label, value in counts.items():
        print(f"{label}: {value}")


if __name__ == "__main__":
    main()
