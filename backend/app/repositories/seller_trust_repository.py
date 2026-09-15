"""Seller evidence queries and idempotent trust-analysis persistence."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.product_listing import ProductListing
from app.models.raw_review import RawReview
from app.models.review_analysis import ReviewAnalysis
from app.models.seller import Seller
from app.models.seller_trust_analysis import SellerTrustAnalysis


class SellerTrustRepository:
    @staticmethod
    def seller(session: Session, seller_id: int) -> Seller | None:
        return session.get(Seller, seller_id)

    @staticmethod
    def listing_count(session: Session, seller_id: int) -> int:
        return int(session.scalar(select(func.count(ProductListing.id)).where(ProductListing.seller_id == seller_id)) or 0)

    @staticmethod
    def review_evidence(session: Session, seller_id: int, review_version: str) -> list[tuple[RawReview, ReviewAnalysis | None]]:
        """Count only reviews consistently attached to the current seller/listing."""
        statement = (
            select(RawReview, ReviewAnalysis)
            .join(ProductListing, ProductListing.id == RawReview.product_listing_id)
            .outerjoin(ReviewAnalysis, (ReviewAnalysis.raw_review_id == RawReview.id) & (ReviewAnalysis.analysis_version == review_version))
            .where(ProductListing.seller_id == seller_id, RawReview.seller_id == seller_id)
            .order_by(RawReview.id)
            .execution_options(populate_existing=True)
        )
        return list(session.execute(statement).all())

    @staticmethod
    def upsert(session: Session, seller_id: int, values: dict[str, object]) -> None:
        statement = insert(SellerTrustAnalysis).values(seller_id=seller_id, **values)
        statement = statement.on_conflict_do_update(
            constraint="uq_seller_trust_analyses_seller_version",
            set_={**{key: statement.excluded[key] for key in values if key != "analysis_version"}, "analyzed_at": func.now(), "updated_at": func.now()},
        )
        session.execute(statement)

    @staticmethod
    def result(session: Session, seller_id: int, version: str) -> SellerTrustAnalysis | None:
        return session.scalar(
            select(SellerTrustAnalysis)
            .where(SellerTrustAnalysis.seller_id == seller_id, SellerTrustAnalysis.analysis_version == version)
            .execution_options(populate_existing=True)
        )
