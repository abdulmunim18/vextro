"""Persistence helpers for unresolved marketplace product matches."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.pending_product_match import PendingProductMatch
from app.models.product_variant import ProductVariant


class PendingProductMatchRepository:
    @staticmethod
    def delete(
        session: Session,
        match: PendingProductMatch,
    ) -> None:
        session.delete(match)

    @staticmethod
    def get_by_source(
        session: Session,
        *,
        platform_code: str,
        external_id: str,
    ) -> PendingProductMatch | None:
        return session.scalar(
            select(PendingProductMatch)
            .options(
                selectinload(PendingProductMatch.assigned_product_variant)
                .selectinload(ProductVariant.canonical_product),
            )
            .where(
                PendingProductMatch.platform_code == platform_code,
                PendingProductMatch.external_id == external_id,
            )
        )

    @staticmethod
    def get(session: Session, match_id: int) -> PendingProductMatch | None:
        return session.scalar(
            select(PendingProductMatch)
            .options(
                selectinload(PendingProductMatch.assigned_product_variant)
                .selectinload(ProductVariant.canonical_product),
            )
            .where(PendingProductMatch.id == match_id)
        )

    @staticmethod
    def list(
        session: Session,
        *,
        query: str | None,
        platform_code: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> tuple[list[PendingProductMatch], int]:
        filters = []
        if query:
            pattern = f"%{query.strip()}%"
            filters.append(
                or_(
                    PendingProductMatch.title.ilike(pattern),
                    PendingProductMatch.external_id.ilike(pattern),
                )
            )
        if platform_code:
            filters.append(PendingProductMatch.platform_code == platform_code)
        if status:
            filters.append(PendingProductMatch.status == status)

        total = session.scalar(
            select(func.count(PendingProductMatch.id)).where(*filters)
        ) or 0
        rows = session.scalars(
            select(PendingProductMatch)
            .options(
                selectinload(PendingProductMatch.assigned_product_variant)
                .selectinload(ProductVariant.canonical_product),
            )
            .where(*filters)
            .order_by(PendingProductMatch.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return list(rows), int(total)

    @staticmethod
    def variant_options(
        session: Session,
        *,
        query: str,
        limit: int,
    ) -> list[tuple[ProductVariant, CanonicalProduct, Brand | None]]:
        pattern = f"%{query.strip()}%"
        rows = session.execute(
            select(ProductVariant, CanonicalProduct, Brand)
            .join(
                CanonicalProduct,
                ProductVariant.canonical_product_id == CanonicalProduct.id,
            )
            .outerjoin(Brand, CanonicalProduct.brand_id == Brand.id)
            .where(
                ProductVariant.is_active.is_(True),
                CanonicalProduct.is_active.is_(True),
                or_(
                    CanonicalProduct.name.ilike(pattern),
                    CanonicalProduct.model.ilike(pattern),
                    Brand.name.ilike(pattern),
                    ProductVariant.sku.ilike(pattern),
                ),
            )
            .order_by(CanonicalProduct.name.asc(), ProductVariant.id.asc())
            .limit(limit)
        ).all()
        return list(rows)
