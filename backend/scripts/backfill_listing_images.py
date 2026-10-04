from __future__ import annotations

import argparse
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.services.product_image_service import sync_product_images


MAX_GALLERY_SIZE = 12


def gallery_urls(listing: ProductListing) -> list[str]:
    """Return the gallery the scraper already captured for one listing.

    Acquisition stored the marketplace gallery inside ``raw_payload`` long
    before it persisted product images, so existing listings can be given
    their pictures without waiting for another crawl.
    """

    raw_payload = listing.raw_payload or {}
    raw_images = raw_payload.get("image_urls")

    if not isinstance(raw_images, (list, tuple)):
        return []

    image_urls: list[str] = []

    for raw_url in raw_images:
        if not isinstance(raw_url, str):
            continue

        image_url = raw_url.strip()[:1000]

        if not image_url.startswith(("http://", "https://")):
            continue

        if image_url not in image_urls:
            image_urls.append(image_url)

    return image_urls[:MAX_GALLERY_SIZE]


def run(*, apply_changes: bool) -> tuple[int, int, int]:
    """Create listing and canonical images from stored scraper payloads."""

    database_session = SessionLocal()
    restored = 0
    still_missing = 0

    try:
        listings = (
            database_session.query(ProductListing)
            .outerjoin(
                ProductImage,
                ProductImage.listing_id == ProductListing.id,
            )
            .filter(ProductImage.id.is_(None))
            .order_by(ProductListing.id)
            .all()
        )

        for listing in listings:
            image_urls = gallery_urls(listing)

            if not image_urls:
                still_missing += 1
                continue

            variant = database_session.get(
                ProductVariant,
                listing.product_variant_id,
            )
            canonical_product = (
                variant.canonical_product if variant is not None else None
            )

            if canonical_product is None:
                still_missing += 1
                continue

            sync_product_images(
                database_session,
                listing=listing,
                canonical_product=canonical_product,
                image_urls=image_urls,
                alt_text=listing.title,
            )
            restored += 1

        if apply_changes:
            database_session.commit()
        else:
            database_session.rollback()

        return len(listings), restored, still_missing
    except Exception:
        database_session.rollback()
        raise
    finally:
        database_session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild product images from galleries already captured in "
            "listing scrape payloads."
        ),
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    total, restored, still_missing = run(apply_changes=args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(
        f"[{mode}] listings_without_images={total} restored={restored} "
        f"still_missing={still_missing}"
    )


if __name__ == "__main__":
    main()
