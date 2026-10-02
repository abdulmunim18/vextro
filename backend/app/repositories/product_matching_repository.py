"""Repository helpers for marketplace product matching."""

import re
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

    def get_manual_match(
        self,
        database_session: Session,
        *,
        platform_code: str,
        external_id: str,
    ) -> ProductMatchCandidate | None:
        """Return an administrator-approved source mapping when available."""

        row = database_session.execute(
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
        if row is None:
            return None
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

    def create_color_sibling_variant(
        self,
        database_session: Session,
        *,
        reference_candidate: ProductMatchCandidate,
        color: str,
    ) -> ProductMatchCandidate | None:
        """Create a new ``ProductVariant`` for a colour not yet in the catalog.

        Marketplaces (PriceOye specifically) list every colour of a
        phone on the same product page, so a single scrape can
        legitimately discover four or five brand-new colour SKUs for
        a product whose catalog only has one. Instead of forcing an
        administrator to resolve each pending match by hand, this
        method clones the reference variant's RAM / storage /
        condition and only varies the colour.

        Returns ``None`` when a matching colour variant already
        exists (e.g. a concurrent request raced the insert, or the
        caller normalised the colour name differently from an
        existing row), so the caller can re-query and reuse the
        existing row rather than crash on the unique constraint.
        """

        cleaned_color = (color or "").strip()
        if not cleaned_color:
            return None

        # The variants table has a unique constraint on
        # (canonical_product_id, ram_gb, storage_gb, color, condition)
        # so a case-insensitive lookup prevents us from creating
        # duplicates that only differ in capitalisation.
        existing = database_session.scalar(
            select(ProductVariant).where(
                ProductVariant.canonical_product_id
                == reference_candidate.canonical_product_id,
                ProductVariant.ram_gb.is_(reference_candidate.ram_gb)
                if reference_candidate.ram_gb is None
                else ProductVariant.ram_gb == reference_candidate.ram_gb,
                ProductVariant.storage_gb.is_(reference_candidate.storage_gb)
                if reference_candidate.storage_gb is None
                else ProductVariant.storage_gb
                == reference_candidate.storage_gb,
                ProductVariant.condition == reference_candidate.condition,
                ProductVariant.color.ilike(cleaned_color),
                ProductVariant.is_active.is_(True),
            )
        )
        if existing is not None:
            return ProductMatchCandidate(
                canonical_product_id=existing.canonical_product_id,
                product_variant_id=existing.id,
                product_name=reference_candidate.product_name,
                brand_name=reference_candidate.brand_name,
                model=reference_candidate.model,
                sku=existing.sku,
                ram_gb=existing.ram_gb,
                storage_gb=existing.storage_gb,
                color=existing.color,
                condition=existing.condition,
            )

        new_variant = ProductVariant(
            canonical_product_id=(
                reference_candidate.canonical_product_id
            ),
            sku=None,
            ram_gb=reference_candidate.ram_gb,
            storage_gb=reference_candidate.storage_gb,
            color=cleaned_color,
            condition=reference_candidate.condition,
            variant_attributes={
                "auto_created": True,
                "created_from_variant_id": (
                    reference_candidate.product_variant_id
                ),
                "reason": "marketplace_discovered_color",
            },
            is_active=True,
        )
        database_session.add(new_variant)
        database_session.flush()

        return ProductMatchCandidate(
            canonical_product_id=new_variant.canonical_product_id,
            product_variant_id=new_variant.id,
            product_name=reference_candidate.product_name,
            brand_name=reference_candidate.brand_name,
            model=reference_candidate.model,
            sku=new_variant.sku,
            ram_gb=new_variant.ram_gb,
            storage_gb=new_variant.storage_gb,
            color=new_variant.color,
            condition=new_variant.condition,
        )

    def get_listing_match(
        self,
        database_session: Session,
        *,
        platform_code: str,
        external_id: str,
    ) -> ProductMatchCandidate | None:
        """Return the variant an existing marketplace listing maps to.

        A marketplace id that has already been ingested identifies the
        same offer on every later crawl, so its mapping is reused
        instead of being re-derived from a title that may have been
        reworded since.
        """

        row = database_session.execute(
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
                ProductListing,
                ProductListing.product_variant_id == ProductVariant.id,
            )
            .join(Platform, Platform.id == ProductListing.platform_id)
            .join(
                CanonicalProduct,
                ProductVariant.canonical_product_id == CanonicalProduct.id,
            )
            .outerjoin(Brand, CanonicalProduct.brand_id == Brand.id)
            .where(
                Platform.code == platform_code,
                ProductListing.external_id == external_id,
                ProductVariant.is_active.is_(True),
                CanonicalProduct.is_active.is_(True),
            )
        ).first()
        if row is None:
            return None
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

    def get_or_create_variant(
        self,
        database_session: Session,
        *,
        reference_candidate: ProductMatchCandidate,
        ram_gb: int | None,
        storage_gb: int | None,
        color: str | None,
    ) -> ProductMatchCandidate:
        """Return the exact configuration of a known product, adding it if new.

        Used for sources that state RAM, storage and colour as separate
        fields, where the configuration is known rather than guessed.
        """

        cleaned_color = (color or "").strip() or None

        conditions = [
            ProductVariant.canonical_product_id
            == reference_candidate.canonical_product_id,
            ProductVariant.condition == "new",
            ProductVariant.is_active.is_(True),
            ProductVariant.ram_gb.is_(None)
            if ram_gb is None
            else ProductVariant.ram_gb == ram_gb,
            ProductVariant.storage_gb.is_(None)
            if storage_gb is None
            else ProductVariant.storage_gb == storage_gb,
            ProductVariant.color.is_(None)
            if cleaned_color is None
            else ProductVariant.color.ilike(cleaned_color),
        ]
        variant = database_session.scalar(
            select(ProductVariant).where(*conditions)
        )

        if variant is None:
            variant = ProductVariant(
                canonical_product_id=(
                    reference_candidate.canonical_product_id
                ),
                sku=None,
                ram_gb=ram_gb,
                storage_gb=storage_gb,
                color=cleaned_color,
                condition="new",
                variant_attributes={
                    "auto_created": True,
                    "reason": "marketplace_discovered_configuration",
                },
                is_active=True,
            )
            database_session.add(variant)
            database_session.flush()

        return ProductMatchCandidate(
            canonical_product_id=variant.canonical_product_id,
            product_variant_id=variant.id,
            product_name=reference_candidate.product_name,
            brand_name=reference_candidate.brand_name,
            model=reference_candidate.model,
            sku=variant.sku,
            ram_gb=variant.ram_gb,
            storage_gb=variant.storage_gb,
            color=variant.color,
            condition=variant.condition,
        )

    def create_catalog_product(
        self,
        database_session: Session,
        *,
        platform_code: str,
        external_id: str,
        name: str,
        brand_name: str | None,
        specifications: dict[str, str],
        ram_gb: int | None,
        storage_gb: int | None,
        color: str | None,
    ) -> ProductMatchCandidate:
        """Add a phone the catalog has never seen, with its first variant."""

        brand = None
        cleaned_brand = (brand_name or "").strip()
        if cleaned_brand:
            brand = database_session.scalar(
                select(Brand).where(
                    func.lower(Brand.name) == cleaned_brand.lower(),
                )
            )
            if brand is None:
                slug_base = (
                    re.sub(r"[^a-z0-9]+", "-", cleaned_brand.lower())
                    .strip("-")
                    or "brand"
                )
                slug = slug_base
                suffix = 2
                while database_session.scalar(
                    select(Brand.id).where(Brand.slug == slug)
                ):
                    slug = f"{slug_base}-{suffix}"
                    suffix += 1
                brand = Brand(
                    name=cleaned_brand[:120],
                    slug=slug,
                    is_active=True,
                )
                database_session.add(brand)
                database_session.flush()

        clean_name = " ".join(name.split())[:255]
        model = clean_name[:120]
        # The product part of a variant-level id ("<product>--<colour>")
        # keeps every colour of one phone on the same catalog product.
        product_key = external_id.split("--", 1)[0]
        slug = re.sub(
            r"[^a-z0-9]+",
            "-",
            f"{platform_code}-{product_key}".lower(),
        ).strip("-")[:255]

        product = database_session.scalar(
            select(CanonicalProduct).where(CanonicalProduct.slug == slug)
        )
        if product is None and brand is not None:
            product = database_session.scalar(
                select(CanonicalProduct).where(
                    CanonicalProduct.brand_id == brand.id,
                    func.lower(CanonicalProduct.model) == model.lower(),
                )
            )

        if product is None:
            category = None
            for category_slug in ("smartphones", "mobile-phones"):
                category = database_session.scalar(
                    select(Category).where(Category.slug == category_slug)
                )
                if category is not None:
                    break
            if category is None:
                category = Category(
                    name="Smartphones",
                    slug="smartphones",
                    is_active=True,
                )
                database_session.add(category)
                database_session.flush()

            product = CanonicalProduct(
                category_id=category.id,
                brand_id=brand.id if brand is not None else None,
                name=clean_name,
                slug=slug,
                model=model,
                specifications=dict(specifications),
                is_active=True,
            )
            database_session.add(product)
            database_session.flush()

        reference = ProductMatchCandidate(
            canonical_product_id=product.id,
            product_variant_id=0,
            product_name=product.name,
            brand_name=brand.name if brand is not None else None,
            model=product.model,
            sku=None,
            ram_gb=ram_gb,
            storage_gb=storage_gb,
            color=color,
            condition="new",
        )
        return self.get_or_create_variant(
            database_session,
            reference_candidate=reference,
            ram_gb=ram_gb,
            storage_gb=storage_gb,
            color=color,
        )
