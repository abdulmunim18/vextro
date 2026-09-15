"""Transaction-aware seller trust calculation and retrieval."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.seller import Seller
from app.models.seller_trust_analysis import SellerTrustAnalysis
from app.repositories.seller_trust_repository import SellerTrustRepository
from app.schemas.seller_trust import SellerTrustResponse
from app.services.review_risk_engine import VERSION as REVIEW_VERSION
from app.services.seller_trust_engine import VERSION, aggregate_seller_evidence, evidence_signature


class SellerTrustService:
    def __init__(self) -> None:
        self.repository = SellerTrustRepository()

    def recalculate(self, session: Session, seller_id: int) -> SellerTrustAnalysis:
        seller = self.repository.seller(session, seller_id)
        if seller is None:
            raise HTTPException(status_code=404, detail="Seller not found")
        rows = self.repository.review_evidence(session, seller_id, REVIEW_VERSION)
        values = aggregate_seller_evidence(
            external_seller_id=seller.external_seller_id,
            listing_count=self.repository.listing_count(session, seller_id), rows=rows,
        )
        self.repository.upsert(session, seller_id, values)
        session.flush()
        result = self.repository.result(session, seller_id, VERSION)
        assert result is not None
        return result

    def result(self, session: Session, seller_id: int) -> SellerTrustResponse:
        seller = self.repository.seller(session, seller_id)
        if seller is None:
            raise HTTPException(status_code=404, detail="Seller not found")
        analysis = self.repository.result(session, seller_id, VERSION)
        if analysis is None:
            return self.unavailable(seller, "Seller trust analysis has not been run for this version.")
        current_rows = self.repository.review_evidence(session, seller_id, REVIEW_VERSION)
        current_listings = self.repository.listing_count(session, seller_id)
        current_analyzed = sum(result is not None for _, result in current_rows)
        if (
            analysis.total_reviews != len(current_rows)
            or analysis.analyzed_reviews != current_analyzed
            or analysis.total_listings != current_listings
            or analysis.signals.get("evidence_signature") != evidence_signature(seller.external_seller_id, current_listings, current_rows)
        ):
            return self.unavailable(seller, "Persisted seller trust evidence is stale; recalculate before interpreting a score.")
        return self.as_response(seller, analysis)

    @staticmethod
    def as_response(seller: Seller, analysis: SellerTrustAnalysis) -> SellerTrustResponse:
        return SellerTrustResponse(
            seller_id=seller.id, seller_name=seller.name,
            status="insufficient_data" if analysis.trust_score is None else "available",
            analysis_version=analysis.analysis_version,
            trust_score=analysis.trust_score, trust_level=analysis.trust_level,
            confidence_score=analysis.confidence_score, confidence_level=analysis.confidence_level,
            total_listings=analysis.total_listings, total_reviews=analysis.total_reviews,
            analyzed_reviews=analysis.analyzed_reviews,
            analysis_coverage_percentage=float(analysis.analysis_coverage_percentage),
            high_suspicion_review_count=analysis.high_suspicion_review_count,
            medium_suspicion_review_count=analysis.medium_suspicion_review_count,
            low_suspicion_review_count=analysis.low_suspicion_review_count,
            high_suspicion_percentage=float(analysis.high_suspicion_percentage),
            average_review_suspicion_score=float(analysis.average_review_suspicion_score) if analysis.average_review_suspicion_score is not None else None,
            verified_purchase_ratio=float(analysis.verified_purchase_ratio) if analysis.verified_purchase_ratio is not None else None,
            rating_average=float(analysis.rating_average) if analysis.rating_average is not None else None,
            rating_variance=float(analysis.rating_variance) if analysis.rating_variance is not None else None,
            signals=analysis.signals, reasons=analysis.reasons, analyzed_at=analysis.analyzed_at,
        )

    @staticmethod
    def unavailable(seller: Seller | None, reason: str) -> SellerTrustResponse:
        return SellerTrustResponse(
            seller_id=seller.id if seller else None,
            seller_name=seller.name if seller else None,
            status="insufficient_data", analysis_version=VERSION,
            trust_score=None, trust_level="insufficient_data",
            confidence_score=0, confidence_level="low", total_listings=0,
            total_reviews=0, analyzed_reviews=0, analysis_coverage_percentage=0,
            high_suspicion_review_count=0, medium_suspicion_review_count=0,
            low_suspicion_review_count=0, high_suspicion_percentage=0,
            average_review_suspicion_score=None, verified_purchase_ratio=None,
            rating_average=None, rating_variance=None,
            signals={}, reasons=[reason], analyzed_at=None,
        )
