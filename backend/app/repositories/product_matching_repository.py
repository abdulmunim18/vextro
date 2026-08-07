"""Repository helpers for marketplace product matching."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.product_variant import ProductVariant


@dataclass(frozen=True)
class ProductMatchCandidate:
    """Structured catalog candidate used by the matching service."""

    canonical_product_id: int
    product_variant_id: int

    product_name: str
    brand_name: str | None
    model: str | None

    sku: str | None
    ram_gb: int | None
    storage_gb: int | None
    color: str | None
    condition: str


class ProductMatchingRepository:
    """Read active catalog variants for product matching."""

    def list_match_candidates(
        self,
        database_session: Session,
        *,
        brand: str | None = None,
    ) -> list[ProductMatchCandidate]:
        """Return active product variants eligible for matching."""

        query = (
            select(
                CanonicalProduct.id,
                ProductVariant.id,
                CanonicalProduct.name,
                Brand.name,
                CanonicalProduct.model,
                ProductVariant.sku,
                ProductVariant.ram_gb,
                ProductVariant.storage_gb,
                ProductVariant.color,
                ProductVariant.condition,
            )
            .join(
                ProductVariant,
                ProductVariant.canonical_product_id
                == CanonicalProduct.id,
            )
            .outerjoin(
                Brand,
                CanonicalProduct.brand_id
                == Brand.id,
            )
            .where(
                CanonicalProduct.is_active.is_(True),
                ProductVariant.is_active.is_(True),
            )
        )

        cleaned_brand = (
            brand.strip()
            if brand
            else ""
        )

        if cleaned_brand:
            query = query.where(
                Brand.name.ilike(
                    cleaned_brand,
                ),
            )

        query = query.order_by(
            CanonicalProduct.name.asc(),
            ProductVariant.id.asc(),
        )

        rows = database_session.execute(
            query,
        ).all()

        return [
            ProductMatchCandidate(
                canonical_product_id=row[0],
                product_variant_id=row[1],
                product_name=row[2],
                brand_name=row[3],
                model=row[4],
                sku=row[5],
                ram_gb=row[6],
                storage_gb=row[7],
                color=row[8],
                condition=row[9],
            )
            for row in rows
        ]