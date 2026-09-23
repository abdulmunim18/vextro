"""Transactional ingestion and retrieval for marketplace reviews."""

from math import ceil

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.review_repository import ReviewRepository
from app.schemas.reviews import (
    ProductReviewsResponse,
    ReviewBatchInput,
    ReviewBatchResponse,
    ReviewIngestionItemResponse,
    ReviewResponse,
)
from app.services.review_normalization import build_review_fingerprint
from app.services.review_analysis_service import ReviewAnalysisService
from app.services.seller_trust_service import SellerTrustService


class ReviewService:
    def __init__(self, repository: ReviewRepository | None = None) -> None:
        self.repository = repository or ReviewRepository()

    def ingest_batch(
        self,
        database_session: Session,
        payload: ReviewBatchInput,
    ) -> ReviewBatchResponse:
        listing = self.repository.get_listing(
            database_session,
            platform_code=payload.platform_code,
            external_listing_id=payload.external_listing_id,
        )
        if listing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "No active marketplace listing matches the supplied "
                    "platform and external listing ID."
                ),
            )

        results: list[ReviewIngestionItemResponse] = []
        created_count = 0
        try:
            for item in payload.reviews:
                fingerprint = build_review_fingerprint(
                    platform_code=payload.platform_code,
                    listing_external_id=payload.external_listing_id,
                    external_review_id=item.external_review_id,
                    reviewer_external_id=item.reviewer_external_id,
                    reviewer_display_name=item.reviewer_display_name,
                    rating=item.rating,
                    review_text=item.review_text,
                    reviewed_at=(
                        item.reviewed_at
                        if hasattr(item.reviewed_at, "isoformat")
                        else None
                    ),
                )
                review, created = self.repository.insert_review(
                    database_session,
                    values={
                        "platform_id": listing.platform_id,
                        "product_listing_id": listing.id,
                        "seller_id": listing.seller_id,
                        "external_review_id": item.external_review_id,
                        "review_fingerprint": fingerprint,
                        "reviewer_external_id": item.reviewer_external_id,
                        "reviewer_display_name": item.reviewer_display_name,
                        "rating": item.rating,
                        "review_text": item.review_text,
                        "reviewed_at": item.reviewed_at,
                        "verified_purchase": item.verified_purchase,
                        "helpful_count": item.helpful_count,
                        "source_url": str(payload.source_url),
                        "raw_metadata": item.raw_metadata,
                    },
                )
                created_count += int(created)
                results.append(
                    ReviewIngestionItemResponse(
                        id=review.id,
                        status="created" if created else "duplicate",
                        external_review_id=review.external_review_id,
                        review_fingerprint=review.review_fingerprint,
                    )
                )
            # Keep derived evidence and its source reviews in one transaction.
            if created_count:
                ReviewAnalysisService().analyze_listing(database_session, listing.id)
                if listing.seller_id is not None:
                    SellerTrustService().recalculate(database_session, listing.seller_id)
            database_session.commit()
        except HTTPException:
            database_session.rollback()
            raise
        except Exception:
            database_session.rollback()
            raise

        return ReviewBatchResponse(
            platform_code=payload.platform_code,
            listing_id=listing.id,
            seller_id=listing.seller_id,
            created_count=created_count,
            duplicate_count=len(results) - created_count,
            items=results,
        )

    def get_product_reviews(
        self,
        database_session: Session,
        *,
        product_id: int,
        listing_id: int | None,
        page: int,
        page_size: int,
    ) -> ProductReviewsResponse:
        if self.repository.get_product(database_session, product_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Product not found",
            )
        if listing_id is not None and not self.repository.listing_belongs_to_product(
            database_session,
            listing_id=listing_id,
            product_id=product_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Listing not found for this product",
            )

        rows, total = self.repository.list_product_reviews(
            database_session,
            product_id=product_id,
            listing_id=listing_id,
            offset=(page - 1) * page_size,
            limit=page_size,
        )
        average, distribution = self.repository.get_product_rating_aggregates(
            database_session,
            product_id=product_id,
            listing_id=listing_id,
        )
        items = [
            ReviewResponse(
                id=review.id,
                platform_code=platform_code,
                product_listing_id=review.product_listing_id,
                seller_id=review.seller_id,
                external_review_id=review.external_review_id,
                review_fingerprint=review.review_fingerprint,
                reviewer_external_id=review.reviewer_external_id,
                reviewer_display_name=review.reviewer_display_name,
                rating=review.rating,
                review_text=review.review_text,
                reviewed_at=review.reviewed_at,
                verified_purchase=review.verified_purchase,
                helpful_count=review.helpful_count,
                source_url=review.source_url,
                raw_metadata=review.raw_metadata,
                created_at=review.created_at,
                updated_at=review.updated_at,
            )
            for review, platform_code in rows
        ]
        return ProductReviewsResponse(
            product_id=product_id,
            listing_id=listing_id,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
            average_rating=average,
            rating_distribution=distribution,
            items=items,
        )
