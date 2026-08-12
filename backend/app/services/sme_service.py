"""Business logic for SME business intelligence."""

import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from math import ceil
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.business_product import BusinessProduct
from app.models.competitor_watchlist import (
    CompetitorWatchlist,
)
from app.models.organization import Organization
from app.repositories.sme_repository import SMERepository
from app.schemas.sme import (
    BusinessProductCreate,
    BusinessProductListResponse,
    BusinessProductResponse,
    BusinessProductUpdate,
    CompetitorWatchlistCreate,
    CompetitorWatchlistListResponse,
    CompetitorWatchlistResponse,
    CompetitorWatchlistStatusUpdate,
    CompetitorInsightResponse,
    CompetitorIntelligenceResponse,
    CompetitorIntelligenceSummary,
    CompetitorTimelinePoint,
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationResponse,
    OrganizationUpdate,
)


class SMEService:
    """Manage SME organizations, products and competitors."""

    def __init__(
        self,
        repository: SMERepository | None = None,
    ) -> None:
        self.repository = repository or SMERepository()

    @staticmethod
    def _build_slug_base(
        value: str,
    ) -> str:
        """Convert an organization name into a URL-safe slug."""

        normalized_value = unicodedata.normalize(
            "NFKD",
            value,
        )

        ascii_value = normalized_value.encode(
            "ascii",
            "ignore",
        ).decode("ascii")

        slug = re.sub(
            r"[^a-z0-9]+",
            "-",
            ascii_value.lower(),
        ).strip("-")

        return slug or "organization"

    def _generate_unique_slug(
        self,
        database_session: Session,
        organization_name: str,
    ) -> str:
        """Generate a unique organization slug."""

        base_slug = self._build_slug_base(
            organization_name,
        )

        candidate = base_slug
        suffix = 2

        while self.repository.organization_slug_exists(
            database_session,
            candidate,
        ):
            candidate = f"{base_slug}-{suffix}"
            suffix += 1

        return candidate

    def _get_accessible_organization(
        self,
        database_session: Session,
        *,
        organization_id: int,
        user_id: int,
        include_inactive: bool = False,
    ) -> Organization:
        """Return an organization or raise an access-safe 404."""

        organization = (
            self.repository.get_organization_for_user(
                database_session,
                organization_id=organization_id,
                user_id=user_id,
                include_inactive=include_inactive,
            )
        )

        if organization is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "The requested organization "
                    "was not found."
                ),
            )

        return organization

    @staticmethod
    def _normalize_sku(
        sku: str | None,
    ) -> str | None:
        """Normalize optional SME product SKUs."""

        if sku is None:
            return None

        normalized_sku = sku.strip().upper()

        return normalized_sku or None

    @staticmethod
    def _commit_and_refresh(
        database_session: Session,
        entity: Any,
        *,
        conflict_detail: str,
    ) -> None:
        """Commit one transaction and refresh its main entity."""

        try:
            database_session.commit()
        except IntegrityError as error:
            database_session.rollback()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=conflict_detail,
            ) from error

        except Exception:
            database_session.rollback()
            raise

        database_session.refresh(entity)

    def create_organization(
        self,
        database_session: Session,
        *,
        user_id: int,
        payload: OrganizationCreate,
    ) -> OrganizationResponse:
        """Create an organization owned by an SME user."""

        slug = self._generate_unique_slug(
            database_session,
            payload.name,
        )

        try:
            organization = (
                self.repository.create_organization(
                    database_session,
                    owner_user_id=user_id,
                    name=payload.name,
                    slug=slug,
                    industry=payload.industry,
                )
            )

            self._commit_and_refresh(
                database_session,
                organization,
                conflict_detail=(
                    "An organization with these "
                    "details already exists."
                ),
            )

        except HTTPException:
            raise

        except Exception:
            database_session.rollback()
            raise

        return OrganizationResponse.model_validate(
            organization,
        )

    def list_organizations(
        self,
        database_session: Session,
        *,
        user_id: int,
    ) -> OrganizationListResponse:
        """Return organizations accessible to an SME user."""

        organizations = (
            self.repository.list_organizations_for_user(
                database_session,
                user_id=user_id,
            )
        )

        return OrganizationListResponse(
            total=len(organizations),
            items=[
                OrganizationResponse.model_validate(
                    organization,
                )
                for organization in organizations
            ],
        )

    def read_organization(
        self,
        database_session: Session,
        *,
        organization_id: int,
        user_id: int,
    ) -> OrganizationResponse:
        """Return one accessible organization."""

        organization = self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        return OrganizationResponse.model_validate(
            organization,
        )

    def update_organization(
        self,
        database_session: Session,
        *,
        organization_id: int,
        user_id: int,
        payload: OrganizationUpdate,
    ) -> OrganizationResponse:
        """Update an organization belonging to the user."""

        organization = self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        supplied_fields = payload.model_fields_set

        new_slug = None

        if (
            "name" in supplied_fields
            and payload.name is not None
            and payload.name.casefold()
            != organization.name.casefold()
        ):
            new_slug = self._generate_unique_slug(
                database_session,
                payload.name,
            )

        try:
            organization = (
                self.repository.update_organization(
                    database_session,
                    organization,
                    name=(
                        payload.name
                        if "name" in supplied_fields
                        else None
                    ),
                    slug=new_slug,
                    industry=payload.industry,
                    update_industry=(
                        "industry" in supplied_fields
                    ),
                )
            )

            self._commit_and_refresh(
                database_session,
                organization,
                conflict_detail=(
                    "The organization could not "
                    "be updated because its new "
                    "details conflict with another "
                    "organization."
                ),
            )

        except HTTPException:
            raise

        except Exception:
            database_session.rollback()
            raise

        return OrganizationResponse.model_validate(
            organization,
        )

    def create_business_product(
        self,
        database_session: Session,
        *,
        organization_id: int,
        user_id: int,
        payload: BusinessProductCreate,
    ) -> BusinessProductResponse:
        """Create a product inside an SME organization."""

        self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        if payload.currency != "PKR":
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_ENTITY
                ),
                detail=(
                    "Only PKR currency is currently "
                    "supported."
                ),
            )

        if payload.canonical_product_id is not None:
            canonical_product = (
                self.repository.get_active_canonical_product(
                    database_session,
                    payload.canonical_product_id,
                )
            )

            if canonical_product is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=(
                        "The requested canonical "
                        "product was not found or "
                        "is inactive."
                    ),
                )

        normalized_sku = self._normalize_sku(
            payload.sku,
        )

        if (
            normalized_sku is not None
            and self.repository.business_product_sku_exists(
                database_session,
                organization_id=organization_id,
                sku=normalized_sku,
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "This SKU already exists in "
                    "the organization."
                ),
            )

        try:
            product = (
                self.repository.create_business_product(
                    database_session,
                    organization_id=organization_id,
                    canonical_product_id=(
                        payload.canonical_product_id
                    ),
                    name=payload.name,
                    sku=normalized_sku,
                    cost_price=payload.cost_price,
                    selling_price=(
                        payload.selling_price
                    ),
                    currency=payload.currency,
                    stock_level=payload.stock_level,
                    reorder_level=(
                        payload.reorder_level
                    ),
                )
            )

            self._commit_and_refresh(
                database_session,
                product,
                conflict_detail=(
                    "This product already exists "
                    "in the organization."
                ),
            )

        except HTTPException:
            raise

        except Exception:
            database_session.rollback()
            raise

        return BusinessProductResponse.model_validate(
            product,
        )

    def list_business_products(
        self,
        database_session: Session,
        *,
        organization_id: int,
        user_id: int,
        query: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> BusinessProductListResponse:
        """Return filtered organization products."""

        self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        total, products = (
            self.repository.list_business_products(
                database_session,
                organization_id=organization_id,
                query=query,
                is_active=is_active,
                page=page,
                page_size=page_size,
            )
        )

        total_pages = (
            ceil(total / page_size)
            if total > 0
            else 0
        )

        return BusinessProductListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=[
                BusinessProductResponse.model_validate(
                    product,
                )
                for product in products
            ],
        )

    def read_business_product(
        self,
        database_session: Session,
        *,
        organization_id: int,
        product_id: int,
        user_id: int,
    ) -> BusinessProductResponse:
        """Return one organization product."""

        self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        product = self.repository.get_business_product(
            database_session,
            organization_id=organization_id,
            product_id=product_id,
            include_inactive=True,
        )

        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "The requested business product "
                    "was not found."
                ),
            )

        return BusinessProductResponse.model_validate(
            product,
        )

    def update_business_product(
        self,
        database_session: Session,
        *,
        organization_id: int,
        product_id: int,
        user_id: int,
        payload: BusinessProductUpdate,
    ) -> BusinessProductResponse:
        """Update one SME business product."""

        self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        product = self.repository.get_business_product(
            database_session,
            organization_id=organization_id,
            product_id=product_id,
            include_inactive=True,
        )

        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "The requested business product "
                    "was not found."
                ),
            )

        update_data = payload.model_dump(
            exclude_unset=True,
        )

        if "currency" in update_data:
            currency = update_data["currency"]

            if currency != "PKR":
                raise HTTPException(
                    status_code=(
                        status
                        .HTTP_422_UNPROCESSABLE_ENTITY
                    ),
                    detail=(
                        "Only PKR currency is "
                        "currently supported."
                    ),
                )

        if "canonical_product_id" in update_data:
            canonical_product_id = update_data[
                "canonical_product_id"
            ]

            if canonical_product_id is not None:
                canonical_product = (
                    self.repository
                    .get_active_canonical_product(
                        database_session,
                        int(canonical_product_id),
                    )
                )

                if canonical_product is None:
                    raise HTTPException(
                        status_code=(
                            status.HTTP_404_NOT_FOUND
                        ),
                        detail=(
                            "The requested canonical "
                            "product was not found or "
                            "is inactive."
                        ),
                    )

        if "sku" in update_data:
            normalized_sku = self._normalize_sku(
                update_data["sku"],
            )

            update_data["sku"] = normalized_sku

            if (
                normalized_sku is not None
                and self.repository
                .business_product_sku_exists(
                    database_session,
                    organization_id=organization_id,
                    sku=normalized_sku,
                    exclude_product_id=product.id,
                )
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This SKU already exists "
                        "in the organization."
                    ),
                )

        try:
            product = (
                self.repository.update_business_product(
                    database_session,
                    product,
                    update_data=update_data,
                )
            )

            self._commit_and_refresh(
                database_session,
                product,
                conflict_detail=(
                    "The business product could "
                    "not be updated because its "
                    "new details conflict with "
                    "another product."
                ),
            )

        except HTTPException:
            raise

        except Exception:
            database_session.rollback()
            raise

        return BusinessProductResponse.model_validate(
            product,
        )

    def create_watchlist_entry(
        self,
        database_session: Session,
        *,
        organization_id: int,
        user_id: int,
        payload: CompetitorWatchlistCreate,
    ) -> CompetitorWatchlistResponse:
        """Add a competitor listing to SME monitoring."""

        self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        business_product = (
            self.repository.get_business_product(
                database_session,
                organization_id=organization_id,
                product_id=payload.business_product_id,
            )
        )

        if business_product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "The requested business product "
                    "was not found or is inactive."
                ),
            )

        marketplace_listing = (
            self.repository.get_marketplace_listing(
                database_session,
                payload.listing_id,
            )
        )

        if marketplace_listing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "The requested marketplace "
                    "listing was not found."
                ),
            )

        existing_entry = (
            self.repository
            .find_duplicate_watchlist_entry(
                database_session,
                organization_id=organization_id,
                business_product_id=(
                    payload.business_product_id
                ),
                listing_id=payload.listing_id,
            )
        )

        if existing_entry is not None:
            if existing_entry.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This competitor listing is "
                        "already being monitored."
                    ),
                )

            existing_entry = (
                self.repository.update_watchlist_status(
                    database_session,
                    existing_entry,
                    is_active=True,
                )
            )

            self._commit_and_refresh(
                database_session,
                existing_entry,
                conflict_detail=(
                    "The competitor watchlist entry "
                    "could not be reactivated."
                ),
            )

            return (
                CompetitorWatchlistResponse
                .model_validate(existing_entry)
            )

        try:
            entry = (
                self.repository.create_watchlist_entry(
                    database_session,
                    organization_id=organization_id,
                    business_product_id=(
                        payload.business_product_id
                    ),
                    listing_id=payload.listing_id,
                    risk_threshold_percentage=(
                        payload.risk_threshold_percentage
                    ),
                )
            )

            self._commit_and_refresh(
                database_session,
                entry,
                conflict_detail=(
                    "This competitor listing is "
                    "already being monitored."
                ),
            )

        except HTTPException:
            raise

        except Exception:
            database_session.rollback()
            raise

        return CompetitorWatchlistResponse.model_validate(
            entry,
        )

    def list_watchlist_entries(
        self,
        database_session: Session,
        *,
        organization_id: int,
        user_id: int,
        is_active: bool | None,
    ) -> CompetitorWatchlistListResponse:
        """Return an organization's competitor entries."""

        self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        entries = (
            self.repository.list_watchlist_entries(
                database_session,
                organization_id=organization_id,
                is_active=is_active,
            )
        )

        return CompetitorWatchlistListResponse(
            total=len(entries),
            items=[
                CompetitorWatchlistResponse
                .model_validate(entry)
                for entry in entries
            ],
        )

    def update_watchlist_status(
        self,
        database_session: Session,
        *,
        organization_id: int,
        watchlist_id: int,
        user_id: int,
        payload: CompetitorWatchlistStatusUpdate,
    ) -> CompetitorWatchlistResponse:
        """Activate or deactivate competitor monitoring."""

        self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        entry = self.repository.get_watchlist_entry(
            database_session,
            organization_id=organization_id,
            watchlist_id=watchlist_id,
        )

        if entry is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "The requested competitor "
                    "watchlist entry was not found."
                ),
            )

        try:
            entry = (
                self.repository.update_watchlist_status(
                    database_session,
                    entry,
                    is_active=payload.is_active,
                )
            )

            self._commit_and_refresh(
                database_session,
                entry,
                conflict_detail=(
                    "The competitor watchlist "
                    "status could not be updated."
                ),
            )

        except HTTPException:
            raise

        except Exception:
            database_session.rollback()
            raise

        return CompetitorWatchlistResponse.model_validate(
            entry,
        )

    def get_competitor_intelligence(
        self,
        database_session: Session,
        *,
        organization_id: int,
        user_id: int,
        risk_threshold_percentage: Decimal,
    ) -> CompetitorIntelligenceResponse:
        """Return price gaps, timelines, risk and market-share estimates."""

        self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )
        records = self.repository.list_competitor_intelligence_records(
            database_session,
            organization_id=organization_id,
        )
        records_by_product: dict[int, list[Any]] = {}

        for record in records:
            records_by_product.setdefault(
                record.business_product.id,
                [],
            ).append(record)

        market_share_by_product: dict[int, Decimal | None] = {}

        for product_id, product_records in records_by_product.items():
            own_price = product_records[0].business_product.selling_price

            if own_price is None or own_price <= 0:
                market_share_by_product[product_id] = None
                continue

            own_weight = Decimal("1") / own_price
            competitor_weights = sum(
                (
                    Decimal("1") / record.listing.current_price
                    for record in product_records
                    if record.listing.current_price > 0
                ),
                Decimal("0"),
            )
            total_weight = own_weight + competitor_weights
            market_share_by_product[product_id] = (
                own_weight
                / total_weight
                * Decimal("100")
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

        items: list[CompetitorInsightResponse] = []
        gap_values: list[Decimal] = []
        at_risk_product_ids: set[int] = set()

        for record in records:
            own_price = record.business_product.selling_price
            competitor_price = record.listing.current_price
            gap: Decimal | None = None
            gap_percentage: Decimal | None = None
            risk_reasons: list[str] = []

            if own_price is None:
                position = "unknown"
                risk_level = "medium"
                risk_reasons.append(
                    "Add a selling price to calculate the competitor gap."
                )
            else:
                gap = (own_price - competitor_price).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )
                gap_values.append(gap)
                gap_percentage = (
                    gap
                    / competitor_price
                    * Decimal("100")
                ).quantize(
                    Decimal("0.01"),
                    rounding=ROUND_HALF_UP,
                )

                if gap > 0:
                    position = "above_competitor"
                elif gap < 0:
                    position = "below_competitor"
                else:
                    position = "matched"

                if gap_percentage >= risk_threshold_percentage:
                    risk_level = "high"
                    at_risk_product_ids.add(record.business_product.id)
                    risk_reasons.append(
                        "Own price exceeds the monitored competitor by "
                        f"{gap_percentage}%."
                    )
                elif gap_percentage > 0:
                    risk_level = "medium"
                    risk_reasons.append(
                        "Own price is above the competitor but below the "
                        "configured risk threshold."
                    )
                else:
                    risk_level = "low"

            if not record.listing.is_available:
                risk_reasons.append(
                    "Competitor listing is currently unavailable."
                )

            items.append(
                CompetitorInsightResponse(
                    watchlist_id=record.watchlist.id,
                    business_product_id=record.business_product.id,
                    listing_id=record.listing.id,
                    own_product_name=record.business_product.name,
                    own_price=own_price,
                    competitor_price=competitor_price,
                    currency=record.listing.currency,
                    platform_name=record.platform_name,
                    seller_name=record.seller_name,
                    price_gap=gap,
                    price_gap_percentage=gap_percentage,
                    price_position=position,
                    risk_level=risk_level,
                    risk_reasons=risk_reasons,
                    estimated_own_market_share_percentage=(
                        market_share_by_product[
                            record.business_product.id
                        ]
                    ),
                    timeline=[
                        CompetitorTimelinePoint(
                            price=point.price,
                            is_available=point.is_available,
                            captured_at=point.captured_at,
                        )
                        for point in record.history
                    ],
                )
            )

        market_shares = [
            share
            for share in market_share_by_product.values()
            if share is not None
        ]
        average_gap = (
            (
                sum(gap_values, Decimal("0"))
                / Decimal(len(gap_values))
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            if gap_values
            else None
        )
        average_market_share = (
            (
                sum(market_shares, Decimal("0"))
                / Decimal(len(market_shares))
            ).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )
            if market_shares
            else None
        )

        return CompetitorIntelligenceResponse(
            organization_id=organization_id,
            generated_at=datetime.now(timezone.utc),
            summary=CompetitorIntelligenceSummary(
                tracked_competitors=len(records),
                tracked_products=len(records_by_product),
                average_price_gap=average_gap,
                products_at_risk=len(at_risk_product_ids),
                estimated_average_market_share_percentage=(
                    average_market_share
                ),
                risk_threshold_percentage=risk_threshold_percentage,
                estimation_note=(
                    "Market share is a transparent price-competitiveness "
                    "estimate based on inverse prices, not marketplace "
                    "sales-volume data."
                ),
            ),
            items=items,
        )
