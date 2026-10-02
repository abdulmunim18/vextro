"""Database operations for marketplace acquisition ingestion."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session, selectinload

from app.models.pending_product_match import PendingProductMatch
from app.models.platform import Platform
from app.models.price_history import PriceHistory
from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.seller import Seller


class AcquisitionRepository:
    """Provide database operations used by acquisition services."""

    @staticmethod
    def get_platform_by_code(
        database_session: Session,
        platform_code: str,
    ) -> Platform | None:
        """Return a marketplace platform by its unique code."""

        statement = select(Platform).where(
            Platform.code == platform_code,
        )

        return database_session.scalar(statement)

    @staticmethod
    def get_product_variant(
        database_session: Session,
        product_variant_id: int,
    ) -> ProductVariant | None:
        """Return a variant together with its canonical product."""

        statement = (
            select(ProductVariant)
            .options(
                selectinload(
                    ProductVariant.canonical_product,
                ),
            )
            .where(
                ProductVariant.id
                == product_variant_id,
            )
        )

        return database_session.scalar(statement)

    @staticmethod
    def get_seller(
        database_session: Session,
        *,
        platform_id: int,
        external_seller_id: str | None,
        seller_name: str,
    ) -> Seller | None:
        """Find a seller by external ID or normalized name."""

        if external_seller_id:
            statement = select(Seller).where(
                Seller.platform_id == platform_id,
                Seller.external_seller_id
                == external_seller_id,
            )

            seller = database_session.scalar(
                statement,
            )

            if seller is not None:
                return seller

        normalized_name = seller_name.strip().lower()

        statement = select(Seller).where(
            Seller.platform_id == platform_id,
            func.lower(Seller.name)
            == normalized_name,
        )

        return database_session.scalar(statement)

    @staticmethod
    def create_seller(
        database_session: Session,
        *,
        platform_id: int,
        external_seller_id: str | None,
        name: str,
        profile_url: str | None,
        rating: Decimal | None,
        review_count: int,
        is_verified: bool,
    ) -> Seller:
        """Create and flush a marketplace seller."""

        seller = Seller(
            platform_id=platform_id,
            external_seller_id=external_seller_id,
            name=name,
            profile_url=profile_url,
            rating=rating,
            review_count=review_count,
            is_verified=is_verified,
            is_active=True,
        )

        database_session.add(seller)
        database_session.flush()

        return seller

    @staticmethod
    def update_seller(
        database_session: Session,
        seller: Seller,
        *,
        external_seller_id: str | None,
        name: str,
        profile_url: str | None,
        rating: Decimal | None,
        review_count: int,
        is_verified: bool,
    ) -> Seller:
        """Refresh a seller using the latest marketplace data."""

        if external_seller_id:
            seller.external_seller_id = (
                external_seller_id
            )

        seller.name = name
        seller.profile_url = profile_url
        seller.rating = rating
        seller.review_count = review_count
        seller.is_verified = is_verified
        seller.is_active = True

        database_session.flush()

        return seller

    @staticmethod
    def get_listing(
        database_session: Session,
        *,
        platform_id: int,
        external_id: str,
    ) -> ProductListing | None:
        """Find a marketplace listing by platform and external ID."""

        statement = select(
            ProductListing,
        ).where(
            ProductListing.platform_id
            == platform_id,
            ProductListing.external_id
            == external_id,
        )

        return database_session.scalar(statement)

    @classmethod
    def find_superseded_listing(
        cls,
        database_session: Session,
        *,
        platform_id: int,
        external_id: str,
    ) -> ProductListing | None:
        """Find the coarser listing that a variant-level id replaces.

        Variant-level ids look like ``<product>--<colour>--<size>``.
        Before listings were tracked per variant, the same marketplace
        page was stored under ``<product>`` (or ``<product>--<colour>``).
        Walking the id from most to least specific returns that older
        row so the caller can re-key it instead of leaving a stale
        duplicate beside the new one.
        """

        parts = external_id.split("--")
        for length in range(len(parts) - 1, 0, -1):
            candidate = cls.get_listing(
                database_session,
                platform_id=platform_id,
                external_id="--".join(parts[:length]),
            )
            if candidate is not None:
                return candidate
        return None

    @staticmethod
    def clear_pending_matches(
        database_session: Session,
        *,
        platform_code: str,
        external_id: str,
    ) -> int:
        """Drop review-queue entries that a successful capture answers.

        An item parked for manual matching stops being work for an
        administrator once the same marketplace offer is ingested.
        Entries an administrator already resolved are kept: they are
        the record of an approved mapping, not open work.
        """

        parts = external_id.split("--")
        candidates = {
            "--".join(parts[:length])
            for length in range(1, len(parts) + 1)
        }
        result = database_session.execute(
            delete(PendingProductMatch)
            .where(
                PendingProductMatch.platform_code == platform_code,
                PendingProductMatch.external_id.in_(candidates),
                PendingProductMatch.status == "pending",
            )
            .execution_options(synchronize_session=False)
        )
        return int(result.rowcount or 0)

    @staticmethod
    def sync_listing_images(
        database_session: Session,
        *,
        listing: ProductListing,
        canonical_product_id: int,
        image_urls: list[str],
        alt_text: str,
    ) -> None:
        """Store a listing's gallery and seed the product's own images.

        The listing gallery mirrors the capture exactly. The product
        gallery only ever gains images, and only while it is empty, so
        the first variant seen gives a new phone its catalogue photo
        without later colours reshuffling it.
        """

        urls: list[str] = []
        for image_url in image_urls[:12]:
            cleaned = str(image_url).strip()
            if cleaned.startswith(("http://", "https://")) and (
                cleaned not in urls
            ):
                urls.append(cleaned)
        if not urls:
            return

        existing = {
            image.image_url: image
            for image in database_session.scalars(
                select(ProductImage).where(
                    ProductImage.listing_id == listing.id,
                )
            )
        }
        for image_url, image in existing.items():
            if image_url not in urls:
                database_session.delete(image)

        for sort_order, image_url in enumerate(urls):
            image = existing.get(image_url)
            if image is None:
                image = ProductImage(
                    listing_id=listing.id,
                    image_url=image_url,
                )
                database_session.add(image)
            image.alt_text = alt_text[:255]
            image.is_primary = sort_order == 0
            image.sort_order = sort_order

        product_has_images = database_session.scalar(
            select(func.count(ProductImage.id)).where(
                ProductImage.canonical_product_id
                == canonical_product_id,
            )
        )
        if not product_has_images:
            for sort_order, image_url in enumerate(urls):
                database_session.add(
                    ProductImage(
                        canonical_product_id=canonical_product_id,
                        image_url=image_url,
                        alt_text=alt_text[:255],
                        is_primary=sort_order == 0,
                        sort_order=sort_order,
                    )
                )

        database_session.flush()

    @staticmethod
    def mark_unseen_listings_unavailable(
        database_session: Session,
        *,
        platform_id: int,
        seen_since: datetime,
    ) -> int:
        """Flag listings a full crawl did not encounter as unavailable.

        Returns the number of rows changed. Rows are never deleted, so
        their price history stays intact.
        """

        result = database_session.execute(
            update(ProductListing)
            .where(
                ProductListing.platform_id == platform_id,
                ProductListing.last_seen_at < seen_since,
                ProductListing.is_available.is_(True),
            )
            .values(is_available=False)
            .execution_options(synchronize_session=False)
        )
        return int(result.rowcount or 0)

    @staticmethod
    def create_listing(
        database_session: Session,
        *,
        platform_id: int,
        product_variant_id: int,
        seller_id: int | None,
        external_id: str,
        title: str,
        product_url: str,
        current_price: Decimal,
        original_price: Decimal | None,
        currency: str,
        rating: Decimal | None,
        review_count: int,
        warranty: str | None,
        is_available: bool,
        raw_payload: dict[str, Any],
        scraped_at: datetime,
    ) -> ProductListing:
        """Create and flush a marketplace listing."""

        listing = ProductListing(
            platform_id=platform_id,
            product_variant_id=(
                product_variant_id
            ),
            seller_id=seller_id,
            external_id=external_id,
            title=title,
            product_url=product_url,
            current_price=current_price,
            original_price=original_price,
            currency=currency,
            rating=rating,
            review_count=review_count,
            warranty=warranty,
            is_available=is_available,
            raw_payload=raw_payload,
            first_seen_at=scraped_at,
            last_seen_at=scraped_at,
        )

        database_session.add(listing)
        database_session.flush()

        return listing

    @staticmethod
    def update_listing(
        database_session: Session,
        listing: ProductListing,
        *,
        product_variant_id: int,
        seller_id: int | None,
        title: str,
        product_url: str,
        current_price: Decimal,
        original_price: Decimal | None,
        currency: str,
        rating: Decimal | None,
        review_count: int,
        warranty: str | None,
        is_available: bool,
        raw_payload: dict[str, Any],
        scraped_at: datetime,
    ) -> ProductListing:
        """Refresh an existing listing with the latest capture."""

        listing.product_variant_id = (
            product_variant_id
        )
        listing.seller_id = seller_id
        listing.title = title
        listing.product_url = product_url
        listing.current_price = current_price
        listing.original_price = original_price
        listing.currency = currency
        listing.rating = rating
        listing.review_count = review_count
        listing.warranty = warranty
        listing.is_available = is_available
        listing.raw_payload = raw_payload
        listing.last_seen_at = scraped_at

        database_session.flush()

        return listing

    @staticmethod
    def get_price_history_capture(
        database_session: Session,
        *,
        listing_id: int,
        captured_at: datetime,
    ) -> PriceHistory | None:
        """Find an existing price capture for idempotent retries."""

        statement = select(
            PriceHistory,
        ).where(
            PriceHistory.listing_id
            == listing_id,
            PriceHistory.captured_at
            == captured_at,
        )

        return database_session.scalar(statement)

    @staticmethod
    def create_price_history(
        database_session: Session,
        *,
        listing_id: int,
        price: Decimal,
        original_price: Decimal | None,
        currency: str,
        is_available: bool,
        captured_at: datetime,
    ) -> PriceHistory:
        """Create and flush one historical marketplace price."""

        price_history = PriceHistory(
            listing_id=listing_id,
            price=price,
            original_price=original_price,
            currency=currency,
            is_available=is_available,
            source="scraper",
            captured_at=captured_at,
        )

        database_session.add(price_history)
        database_session.flush()

        return price_history