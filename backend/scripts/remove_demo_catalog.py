"""Remove only the catalog artifacts created by ``seed_demo_catalog.py``.

The default mode is a dry run; pass ``--apply`` to commit.

How demo data is told apart from real data
------------------------------------------
Every record the demo seeder writes carries a marker it alone produces. The
cleanup only ever touches records matching one of these, and never deletes by
shape, age or guesswork:

1. ``canonical_products.slug`` is one of the five exact demo slugs.
2. ``product_listings.external_id`` starts with ``daraz-demo-`` or
   ``priceoye-demo-``, or its ``raw_payload`` says ``demo: true`` /
   ``source: "vextro_demo_seed"``.
3. ``price_history.source`` is ``demo_seed``.
4. ``sellers.external_seller_id`` is one of the two demo seller IDs.
5. ``product_images.image_url`` points at ``placehold.co``.
6. ``product_listings.external_id`` starts with ``NOTIFICATION-E2E-`` - an
   end-to-end test artifact, removed only with ``--include-test-listings``.

Why real data survives
----------------------
Because only demo products existed when crawling began, genuine Daraz and
PriceOye listings were matched onto demo variants. Deleting those canonical
products would cascade into real listings, real price history and real
reviews, so a demo product that still carries any non-demo listing is kept
and simply de-branded (its ``-demo`` slug suffix and demo blurb are dropped).

User price alerts cascade from both canonical products and listings. Anything
a live alert points at is preserved and reported rather than deleted, unless
``--force-drop-alerts`` says otherwise.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.database import SessionLocal
from app.models.canonical_product import CanonicalProduct
from app.models.competitor_watchlist import CompetitorWatchlist
from app.models.price_alert import PriceAlert
from app.models.price_history import PriceHistory
from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.raw_review import RawReview
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
TEST_EXTERNAL_PREFIXES = ("NOTIFICATION-E2E-",)
DEMO_PRICE_HISTORY_SOURCE = "demo_seed"
DEMO_IMAGE_HOST = "placehold.co"


@dataclass
class CleanupReport:
    """What the cleanup removed, kept, and refused to touch."""

    listings_deleted: int = 0
    price_history_deleted: int = 0
    reviews_deleted: int = 0
    images_deleted: int = 0
    products_deleted: int = 0
    products_preserved: int = 0
    sellers_deleted: int = 0
    test_listings_deleted: int = 0
    deleted_listing_labels: list[str] = field(default_factory=list)
    deleted_product_slugs: list[str] = field(default_factory=list)
    preserved_product_slugs: list[str] = field(default_factory=list)
    blocked_by_alerts: list[str] = field(default_factory=list)
    ambiguous: list[str] = field(default_factory=list)

    def as_counts(self) -> dict[str, int]:
        return {
            "listings_deleted": self.listings_deleted,
            "test_listings_deleted": self.test_listings_deleted,
            "price_history_deleted": self.price_history_deleted,
            "reviews_deleted": self.reviews_deleted,
            "images_deleted": self.images_deleted,
            "products_deleted": self.products_deleted,
            "products_preserved": self.products_preserved,
            "sellers_deleted": self.sellers_deleted,
        }


def is_demo_listing(listing: ProductListing) -> bool:
    """Report whether one listing was written by the demo seeder."""

    payload = listing.raw_payload or {}

    return bool(
        payload.get("demo") is True
        or payload.get("source") == "vextro_demo_seed"
        or listing.external_id.startswith(DEMO_EXTERNAL_PREFIXES)
    )


def is_test_listing(listing: ProductListing) -> bool:
    """Report whether one listing is an automated-test artifact."""

    return listing.external_id.startswith(TEST_EXTERNAL_PREFIXES)


def _listing_label(listing: ProductListing) -> str:
    return f"listing#{listing.id} {listing.external_id}"


def _count(session: Session, column, listing_ids: list[int]) -> int:
    """Count rows in a child table belonging to the given listings."""

    if not listing_ids:
        return 0

    return int(
        session.scalar(
            select(func.count()).where(column.in_(listing_ids))
        )
        or 0
    )


def _alert_holders(
    session: Session,
    *,
    listing_ids: list[int],
    product_ids: list[int],
) -> tuple[set[int], set[int]]:
    """Return which listings and products a live price alert points at."""

    alerted_listings: set[int] = set()
    alerted_products: set[int] = set()

    if listing_ids:
        alerted_listings = {
            row[0]
            for row in session.execute(
                select(PriceAlert.listing_id).where(
                    PriceAlert.listing_id.in_(listing_ids)
                )
            )
            if row[0] is not None
        }

    if product_ids:
        alerted_products = {
            row[0]
            for row in session.execute(
                select(PriceAlert.canonical_product_id).where(
                    PriceAlert.canonical_product_id.in_(product_ids)
                )
            )
            if row[0] is not None
        }

    return alerted_listings, alerted_products


def _collect_demo_listings(
    session: Session,
    *,
    include_test_listings: bool,
) -> tuple[list[ProductListing], list[ProductListing]]:
    """Return ``(demo_listings, test_listings)`` across the whole database.

    Demo listings are found by their own markers rather than by walking the
    demo products, because a demo listing can be attached to any variant.
    """

    listings = list(session.scalars(select(ProductListing)).all())

    demo_listings = [
        listing for listing in listings if is_demo_listing(listing)
    ]
    test_listings = (
        [listing for listing in listings if is_test_listing(listing)]
        if include_test_listings
        else []
    )

    return demo_listings, test_listings


def remove_demo_catalog(
    *,
    apply_changes: bool,
    include_test_listings: bool = False,
    force_drop_alerts: bool = False,
) -> CleanupReport:
    """Delete demo catalog records, preserving everything genuine."""

    session = SessionLocal()
    report = CleanupReport()

    try:
        demo_products = list(
            session.scalars(
                select(CanonicalProduct)
                .options(
                    selectinload(CanonicalProduct.variants),
                    selectinload(CanonicalProduct.images),
                )
                .where(CanonicalProduct.slug.in_(DEMO_PRODUCT_SLUGS))
            ).all()
        )
        demo_listings, test_listings = _collect_demo_listings(
            session,
            include_test_listings=include_test_listings,
        )

        product_ids = [product.id for product in demo_products]
        removable = demo_listings + test_listings
        alerted_listings, alerted_products = _alert_holders(
            session,
            listing_ids=[listing.id for listing in removable],
            product_ids=product_ids,
        )

        # 1. Remove demo listings. Price history, reviews and images cascade
        # from the listing, so they are counted before the delete.
        deletable_listings = []

        for listing in removable:
            if listing.id in alerted_listings and not force_drop_alerts:
                report.blocked_by_alerts.append(
                    f"{_listing_label(listing)} (a user price alert "
                    f"watches it)"
                )
                continue

            deletable_listings.append(listing)

        deletable_ids = [listing.id for listing in deletable_listings]
        report.price_history_deleted += _count(
            session,
            PriceHistory.listing_id,
            deletable_ids,
        )
        report.reviews_deleted += _count(
            session,
            RawReview.product_listing_id,
            deletable_ids,
        )
        report.images_deleted += _count(
            session,
            ProductImage.listing_id,
            deletable_ids,
        )
        watchlist_references = _count(
            session,
            CompetitorWatchlist.listing_id,
            deletable_ids,
        )

        if watchlist_references:
            report.ambiguous.append(
                f"{watchlist_references} SME competitor watchlist "
                "entries reference demo listings and will be removed "
                "with them."
            )

        for listing in deletable_listings:
            if is_test_listing(listing) and not is_demo_listing(listing):
                report.test_listings_deleted += 1
            else:
                report.listings_deleted += 1

            report.deleted_listing_labels.append(_listing_label(listing))
            session.delete(listing)

        session.flush()

        # 2. Remove demo price history still attached to surviving listings.
        remaining_demo_history = list(
            session.scalars(
                select(PriceHistory).where(
                    PriceHistory.source == DEMO_PRICE_HISTORY_SOURCE
                )
            ).all()
        )

        for point in remaining_demo_history:
            report.price_history_deleted += 1
            session.delete(point)

        # 3. Remove demo placeholder imagery wherever it was attached.
        placeholder_images = list(
            session.scalars(
                select(ProductImage).where(
                    ProductImage.image_url.contains(DEMO_IMAGE_HOST)
                )
            ).all()
        )

        for image in placeholder_images:
            report.images_deleted += 1
            session.delete(image)

        session.flush()

        # 4. A demo product that still carries genuine listings is kept and
        # de-branded; only an empty one is deleted.
        for product in demo_products:
            remaining_listing = session.scalar(
                select(ProductListing.id)
                .join(
                    ProductVariant,
                    ProductListing.product_variant_id == ProductVariant.id,
                )
                .where(ProductVariant.canonical_product_id == product.id)
                .limit(1)
            )

            if remaining_listing is not None:
                report.products_preserved += 1
                report.preserved_product_slugs.append(product.slug)
                _debrand_product(session, product)
                continue

            if product.id in alerted_products and not force_drop_alerts:
                # Deliberately left branded: the demo slug is how a later
                # run (with --force-drop-alerts) still finds this product.
                report.products_preserved += 1
                report.blocked_by_alerts.append(
                    f"product#{product.id} {product.slug} (a user price "
                    f"alert watches it)"
                )
                continue

            report.products_deleted += 1
            report.deleted_product_slugs.append(product.slug)
            session.execute(
                delete(CanonicalProduct)
                .where(CanonicalProduct.id == product.id)
                .execution_options(synchronize_session=False)
            )

        session.flush()

        # 5. Remove demo sellers once nothing of theirs remains.
        for seller in session.scalars(
            select(Seller)
            .options(selectinload(Seller.listings))
            .where(Seller.external_seller_id.in_(DEMO_SELLER_IDS))
        ).all():
            if seller.listings:
                report.ambiguous.append(
                    f"seller#{seller.id} {seller.external_seller_id} still "
                    "has listings and was preserved."
                )
                continue

            report.sellers_deleted += 1
            session.delete(seller)

        if apply_changes:
            session.commit()
        else:
            session.rollback()

        return report
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _debrand_product(
    session: Session,
    product: CanonicalProduct,
) -> None:
    """Strip demo branding from a product that holds genuine listings."""

    clean_slug = product.slug.removesuffix("-demo")

    slug_conflict = session.scalar(
        select(CanonicalProduct.id).where(
            CanonicalProduct.slug == clean_slug,
            CanonicalProduct.id != product.id,
        )
    )

    if slug_conflict is None and clean_slug:
        product.slug = clean_slug

    if product.description and "demo product" in product.description.lower():
        product.description = None


def _print_report(report: CleanupReport, *, mode: str) -> None:
    print(f"Demo catalog cleanup: {mode}")

    for label, value in report.as_counts().items():
        print(f"{label}: {value}")

    for title, entries in (
        ("Deleted listings", report.deleted_listing_labels),
        ("Deleted products", report.deleted_product_slugs),
        ("Preserved products (hold genuine listings)",
         report.preserved_product_slugs),
        ("Preserved because a user alert depends on them",
         report.blocked_by_alerts),
        ("Needs a human decision", report.ambiguous),
    ):
        if not entries:
            continue

        print(f"\n{title}:")
        for entry in entries[:50]:
            print(f"  - {entry}")

        if len(entries) > 50:
            print(f"  ... and {len(entries) - 50} more")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Remove seeded demo catalog data, preserving genuine scraped "
            "listings, price history, reviews and user alerts."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the cleanup. Without this flag the script rolls back.",
    )
    parser.add_argument(
        "--include-test-listings",
        action="store_true",
        help=(
            "Also remove automated-test listings "
            "(external IDs starting with NOTIFICATION-E2E-)."
        ),
    )
    parser.add_argument(
        "--force-drop-alerts",
        action="store_true",
        help=(
            "Delete demo records even when a user price alert points at "
            "them. Those alerts are removed by the database cascade."
        ),
    )
    args = parser.parse_args()

    report = remove_demo_catalog(
        apply_changes=args.apply,
        include_test_listings=args.include_test_listings,
        force_drop_alerts=args.force_drop_alerts,
    )
    _print_report(
        report,
        mode="APPLIED" if args.apply else "DRY RUN",
    )


if __name__ == "__main__":
    main()
