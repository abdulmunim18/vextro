"""Transactional orchestration of review-risk analysis and API aggregates."""

from math import ceil

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.raw_review import RawReview
from app.models.review_analysis import ReviewAnalysis
from app.repositories.review_analysis_repository import ReviewAnalysisRepository
from app.repositories.review_repository import ReviewRepository
from app.schemas.review_analysis import ProductReviewAnalysisResponse, ReviewAnalysisResponse
from app.services.review_risk_engine import VERSION, analyze_review


class ReviewAnalysisService:
    def __init__(self) -> None:
        self.repository = ReviewAnalysisRepository()

    def analyze_listing(self, session: Session, listing_id: int) -> int:
        reviews = self.repository.listing_reviews(session, listing_id)
        for review in reviews:
            self.repository.upsert(session, review.id, analyze_review(review, reviews))
        return len(reviews)

    def analyze_one(self, session: Session, review_id: int) -> ReviewAnalysis:
        review = session.get(RawReview, review_id)
        if review is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Review not found")
        peers = self.repository.listing_reviews(session, review.product_listing_id)
        self.repository.upsert(session, review_id, analyze_review(review, peers))
        session.flush()
        result = self.repository.review_result(session, review_id, VERSION)
        assert result is not None
        return result

    @staticmethod
    def as_response(review: RawReview, analysis: ReviewAnalysis) -> ReviewAnalysisResponse:
        return ReviewAnalysisResponse(
            review_id=review.id, listing_id=review.product_listing_id,
            analysis_version=analysis.analysis_version,
            suspicion_score=analysis.suspicion_score, suspicion_level=analysis.suspicion_level,
            duplicate_similarity_score=analysis.duplicate_similarity_score,
            text_anomaly_score=analysis.text_anomaly_score,
            rating_anomaly_score=analysis.rating_anomaly_score,
            temporal_anomaly_score=analysis.temporal_anomaly_score,
            reviewer_anomaly_score=analysis.reviewer_anomaly_score,
            is_exact_duplicate=analysis.is_exact_duplicate, is_near_duplicate=analysis.is_near_duplicate,
            signals=analysis.signals, reasons=analysis.reasons, analyzed_at=analysis.analyzed_at,
        )

    def product_summary(self, session: Session, *, product_id: int, listing_id: int | None, page: int, page_size: int) -> ProductReviewAnalysisResponse:
        review_repository = ReviewRepository()
        if review_repository.get_product(session, product_id) is None:
            raise HTTPException(status_code=404, detail="Product not found")
        if listing_id is not None and not review_repository.listing_belongs_to_product(session, listing_id=listing_id, product_id=product_id):
            raise HTTPException(status_code=404, detail="Listing not found for this product")
        rows = self.repository.product_rows(session, product_id, listing_id, VERSION)
        analyzed = [(review, result) for review, result in rows if result is not None]
        counts = {level: sum(result.suspicion_level == level for _, result in analyzed) for level in ("low", "medium", "high")}
        total = len(analyzed)
        return ProductReviewAnalysisResponse(
            product_id=product_id, listing_id=listing_id, analysis_version=VERSION,
            total_reviews=len(rows), analyzed_reviews=total,
            low=counts["low"], medium=counts["medium"], high=counts["high"],
            high_suspicion_percentage=round(counts["high"] * 100 / total, 2) if total else 0,
            average_suspicion_score=round(sum(result.suspicion_score for _, result in analyzed) / total, 2) if total else None,
            exact_duplicate_count=sum(result.is_exact_duplicate for _, result in analyzed),
            near_duplicate_count=sum(result.is_near_duplicate for _, result in analyzed),
            page=page, page_size=page_size, total_pages=ceil(total / page_size) if total else 0,
            reviews=[self.as_response(review, result) for review, result in analyzed[(page - 1) * page_size:page * page_size]],
        )

    def product_review_result(self, session: Session, *, product_id: int, review_id: int) -> ReviewAnalysisResponse:
        review = self.repository.product_review(session, product_id, review_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Review not found for this product")
        result = self.repository.review_result(session, review_id, VERSION)
        if result is None:
            raise HTTPException(status_code=404, detail="Analysis not found; run review analysis for this listing")
        return self.as_response(review, result)
