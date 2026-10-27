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
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.canonical_product import CanonicalProduct
from app.models.platform import Platform
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.services.category_profiles import profile_for
from app.services.variant_identity import IDENTITY, MEMORY_COLUMNS
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
    names_differ_on_5g,
)
from app.services.smartphone_normalization import (
    clean_marketplace_title,
    clean_model_name,
    detect_title_color,
    extract_memory_capacities,
    is_accessory_title,
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

# A match-only listing below this share of the product's cheapest offer
# elsewhere is taken for a copy wearing the product's name.
COPY_PRICE_RATIO = Decimal("0.5")
# Above this multiple of its dearest offer elsewhere, a placeholder.
PLACEHOLDER_PRICE_RATIO = Decimal("3")


def _compact(value: str | None) -> str:
    """Lower-case a value and drop everything but letters and digits."""

    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _slugify(value: str, *, fallback: str) -> str:
    """Return a compact URL-safe slug."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")

    return slug[:200] or fallback


# Marketplaces that publish exact model names, in the order their spelling
# is preferred when more than one lists the same phone. PriceOye catalogues
# the most phones, so its names are the catalogue's default.
MODEL_NAME_AUTHORITIES = ("priceoye", "shophive")


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
            if payload.color is None:
                # A seller's colour lives in the title or nowhere.
                stated = detect_title_color(
                    clean_marketplace_title(
                        payload.title,
                        payload.seller_name,
                    )
                )
                if stated is not None:
                    payload = payload.model_copy(update={"color": stated})

            response = self._resolve(database_session, payload)

            if self._priced_out_of_line(database_session, payload, response):
                # Anything the match prepared (a colour variant) is undone.
                database_session.rollback()
                logger.info(
                    "Passed over a match-only listing priced far from its "
                    "product: platform=%s external_id=%s product_id=%s",
                    payload.platform_code,
                    payload.external_id,
                    response.canonical_product_id,
                )
                return ProductResolveResponse(
                    matched=False,
                    confidence=0,
                    reason=(
                        "Priced far from what the stores ask for this "
                        "product: likely a copy using its name, or a "
                        "listing not meant to sell."
                    ),
                )

            self._adopt_marketplace_name(database_session, payload, response)

            if (
                payload.exact_model_title
                and payload.platform_code
                and response.matched
                and response.product_variant_id
            ):
                # Noted now, not when the listing arrives: the next phone
                # in the same crawl batch has to see it.
                self.repository.note_named_by(
                    database_session,
                    variant_id=response.product_variant_id,
                    platform_code=payload.platform_code,
                    # Without variant words, so a tablet's "5G" names its
                    # connectivity, not a different product.
                    model_name=profile_for(
                        payload.category_slug
                    ).product_title(payload.title),
                )
            database_session.commit()
        except Exception:
            database_session.rollback()
            raise

        return response

    @staticmethod
    def _priced_out_of_line(
        database_session: Session,
        payload: ProductResolveRequest,
        response: ProductResolveResponse,
    ) -> bool:
        """Report whether a match-only listing's price rules it out.

        Compared with the offers the product has in stock on the other
        marketplaces: below half the cheapest, the listing is a copy using
        the product's name; above three times the dearest, a placeholder a
        seller keeps up so nobody buys it ("Do Not Purchase", Rs 99,999).
        """

        if (
            payload.allow_new_product
            or payload.listing_price is None
            or not response.matched
            or response.canonical_product_id is None
        ):
            return False

        cheapest, dearest = database_session.execute(
            select(
                func.min(ProductListing.current_price),
                func.max(ProductListing.current_price),
            )
            .join(ProductVariant, ProductVariant.id == ProductListing.product_variant_id)
            .join(Platform, Platform.id == ProductListing.platform_id)
            .where(
                ProductVariant.canonical_product_id == response.canonical_product_id,
                ProductListing.is_available.is_(True),
                Platform.code != payload.platform_code,
            )
        ).one()

        if cheapest is None:
            return False

        return (
            payload.listing_price < cheapest * COPY_PRICE_RATIO
            or payload.listing_price > dearest * PLACEHOLDER_PRICE_RATIO
        )

    def _resolve(
        self,
        database_session: Session,
        payload: ProductResolveRequest,
    ) -> ProductResolveResponse:
        # A listing VEXTRO already stores keeps its place: its mapping is
        # settled, and moving it would break its price history.
        settled = self.matching_service.resolve_exact_identity(
            database_session,
            payload,
        )

        if settled is not None:
            return ProductResolveResponse(**settled.model_dump())

        match = self.matching_service.match_product(
            database_session,
            payload,
        )

        if match.matched and (
            match.match_tier in AUTO_ATTACH_TIERS
            or match.confidence >= 100
        ):
            coloured = self._place_on_stated_colour(
                database_session,
                payload,
                match,
            )

            if coloured is not None:
                return coloured

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

    def _adopt_marketplace_name(
        self,
        database_session: Session,
        payload: ProductResolveRequest,
        response: ProductResolveResponse,
    ) -> None:
        """Name a phone the way the marketplace that catalogues it does.

        A product first seen through a seller's listing carries whatever
        could be salvaged from that seller's title. When a source that
        publishes exact model names resolves to the same phone, its name
        is the better one.
        """

        if not (
            payload.exact_model_title
            and response.matched
            and response.canonical_product_id
        ):
            return

        product = database_session.get(
            CanonicalProduct,
            response.canonical_product_id,
        )

        if product is None:
            return

        if self._named_by_another_marketplace(
            database_session,
            payload.platform_code,
            product.id,
        ):
            return

        brand_name = response.brand_name
        # Named as it was created: without the words that name a variant
        # ("11inch", "Wi-Fi"), which every variant's title would otherwise
        # take turns writing into the product's name.
        profile = profile_for(payload.category_slug)
        product_title = profile.product_title(payload.title)
        if profile.slug != "mobile-phones":
            # Cleaned as a new product's name is, so a second offer does not
            # rename the product to a longer spelling of the same model.
            product_title = clean_product_display_name(product_title) or product_title
        name = clean_model_name(product_title, brand_name)

        if (
            not name
            or name == product.name
            or cross_marketplace_product_key(name, brand_name)
            != cross_marketplace_product_key(product.name, brand_name)
        ):
            return

        if database_session.scalar(
            select(CanonicalProduct.id)
            .where(
                CanonicalProduct.brand_id == product.brand_id,
                CanonicalProduct.category_id == product.category_id,
                CanonicalProduct.model == name[:120],
                CanonicalProduct.id != product.id,
            )
            .limit(1)
        ) is not None:
            # Another product already carries the name; taking it would
            # break the one-name-per-model rule.
            return

        product.name = name[:255]
        product.model = name[:120]
        database_session.flush()
        response.product_name = product.name
        response.model = product.model

    def _named_by_another_marketplace(
        self,
        database_session: Session,
        platform_code: str | None,
        product_id: int,
    ) -> bool:
        """Report whether a marketplace ranked above this one names the phone.

        Two marketplaces that both publish exact model names still spell
        some phones differently ("Reno 15F" and "Reno 15F 5G"). Letting
        each rename the product would flip its name at every crawl, so the
        first marketplace in ``MODEL_NAME_AUTHORITIES`` that lists a phone
        is the one that names it.
        """

        if platform_code not in MODEL_NAME_AUTHORITIES:
            return False

        for other in MODEL_NAME_AUTHORITIES:
            if other == platform_code:
                return False

            if self.repository.platform_model_names(
                database_session,
                platform_code=other,
                product_ids={product_id},
            ):
                return True

        return False

    def _place_on_stated_colour(
        self,
        database_session: Session,
        payload: ProductResolveRequest,
        match,
    ) -> ProductResolveResponse | None:
        """File a listing under the colour it states, or under none.

        The matcher treats a missing colour as agreeing with anything. That
        filed every colour PriceOye states under the one colourless variant
        a seller listing had created, and filed seller listings that name
        no colour under whichever colour happened to rank first, so the
        product page showed them as that colour. The phone is the one the
        matcher chose; only the variant is made exact. Returns ``None``
        when the matched variant already agrees with the listing.
        """

        if match.canonical_product_id is None or not payload.allow_create:
            return None

        color = normalize_color(payload.color)

        if color is not None:
            if _compact(match.color) == _compact(color) or (
                match.color
                and _compact(match.color) in _compact(payload.title)
            ):
                # The same colour, or one the title spells out in full.
                return None
            # "Blue" is close enough to "Ocean Blue" for the matcher to
            # recognise the phone, but it is not that variant's name.
        else:
            if not match.color:
                return None

            title = clean_marketplace_title(
                payload.title,
                payload.seller_name,
            )

            if _compact(match.color) in _compact(title):
                # The seller wrote the colour into the title.
                return None

        # The new colour keeps the matched variant's whole identity, not
        # only its memory: a cellular tablet's other colour is cellular too.
        matched_variant = database_session.get(
            ProductVariant,
            match.product_variant_id,
        )
        extra_identity = {
            key: value
            for key, value in (
                (matched_variant.variant_attributes or {}).get(IDENTITY) or {}
                if matched_variant is not None
                else {}
            ).items()
            if key not in MEMORY_COLUMNS
        }

        variant = self.repository.get_variant(
            database_session,
            canonical_product_id=match.canonical_product_id,
            ram_gb=match.ram_gb,
            storage_gb=match.storage_gb,
            color=color,
            identity=extra_identity,
        )
        variant_created = variant is None

        if variant is None:
            variant = self.repository.create_variant(
                database_session,
                canonical_product_id=match.canonical_product_id,
                ram_gb=match.ram_gb,
                storage_gb=match.storage_gb,
                color=color,
                identity=extra_identity,
                sku=None,
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
            "Listing placed on its own colour: platform=%s "
            "external_id=%s product_id=%s variant_id=%s "
            "variant_created=%s color=%s",
            payload.platform_code,
            payload.external_id,
            match.canonical_product_id,
            variant.id,
            variant_created,
            color,
        )

        response = match.model_dump()
        response.update(
            product_variant_id=variant.id,
            color=color,
            reason=(
                "Matched the catalog product and placed the listing on "
                "the colour the marketplace states."
                if color is not None
                else "Matched the catalog product; the listing names no "
                "colour, so it was not filed under one."
            ),
        )

        return ProductResolveResponse(
            **response,
            variant_created=variant_created,
        )

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

        # A canonical product created from a raw marketplace title keeps the
        # seller's store name forever ("Carrefour Samsung Galaxy A07"), and
        # the same phone from another marketplace can then never find it.
        title = clean_marketplace_title(payload.title, payload.seller_name)
        profile = profile_for(payload.category_slug)
        # The product's name leaves out what names a variant ("Wi-Fi",
        # "44mm"); the full title is still read for the variant itself.
        name_title = profile.product_title(title)

        # The accessory rules describe what is not a phone; other categories
        # bring their own.
        if profile.slug == "mobile-phones" and is_accessory_title(title):
            logger.warning(
                "Declined to create a canonical product for an accessory: "
                "platform=%s external_id=%s",
                payload.platform_code,
                payload.external_id,
            )
            return None

        brand_name = infer_brand_name(
            title,
            payload.brand,
            # A store naming its own goods states their maker; outside
            # phones, models are often named after another brand's line.
            prefer_provided=payload.exact_model_title and profile.slug != "mobile-phones",
        )
        display_name = clean_model_name(
            clean_product_display_name(
                profile.product_title(payload.model) if payload.model else name_title
            )
            or clean_product_display_name(name_title),
            brand_name,
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

        category = self.repository.get_category(
            database_session,
            profile.slug,
        )

        if category is None:
            logger.error(
                "Cannot create canonical products: the %s category does "
                "not exist in the catalog.",
                profile.slug,
            )
            return None

        if payload.allow_new_product:
            brand = self._resolve_brand(database_session, brand_name)
        else:
            brand = self.repository.get_brand_by_name(
                database_session,
                brand_name,
            )
            if brand is None:
                return None

        specifications = merge_specifications(
            infer_title_specifications(title),
            payload.specifications,
        )

        if profile.reads_own_memory:
            ram_gb, storage_gb = profile.memory_from(
                title=title,
                specifications=payload.specifications,
            )
        else:
            ram_gb, storage_gb = extract_memory_capacities(
                specifications=payload.specifications,
                title=title,
            )
        if ram_gb is None:
            ram_gb = payload.ram_gb
        if storage_gb is None:
            storage_gb = payload.storage_gb
        if not profile.uses_memory:
            ram_gb = storage_gb = None

        color = normalize_color(payload.color)
        extra_identity = {
            key: value
            for key, value in profile.identity_from(
                title=title,
                specifications=payload.specifications,
            ).items()
            if key not in MEMORY_COLUMNS
        }

        product, product_created = self._resolve_canonical_product(
            database_session,
            platform_code=payload.platform_code,
            title=name_title,
            display_name=display_name,
            brand=brand,
            category_id=category.id,
            specifications=specifications,
            exact_model_title=payload.exact_model_title,
            may_create=payload.allow_new_product,
            word_order_matters=profile.slug == "mobile-phones",
        )

        if product is None:
            logger.info(
                "Left a listing for review: no catalogue product for it and "
                "its source may not create one: platform=%s external_id=%s",
                payload.platform_code,
                payload.external_id,
            )
            return None

        variant = self.repository.get_variant(
            database_session,
            canonical_product_id=product.id,
            ram_gb=ram_gb,
            storage_gb=storage_gb,
            color=color,
            identity=extra_identity,
        )

        if variant is None and profile.slug != "mobile-phones":
            # A seller title that states less than the catalogue knows
            # ("8GB RAM", no storage) joins the one variant it describes
            # instead of opening a half-described one beside it.
            variant = self.repository.get_variant_stating_more(
                database_session,
                canonical_product_id=product.id,
                ram_gb=ram_gb,
                storage_gb=storage_gb,
                color=color,
                identity=extra_identity,
            )

        variant_created = variant is None

        if variant is None:
            variant = self.repository.create_variant(
                database_session,
                canonical_product_id=product.id,
                ram_gb=ram_gb,
                storage_gb=storage_gb,
                color=color,
                identity=extra_identity,
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
        exact_model_title: bool = False,
        may_create: bool = True,
        word_order_matters: bool = True,
    ) -> tuple[CanonicalProduct | None, bool]:
        """Find the canonical phone for a title, or create it.

        A Daraz listing and a PriceOye listing for the same phone must land on
        one canonical product, so the brand-scoped cross-marketplace identity
        key is consulted before anything new is created. Without
        ``may_create`` a title naming no known product yields ``None``.
        """

        brand_id = brand.id if brand is not None else None
        brand_name = brand.name if brand is not None else None
        model = display_name[:120]

        existing = self.repository.get_canonical_product_by_model(
            database_session,
            brand_id=brand_id,
            model=model,
            category_id=category_id,
        )

        if existing is None and brand_id is not None:
            existing = self._find_cross_marketplace_product(
                database_session,
                title=title,
                brand_id=brand_id,
                brand_name=brand_name,
                category_id=category_id,
                word_order_matters=word_order_matters,
            )

        if existing is not None and exact_model_title and any(
            names_differ_on_5g(display_name, own_name)
            for own_name in self.repository.platform_model_names(
                database_session,
                platform_code=platform_code,
                product_ids={existing.id},
            ).get(existing.id, ())
        ):
            # The shared identity key ignores "5G"; a marketplace's own
            # model name does not, where it already uses the other
            # spelling for this phone and so sells both.
            existing = None

        if existing is not None:
            self.repository.merge_product_specifications(
                database_session,
                existing,
                merge_specifications(existing.specifications, specifications),
            )
            return existing, False

        if not may_create:
            return None, False

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
        category_id: int | None = None,
        word_order_matters: bool = True,
    ) -> CanonicalProduct | None:
        """Return the same product already registered under another title.

        Without ``word_order_matters`` the same words in another order are
        the same name: one store's "iPad Air M4 8th Gen" is another's
        "iPad Air 8th Gen M4". Phones keep the strict comparison they
        were tuned with.
        """

        identity = cross_marketplace_product_key(title, brand_name)

        def same(key: str) -> bool:
            if word_order_matters:
                return key == identity
            return sorted(key.split()) == sorted(identity.split())

        if not identity:
            return None

        # Every product of the brand is compared, with or without a listing:
        # a crawl registers a phone before its listing is delivered, and a
        # second title for it arriving in between used to register it twice.
        same_brand = database_session.scalars(
            select(CanonicalProduct)
            .where(
                CanonicalProduct.is_active.is_(True),
                CanonicalProduct.brand_id == brand_id,
                *(
                    (CanonicalProduct.category_id == category_id,)
                    if category_id is not None
                    else ()
                ),
            )
            .order_by(CanonicalProduct.id.asc())
        )

        for candidate in same_brand:
            if same(
                cross_marketplace_product_key(candidate.name, brand_name)
            ) or same(
                cross_marketplace_product_key(candidate.model, brand_name)
            ):
                return candidate

        # ``find_cross_platform_canonical`` only inspects products that
        # already carry a listing from a different platform, which is exactly
        # the cross-marketplace case; pass a platform id that cannot match so
        # every other platform's products stay eligible.
        return find_cross_platform_canonical(
            database_session,
            title=title,
            brand_id=brand_id,
            incoming_platform_id=-1,
            category_id=category_id,
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
