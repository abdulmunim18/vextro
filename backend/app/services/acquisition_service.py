"""Business logic for marketplace acquisition ingestion."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.acquisition_repository import (
    AcquisitionRepository,
)
from app.schemas.acquisition import (
    AcquisitionListingInput,
    AcquisitionListingResponse,
)
from app.services.price_alert_service import (
    evaluate_price_alerts_for_capture,
)

class AcquisitionService:
    """Process normalized marketplace listing captures."""

    def __init__(
        self,
        repository: AcquisitionRepository | None = None,
    ) -> None:
        self.repository = (
            repository or AcquisitionRepository()
        )

    def ingest_listing(
        self,
        database_session: Session,
        payload: AcquisitionListingInput,
    ) -> AcquisitionListingResponse:
        """Create or update a listing and save its price capture."""

        platform = self.repository.get_platform_by_code(
            database_session,
            payload.platform_code,
        )

        if platform is None or not platform.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "The requested marketplace platform "
                    "was not found or is inactive."
                ),
            )

        product_variant = (
            self.repository.get_product_variant(
                database_session,
                payload.product_variant_id,
            )
        )

        if product_variant is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The requested product variant was not found.",
            )

        canonical_product = (
            product_variant.canonical_product
        )

        if (
            not product_variant.is_active
            or canonical_product is None
            or not canonical_product.is_active
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "The requested product or variant "
                    "is inactive."
                ),
            )

        if payload.currency != "PKR":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Only PKR currency is currently supported.",
            )

        existing_listing = (
            self.repository.get_listing(
                database_session,
                platform_id=platform.id,
                external_id=payload.external_id,
            )
        )

        if existing_listing is not None:
            existing_capture = (
                self.repository.get_price_history_capture(
                    database_session,
                    listing_id=existing_listing.id,
                    captured_at=payload.scraped_at,
                )
            )

            if existing_capture is not None:
                return AcquisitionListingResponse(
                    status="duplicate",
                    platform_code=payload.platform_code,
                    listing_id=existing_listing.id,
                    seller_id=existing_listing.seller_id,
                    price_history_id=existing_capture.id,
                    listing_created=False,
                    seller_created=False,
                    price_history_created=False,
                    alerts_triggered=0,
                    captured_at=existing_capture.captured_at,
                )

        seller = None
        seller_created = False

        try:
            if payload.seller is not None:
                seller = self.repository.get_seller(
                    database_session,
                    platform_id=platform.id,
                    external_seller_id=(
                        payload.seller.external_seller_id
                    ),
                    seller_name=payload.seller.name,
                )

                profile_url = (
                    str(payload.seller.profile_url)
                    if payload.seller.profile_url
                    else None
                )

                if seller is None:
                    seller = self.repository.create_seller(
                        database_session,
                        platform_id=platform.id,
                        external_seller_id=(
                            payload.seller.external_seller_id
                        ),
                        name=payload.seller.name,
                        profile_url=profile_url,
                        rating=payload.seller.rating,
                        review_count=(
                            payload.seller.review_count
                        ),
                        is_verified=(
                            payload.seller.is_verified
                        ),
                    )

                    seller_created = True
                else:
                    seller = self.repository.update_seller(
                        database_session,
                        seller,
                        external_seller_id=(
                            payload.seller.external_seller_id
                        ),
                        name=payload.seller.name,
                        profile_url=profile_url,
                        rating=payload.seller.rating,
                        review_count=(
                            payload.seller.review_count
                        ),
                        is_verified=(
                            payload.seller.is_verified
                        ),
                    )

            seller_id = (
                seller.id
                if seller is not None
                else None
            )

            listing_created = (
                existing_listing is None
            )

            if existing_listing is None:
                listing = self.repository.create_listing(
                    database_session,
                    platform_id=platform.id,
                    product_variant_id=(
                        payload.product_variant_id
                    ),
                    seller_id=seller_id,
                    external_id=payload.external_id,
                    title=payload.title,
                    product_url=str(
                        payload.product_url,
                    ),
                    current_price=payload.current_price,
                    original_price=(
                        payload.original_price
                    ),
                    currency=payload.currency,
                    rating=payload.rating,
                    review_count=payload.review_count,
                    warranty=payload.warranty,
                    is_available=payload.is_available,
                    raw_payload=payload.raw_payload,
                    scraped_at=payload.scraped_at,
                )
            else:
                listing = self.repository.update_listing(
                    database_session,
                    existing_listing,
                    product_variant_id=(
                        payload.product_variant_id
                    ),
                    seller_id=seller_id,
                    title=payload.title,
                    product_url=str(
                        payload.product_url,
                    ),
                    current_price=payload.current_price,
                    original_price=(
                        payload.original_price
                    ),
                    currency=payload.currency,
                    rating=payload.rating,
                    review_count=payload.review_count,
                    warranty=payload.warranty,
                    is_available=payload.is_available,
                    raw_payload=payload.raw_payload,
                    scraped_at=payload.scraped_at,
                )

            price_history = (
                self.repository.create_price_history(
                    database_session,
                    listing_id=listing.id,
                    price=payload.current_price,
                    original_price=(
                        payload.original_price
                    ),
                    currency=payload.currency,
                    is_available=payload.is_available,
                    captured_at=payload.scraped_at,
                )
            )

            alerts_triggered = evaluate_price_alerts_for_capture(
                database_session,
                canonical_product_id=canonical_product.id,
                listing_id=listing.id,
                current_price=payload.current_price,
                currency=payload.currency,
            )

            database_session.commit()

            database_session.refresh(listing)
            database_session.refresh(price_history)

            if seller is not None:
                database_session.refresh(seller)

            return AcquisitionListingResponse(
                status=(
                    "created"
                    if listing_created
                    else "updated"
                ),
                platform_code=payload.platform_code,
                listing_id=listing.id,
                seller_id=(
                    seller.id
                    if seller is not None
                    else None
                ),
                price_history_id=price_history.id,
                listing_created=listing_created,
                seller_created=seller_created,
                price_history_created=True,
                alerts_triggered=alerts_triggered,
                captured_at=price_history.captured_at,
            )

        except HTTPException:
            database_session.rollback()
            raise

        except Exception:
            database_session.rollback()
            raise