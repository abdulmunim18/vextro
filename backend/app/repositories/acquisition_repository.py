"""Database operations for marketplace acquisition ingestion."""

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.platform import Platform
from app.models.price_history import PriceHistory
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
        """Refresh an existing listing with the latest capture.

        Price, availability and currency always come from the fresh scrape:
        they are the facts the crawl exists to collect. Everything else is
        only overwritten when the scrape actually carried a value, because a
        parser that failed to read a seller, a rating or a discount must not
        erase one VEXTRO already holds. ``rating`` and ``review_count`` in
        particular are recomputed from stored reviews, so a listing payload
        that omits them would otherwise reset the review aggregate on every
        refresh.
        """

        listing.product_variant_id = (
            product_variant_id
        )
        listing.current_price = current_price
        listing.currency = currency
        listing.is_available = is_available
        listing.last_seen_at = scraped_at

        if seller_id is not None:
            listing.seller_id = seller_id

        if title:
            listing.title = title

        if product_url:
            listing.product_url = product_url

        if original_price is not None:
            listing.original_price = original_price
        elif (
            listing.original_price is not None
            and listing.original_price <= current_price
        ):
            # A stored list price at or below the new selling price would
            # render as a fake discount, so drop that stale baseline.
            listing.original_price = None

        if rating is not None:
            listing.rating = rating

        if review_count:
            listing.review_count = review_count

        if warranty:
            listing.warranty = warranty

        listing.raw_payload = {
            **(listing.raw_payload or {}),
            **(raw_payload or {}),
        }

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
    def get_latest_price_history(
        database_session: Session,
        *,
        listing_id: int,
    ) -> PriceHistory | None:
        """Return the newest stored observation for one listing."""

        statement = (
            select(PriceHistory)
            .where(PriceHistory.listing_id == listing_id)
            .order_by(
                PriceHistory.captured_at.desc(),
                PriceHistory.id.desc(),
            )
            .limit(1)
        )

        return database_session.scalar(statement)

    @staticmethod
    def touch_price_history(
        database_session: Session,
        price_history: PriceHistory,
        *,
        captured_at: datetime,
    ) -> PriceHistory:
        """Acknowledge a price that has not changed since it was recorded.

        Repeating an identical price is not a new data point, and the
        existing point is left exactly where it is: its timestamp is the
        moment this price began. Moving it forward on every scrape erased
        that moment, so a price that had held for a month was drawn as if
        it started today. When the offer was last confirmed is the
        listing's ``last_seen_at``, not a fact about the price point.
        """

        return price_history

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