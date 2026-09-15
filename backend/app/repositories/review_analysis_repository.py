"""Persistence and read queries for versioned review-risk results."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.raw_review import RawReview
from app.models.review_analysis import ReviewAnalysis


class ReviewAnalysisRepository:
    @staticmethod
    def listing_reviews(session: Session, listing_id: int) -> list[RawReview]:
        return list(session.scalars(select(RawReview).where(RawReview.product_listing_id == listing_id).order_by(RawReview.id)).all())

    @staticmethod
    def upsert(session: Session, review_id: int, values: dict[str, object]) -> None:
        statement = insert(ReviewAnalysis).values(raw_review_id=review_id, **values)
        statement = statement.on_conflict_do_update(
            constraint="uq_review_analyses_review_version",
            set_={**{key: statement.excluded[key] for key in values if key != "analysis_version"}, "analyzed_at": func.now(), "updated_at": func.now()},
        )
        session.execute(statement)

    @staticmethod
    def product_rows(session: Session, product_id: int, listing_id: int | None, version: str) -> list[tuple[RawReview, ReviewAnalysis | None]]:
        statement = (
            select(RawReview, ReviewAnalysis)
            .join(ProductListing, ProductListing.id == RawReview.product_listing_id)
            .join(ProductVariant, ProductVariant.id == ProductListing.product_variant_id)
            .outerjoin(ReviewAnalysis, (ReviewAnalysis.raw_review_id == RawReview.id) & (ReviewAnalysis.analysis_version == version))
            .where(ProductVariant.canonical_product_id == product_id)
            .order_by(RawReview.reviewed_at.desc().nulls_last(), RawReview.id.desc())
        )
        if listing_id is not None:
            statement = statement.where(RawReview.product_listing_id == listing_id)
        return list(session.execute(statement.execution_options(populate_existing=True)).all())

    @staticmethod
    def review_result(session: Session, review_id: int, version: str) -> ReviewAnalysis | None:
        return session.scalar(
            select(ReviewAnalysis)
            .where(ReviewAnalysis.raw_review_id == review_id, ReviewAnalysis.analysis_version == version)
            .execution_options(populate_existing=True)
        )

    @staticmethod
    def product_review(session: Session, product_id: int, review_id: int) -> RawReview | None:
        return session.scalar(
            select(RawReview)
            .join(ProductListing, ProductListing.id == RawReview.product_listing_id)
            .join(ProductVariant, ProductVariant.id == ProductListing.product_variant_id)
            .where(ProductVariant.canonical_product_id == product_id, RawReview.id == review_id)
        )
