"""Repository helpers for marketplace product matching."""

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.pending_product_match import PendingProductMatch
from app.models.platform import Platform
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant


CANDIDATE_COLUMNS = (
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


def _build_candidate(row) -> ProductMatchCandidate:
    """Map one ``CANDIDATE_COLUMNS`` row onto a match candidate."""

    return ProductMatchCandidate(
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


class ProductMatchingRepository:
    """Read active catalog variants for product matching."""

    def get_listing_match(
        self,
        database_session: Session,
        *,
        platform_code: str,
        external_id: str,
    ) -> ProductMatchCandidate | None:
        """Return the variant a known marketplace listing already maps to.

        A listing VEXTRO has already ingested carries its own identity: the
        marketplace's own external ID. Re-deriving that identity from the
        title on every refresh is what allowed catalog growth to orphan
        existing listings and freeze their prices, so this exact mapping is
        resolved before any fuzzy scoring runs.
        """

        row = database_session.execute(
            select(*CANDIDATE_COLUMNS)
            .select_from(ProductListing)
            .join(Platform, Platform.id == ProductListing.platform_id)
            .join(
                ProductVariant,
                ProductVariant.id == ProductListing.product_variant_id,
            )
            .join(
                CanonicalProduct,
                ProductVariant.canonical_product_id == CanonicalProduct.id,
            )
            .outerjoin(Brand, CanonicalProduct.brand_id == Brand.id)
            .where(
                Platform.code == platform_code,
                Platform.is_active.is_(True),
                ProductListing.external_id == external_id,
                ProductVariant.is_active.is_(True),
                CanonicalProduct.is_active.is_(True),
            )
        ).first()

        return None if row is None else _build_candidate(row)

    def get_sku_match(
        self,
        database_session: Session,
        *,
        sku: str,
    ) -> ProductMatchCandidate | None:
        """Return the variant holding one exact marketplace SKU code."""

        row = database_session.execute(
            select(*CANDIDATE_COLUMNS)
            .select_from(ProductVariant)
            .join(
                CanonicalProduct,
                ProductVariant.canonical_product_id == CanonicalProduct.id,
            )
            .outerjoin(Brand, CanonicalProduct.brand_id == Brand.id)
            .where(
                func.lower(ProductVariant.sku) == sku.strip().lower(),
                ProductVariant.is_active.is_(True),
                CanonicalProduct.is_active.is_(True),
            )
        ).first()

        return None if row is None else _build_candidate(row)

    def get_candidate_for_variant(
        self,
        database_session: Session,
        product_variant_id: int,
    ) -> ProductMatchCandidate | None:
        """Return one specific active variant as a match candidate."""

        row = database_session.execute(
            select(*CANDIDATE_COLUMNS)
            .select_from(ProductVariant)
            .join(
                CanonicalProduct,
                ProductVariant.canonical_product_id == CanonicalProduct.id,
            )
            .outerjoin(Brand, CanonicalProduct.brand_id == Brand.id)
            .where(
                ProductVariant.id == product_variant_id,
                ProductVariant.is_active.is_(True),
                CanonicalProduct.is_active.is_(True),
            )
        ).first()

        return None if row is None else _build_candidate(row)

    def get_brand_by_name(
        self,
        database_session: Session,
        name: str,
    ) -> Brand | None:
        """Return one brand matched case-insensitively by name."""

        return database_session.scalar(
            select(Brand).where(
                func.lower(Brand.name) == name.strip().lower()
            )
        )

    def create_brand(
        self,
        database_session: Session,
        *,
        name: str,
        slug: str,
    ) -> Brand:
        """Create and flush one catalog brand."""

        brand = Brand(name=name, slug=slug, is_active=True)
        database_session.add(brand)
        database_session.flush()

        return brand

    def brand_slug_exists(
        self,
        database_session: Session,
        slug: str,
    ) -> bool:
        """Report whether a brand slug is already taken."""

        return database_session.scalar(
            select(Brand.id).where(Brand.slug == slug)
        ) is not None

    def get_smartphone_category(
        self,
        database_session: Session,
    ) -> Category | None:
        """Return the category new smartphones are filed under."""

        return database_session.scalar(
            select(Category)
            .where(Category.slug.in_(("mobile-phones", "smartphones")))
            .order_by(Category.slug.asc())
            .limit(1)
        )

    def get_canonical_product_by_model(
        self,
        database_session: Session,
        *,
        brand_id: int | None,
        model: str,
    ) -> CanonicalProduct | None:
        """Return an active product with the same brand and model code."""

        filters = [
            CanonicalProduct.is_active.is_(True),
            func.lower(CanonicalProduct.model) == model.strip().lower(),
        ]

        if brand_id is None:
            filters.append(CanonicalProduct.brand_id.is_(None))
        else:
            filters.append(CanonicalProduct.brand_id == brand_id)

        return database_session.scalar(
            select(CanonicalProduct)
            .where(*filters)
            .order_by(CanonicalProduct.id.asc())
            .limit(1)
        )

    def product_slug_exists(
        self,
        database_session: Session,
        slug: str,
    ) -> bool:
        """Report whether a canonical product slug is already taken."""

        return database_session.scalar(
            select(CanonicalProduct.id).where(
                CanonicalProduct.slug == slug
            )
        ) is not None

    def create_canonical_product(
        self,
        database_session: Session,
        *,
        category_id: int,
        brand_id: int | None,
        name: str,
        slug: str,
        model: str,
        specifications: dict[str, object],
    ) -> CanonicalProduct:
        """Create and flush one canonical smartphone."""

        product = CanonicalProduct(
            category_id=category_id,
            brand_id=brand_id,
            name=name,
            slug=slug,
            model=model,
            specifications=specifications,
            is_active=True,
        )
        database_session.add(product)
        database_session.flush()

        return product

    def get_variant(
        self,
        database_session: Session,
        *,
        canonical_product_id: int,
        ram_gb: int | None,
        storage_gb: int | None,
        color: str | None,
        condition: str = "new",
    ) -> ProductVariant | None:
        """Return the variant holding one exact configuration."""

        filters = [
            ProductVariant.canonical_product_id == canonical_product_id,
            ProductVariant.condition == condition,
        ]

        for column, value in (
            (ProductVariant.ram_gb, ram_gb),
            (ProductVariant.storage_gb, storage_gb),
            (ProductVariant.color, color),
        ):
            filters.append(
                column.is_(None) if value is None else column == value
            )

        return database_session.scalar(
            select(ProductVariant).where(*filters)
        )

    def create_variant(
        self,
        database_session: Session,
        *,
        canonical_product_id: int,
        ram_gb: int | None,
        storage_gb: int | None,
        color: str | None,
        sku: str | None,
        variant_attributes: dict[str, object],
        condition: str = "new",
    ) -> ProductVariant:
        """Create and flush one product configuration."""

        variant = ProductVariant(
            canonical_product_id=canonical_product_id,
            sku=sku,
            ram_gb=ram_gb,
            storage_gb=storage_gb,
            color=color,
            condition=condition,
            variant_attributes=variant_attributes,
            is_active=True,
        )
        database_session.add(variant)
        database_session.flush()

        return variant

    def merge_product_specifications(
        self,
        database_session: Session,
        product: CanonicalProduct,
        specifications: dict[str, object],
    ) -> None:
        """Store merged specifications on an existing canonical product."""

        if specifications != (product.specifications or {}):
            product.specifications = specifications
            database_session.flush()

    def list_match_candidates(
        self,
        database_session: Session,
        *,
        brand: str | None = None,
    ) -> list[ProductMatchCandidate]:
        """Return active product variants eligible for matching."""

        query = (
            select(*CANDIDATE_COLUMNS)
            .select_from(CanonicalProduct)
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

        return [_build_candidate(row) for row in rows]

    def get_manual_match(
        self,
        database_session: Session,
        *,
        platform_code: str,
        external_id: str,
    ) -> ProductMatchCandidate | None:
        """Return an administrator-approved source mapping when available."""

        row = database_session.execute(
            select(*CANDIDATE_COLUMNS)
            .select_from(ProductVariant)
            .join(
                PendingProductMatch,
                PendingProductMatch.assigned_product_variant_id
                == ProductVariant.id,
            )
            .join(
                CanonicalProduct,
                ProductVariant.canonical_product_id == CanonicalProduct.id,
            )
            .outerjoin(Brand, CanonicalProduct.brand_id == Brand.id)
            .where(
                PendingProductMatch.platform_code == platform_code,
                PendingProductMatch.external_id == external_id,
                PendingProductMatch.status.in_(("resolved", "replayed")),
                ProductVariant.is_active.is_(True),
                CanonicalProduct.is_active.is_(True),
            )
        ).first()
        return None if row is None else _build_candidate(row)
