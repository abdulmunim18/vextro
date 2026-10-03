"""Resolve a scraped marketplace product to a catalog variant.

The matcher alone can only recognise phones VEXTRO already knows, which left
every genuinely new marketplace smartphone stuck in the pending-match queue.
This service wraps the matcher with the three cases a crawl actually produces:

* **Case A** - the marketplace listing is already mapped, or scores a safe
  automatic match: reuse that variant.
* **Case B** - the phone exists in the catalog but this configuration does
  not: create the missing variant under the existing canonical product.
* **Case C** - the phone is new: create the canonical product, its variant
  and its normalized specifications.

Creation is deliberately conservative. Without a resolvable brand and a model
name of real substance the item is still queued for an administrator, because
inventing a canonical product from a vague title is the one mistake that
cannot be undone safely.
"""

from __future__ import annotations

import logging
import re

from sqlalchemy.orm import Session

from app.models.canonical_product import CanonicalProduct
from app.repositories.product_matching_repository import (
    ProductMatchingRepository,
)
from app.schemas.product_matching import (
    ProductResolveRequest,
    ProductResolveResponse,
)
from app.services.cross_marketplace_matching import (
    clean_product_display_name,
    cross_marketplace_product_key,
    find_cross_platform_canonical,
)
from app.services.product_matching_service import (
    TIER_EXACT,
    TIER_HIGH,
    ProductMatchingService,
)
from app.services.smartphone_normalization import (
    extract_memory_capacities,
    infer_brand_name,
    infer_title_specifications,
    merge_specifications,
    normalize_color,
    normalize_specifications,
)


logger = logging.getLogger(__name__)


# Tiers safe to attach without an administrator looking at the item.
AUTO_ATTACH_TIERS = frozenset({TIER_EXACT, TIER_HIGH})

MIN_MODEL_NAME_LENGTH = 3


def _slugify(value: str, *, fallback: str) -> str:
    """Return a compact URL-safe slug."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    return slug[:200] or fallback


class ProductResolutionService:
    """Attach scraped listings to the catalog, creating records when safe."""

    def __init__(
        self,
        repository: ProductMatchingRepository | None = None,
        matching_service: ProductMatchingService | None = None,
    ) -> None:
        self.repository = repository or ProductMatchingRepository()
        self.matching_service = (
            matching_service or ProductMatchingService()
        )

    def resolve_product(
        self,
        database_session: Session,
        payload: ProductResolveRequest,
    ) -> ProductResolveResponse:
        """Return a usable variant for one scraped marketplace product."""

        try:
            response = self._resolve(database_session, payload)
            database_session.commit()
        except Exception:
            database_session.rollback()
            raise

        return response

    def _resolve(
        self,
        database_session: Session,
        payload: ProductResolveRequest,
    ) -> ProductResolveResponse:
        match = self.matching_service.match_product(
            database_session,
            payload,
        )

        if match.matched and (
            match.match_tier in AUTO_ATTACH_TIERS
            or match.confidence >= 100
        ):
            logger.info(
                "Canonical product matched: platform=%s external_id=%s "
                "variant_id=%s tier=%s confidence=%s",
                payload.platform_code,
                payload.external_id,
                match.product_variant_id,
                match.match_tier,
                match.confidence,
            )
            return ProductResolveResponse(**match.model_dump())

        if not payload.allow_create:
            return self._as_resolve_response(match)

        created = self._create_catalog_records(database_session, payload)

        if created is None:
            # Keep the matcher's own explanation so the pending-match queue
            # still shows an administrator why nothing was safe.
            return self._as_resolve_response(match)

        return created

    @staticmethod
    def _as_resolve_response(
        match,
    ) -> ProductResolveResponse:
        """Carry an unresolved match through unchanged."""

        payload = match.model_dump()
        payload["matched"] = False
        payload["product_variant_id"] = None

        if match.matched:
            # A MEDIUM/LOW tier automatic match is not trustworthy enough to
            # merge, so surface it as a suggestion instead of a decision.
            payload["suggested_product_variant_id"] = (
                match.product_variant_id
            )
            payload["reason"] = (
                "The best catalog match was only "
                f"{match.match_tier} confidence, which VEXTRO does not "
                "merge automatically."
            )

        return ProductResolveResponse(**payload)

    def _create_catalog_records(
        self,
        database_session: Session,
        payload: ProductResolveRequest,
    ) -> ProductResolveResponse | None:
        """Create the missing canonical product and/or variant."""

        brand_name = infer_brand_name(payload.title, payload.brand)
        display_name = (
            clean_product_display_name(payload.model or payload.title)
            or clean_product_display_name(payload.title)
        )

        if (
            not brand_name
            or len(display_name) < MIN_MODEL_NAME_LENGTH
            or len(display_name.split()) < 2
        ):
            logger.warning(
                "Declined to create a canonical product without a clear "
                "brand and model: platform=%s external_id=%s",
                payload.platform_code,
                payload.external_id,
            )
            return None

        category = self.repository.get_smartphone_category(
            database_session,
        )

        if category is None:
            logger.error(
                "Cannot create canonical products: no smartphone category "
                "exists in the catalog."
            )
            return None

        brand = self._resolve_brand(database_session, brand_name)

        specifications = merge_specifications(
            infer_title_specifications(payload.title),
            payload.specifications,
        )

        ram_gb, storage_gb = extract_memory_capacities(
            specifications=payload.specifications,
            title=payload.title,
        )
        if ram_gb is None:
            ram_gb = payload.ram_gb
        if storage_gb is None:
            storage_gb = payload.storage_gb

        color = normalize_color(payload.color)

        product, product_created = self._resolve_canonical_product(
            database_session,
            platform_code=payload.platform_code,
            title=payload.title,
            display_name=display_name,
            brand=brand,
            category_id=category.id,
            specifications=specifications,
        )

        variant = self.repository.get_variant(
            database_session,
            canonical_product_id=product.id,
            ram_gb=ram_gb,
            storage_gb=storage_gb,
            color=color,
        )
        variant_created = variant is None

        if variant is None:
            variant = self.repository.create_variant(
                database_session,
                canonical_product_id=product.id,
                ram_gb=ram_gb,
                storage_gb=storage_gb,
                color=color,
                sku=self._available_sku(database_session, payload),
                variant_attributes={
                    key: value
                    for key, value in (
                        ("source_platform", payload.platform_code),
                        ("source_external_id", payload.external_id),
                    )
                    if value
                },
            )

        logger.info(
            "Canonical product %s: platform=%s external_id=%s "
            "product_id=%s variant_id=%s variant_created=%s "
            "ram_gb=%s storage_gb=%s color=%s",
            "created" if product_created else "reused",
            payload.platform_code,
            payload.external_id,
            product.id,
            variant.id,
            variant_created,
            ram_gb,
            storage_gb,
            color,
        )

        return ProductResolveResponse(
            matched=True,
            confidence=100,
            match_tier=TIER_EXACT,
            product_variant_id=variant.id,
            canonical_product_id=product.id,
            product_name=product.name,
            brand_name=brand.name if brand is not None else None,
            model=product.model,
            ram_gb=ram_gb,
            storage_gb=storage_gb,
            color=color,
            product_created=product_created,
            variant_created=variant_created,
            reason=(
                "New marketplace smartphone registered in the catalog."
                if product_created
                else "New marketplace configuration registered as a variant."
            ),
        )

    def _resolve_brand(
        self,
        database_session: Session,
        brand_name: str,
    ):
        """Return the catalog brand for a name, creating it when new."""

        brand = self.repository.get_brand_by_name(
            database_session,
            brand_name,
        )

        if brand is not None:
            return brand

        slug_base = _slugify(brand_name, fallback="brand")
        slug = slug_base
        suffix = 2

        while self.repository.brand_slug_exists(database_session, slug):
            slug = f"{slug_base}-{suffix}"
            suffix += 1

        return self.repository.create_brand(
            database_session,
            name=brand_name[:120],
            slug=slug,
        )

    def _resolve_canonical_product(
        self,
        database_session: Session,
        *,
        platform_code: str | None,
        title: str,
        display_name: str,
        brand,
        category_id: int,
        specifications: dict[str, str],
    ) -> tuple[CanonicalProduct, bool]:
        """Find the canonical phone for a title, or create it.

        A Daraz listing and a PriceOye listing for the same phone must land on
        one canonical product, so the brand-scoped cross-marketplace identity
        key is consulted before anything new is created.
        """

        brand_id = brand.id if brand is not None else None
        brand_name = brand.name if brand is not None else None
        model = display_name[:120]

        existing = self.repository.get_canonical_product_by_model(
            database_session,
            brand_id=brand_id,
            model=model,
        )

        if existing is None and brand_id is not None:
            existing = self._find_cross_marketplace_product(
                database_session,
                title=title,
                brand_id=brand_id,
                brand_name=brand_name,
            )

        if existing is not None:
            self.repository.merge_product_specifications(
                database_session,
                existing,
                merge_specifications(existing.specifications, specifications),
            )
            return existing, False

        slug_base = _slugify(
            f"{brand_name or ''} {model}".strip(),
            fallback=f"{platform_code or 'marketplace'}-product",
        )
        slug = slug_base
        suffix = 2

        while self.repository.product_slug_exists(database_session, slug):
            slug = f"{slug_base}-{suffix}"
            suffix += 1

        product = self.repository.create_canonical_product(
            database_session,
            category_id=category_id,
            brand_id=brand_id,
            name=display_name[:255],
            slug=slug,
            model=model,
            specifications=normalize_specifications(specifications),
        )

        return product, True

    @staticmethod
    def _find_cross_marketplace_product(
        database_session: Session,
        *,
        title: str,
        brand_id: int,
        brand_name: str | None,
    ) -> CanonicalProduct | None:
        """Return the same phone already registered from another marketplace."""

        identity = cross_marketplace_product_key(title, brand_name)

        if not identity:
            return None

        # ``find_cross_platform_canonical`` only inspects products that
        # already carry a listing from a different platform, which is exactly
        # the cross-marketplace case; pass a platform id that cannot match so
        # every other platform's products stay eligible.
        return find_cross_platform_canonical(
            database_session,
            title=title,
            brand_id=brand_id,
            incoming_platform_id=-1,
        )

    def _available_sku(
        self,
        database_session: Session,
        payload: ProductResolveRequest,
    ) -> str | None:
        """Return the marketplace SKU when it is free to claim."""

        if not payload.sku:
            return None

        sku = payload.sku.strip()[:120]

        if not sku:
            return None

        taken = self.repository.get_sku_match(database_session, sku=sku)

        return None if taken is not None else sku


__all__ = [
    "AUTO_ATTACH_TIERS",
    "ProductResolutionService",
]
