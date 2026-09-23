"""Database operations for normalized marketplace reviews."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload

from app.models.canonical_product import CanonicalProduct
from app.models.platform import Platform
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.raw_review import RawReview


class ReviewRepository:
    @staticmethod
    def get_listing(
        database_session: Session,
        *,
        platform_code: str,
        external_listing_id: str,
    ) -> ProductListing | None:
        statement = (
            select(ProductListing)
            .join(Platform, Platform.id == ProductListing.platform_id)
            .options(selectinload(ProductListing.seller))
            .where(
                Platform.code == platform_code,
                Platform.is_active.is_(True),
                ProductListing.external_id == external_listing_id,
            )
        )
        return database_session.scalar(statement)

    @staticmethod
    def insert_review(
        database_session: Session,
        *,
        values: dict[str, object],
    ) -> tuple[RawReview, bool]:
        statement = (
            insert(RawReview)
            .values(**values)
            .on_conflict_do_nothing()
            .returning(RawReview.id)
        )
        review_id = database_session.scalar(statement)
        created = review_id is not None

        if review_id is None:
            review_id = database_session.scalar(
                select(RawReview.id).where(
                    RawReview.platform_id == values["platform_id"],
                    RawReview.review_fingerprint
                    == values["review_fingerprint"],
                )
            )

        if review_id is None:
            external_review_id = values.get("external_review_id")
            if external_review_id is not None:
                review_id = database_session.scalar(
                    select(RawReview.id).where(
                        RawReview.platform_id == values["platform_id"],
                        RawReview.external_review_id == external_review_id,
                    )
                )

        if review_id is None:
            raise RuntimeError("Review identity conflict could not be resolved.")

        review = database_session.get(RawReview, review_id)
        if review is None:
            raise RuntimeError("Persisted review could not be loaded.")
        return review, created

    @staticmethod
    def get_product(
        database_session: Session,
        product_id: int,
    ) -> CanonicalProduct | None:
        return database_session.scalar(
            select(CanonicalProduct).where(
                CanonicalProduct.id == product_id,
                CanonicalProduct.is_active.is_(True),
            )
        )

    @staticmethod
    def listing_belongs_to_product(
        database_session: Session,
        *,
        listing_id: int,
        product_id: int,
    ) -> bool:
        return database_session.scalar(
            select(ProductListing.id)
            .join(
                ProductVariant,
                ProductVariant.id == ProductListing.product_variant_id,
            )
            .where(
                ProductListing.id == listing_id,
                ProductVariant.canonical_product_id == product_id,
            )
        ) is not None

    @staticmethod
    def list_product_reviews(
        database_session: Session,
        *,
        product_id: int,
        listing_id: int | None,
        offset: int,
        limit: int,
    ) -> tuple[list[tuple[RawReview, str]], int]:
        filters = [ProductVariant.canonical_product_id == product_id]
        if listing_id is not None:
            filters.append(RawReview.product_listing_id == listing_id)

        base = (
            select(RawReview)
            .join(
                ProductListing,
                ProductListing.id == RawReview.product_listing_id,
            )
            .join(
                ProductVariant,
                ProductVariant.id == ProductListing.product_variant_id,
            )
            .where(*filters)
        )
        total = database_session.scalar(
            select(func.count()).select_from(base.subquery())
        ) or 0
        rows = database_session.execute(
            select(RawReview, Platform.code)
            .join(Platform, Platform.id == RawReview.platform_id)
            .join(
                ProductListing,
                ProductListing.id == RawReview.product_listing_id,
            )
            .join(
                ProductVariant,
                ProductVariant.id == ProductListing.product_variant_id,
            )
            .where(*filters)
            .order_by(
                RawReview.reviewed_at.desc().nulls_last(),
                RawReview.id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()
        return [(row[0], row[1]) for row in rows], int(total)

    @staticmethod
    def get_product_rating_aggregates(
        database_session: Session,
        *,
        product_id: int,
        listing_id: int | None,
    ) -> tuple[float | None, dict[int, int]]:
        filters = [ProductVariant.canonical_product_id == product_id]
        if listing_id is not None:
            filters.append(RawReview.product_listing_id == listing_id)

        statement = (
            select(
                RawReview.rating,
                func.count(RawReview.id),
            )
            .join(
                ProductListing,
                ProductListing.id == RawReview.product_listing_id,
            )
            .join(
                ProductVariant,
                ProductVariant.id == ProductListing.product_variant_id,
            )
            .where(*filters)
            .group_by(RawReview.rating)
        )
        distribution = {rating: 0 for rating in range(1, 6)}
        weighted_total = 0
        review_total = 0
        for rating, count in database_session.execute(statement):
            distribution[int(rating)] = int(count)
            weighted_total += int(rating) * int(count)
            review_total += int(count)

        average = (
            round(weighted_total / review_total, 2)
            if review_total
            else None
        )
        return average, distribution
