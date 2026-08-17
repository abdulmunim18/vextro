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