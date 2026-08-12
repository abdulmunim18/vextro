"""Database operations for SME business intelligence."""

from sqlalchemy import (
    exists,
    func,
    or_,
    select,
)
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.business_product import BusinessProduct
from app.models.canonical_product import CanonicalProduct
from app.models.competitor_watchlist import (
    CompetitorWatchlist,
)
from app.models.organization import Organization
from app.models.organization_user import OrganizationUser
from app.models.product_listing import ProductListing
from app.models.price_history import PriceHistory
from app.models.platform import Platform
from app.models.seller import Seller


@dataclass(frozen=True)
class CompetitorIntelligenceRecord:
    """Joined data required for an SME competitor insight."""

    watchlist: CompetitorWatchlist
    business_product: BusinessProduct
    listing: ProductListing
    platform_name: str
    seller_name: str | None
    history: tuple[PriceHistory, ...]


class SMERepository:
    """Database operations for organizations and SME products."""

    @staticmethod
    def organization_slug_exists(
        database_session: Session,
        slug: str,
    ) -> bool:
        """Return whether an organization slug already exists."""

        statement = select(
            exists().where(
                Organization.slug == slug,
            ),
        )

        return bool(
            database_session.scalar(statement),
        )

    @staticmethod
    def create_organization(
        database_session: Session,
        *,
        owner_user_id: int,
        name: str,
        slug: str,
        industry: str | None,
    ) -> Organization:
        """Create an organization and its owner membership."""

        organization = Organization(
            owner_user_id=owner_user_id,
            name=name,
            slug=slug,
            industry=industry,
            is_active=True,
        )

        database_session.add(organization)
        database_session.flush()

        owner_membership = OrganizationUser(
            organization_id=organization.id,
            user_id=owner_user_id,
            membership_role="owner",
            is_active=True,
        )

        database_session.add(owner_membership)
        database_session.flush()

        return organization

    @staticmethod
    def get_organization_for_user(
        database_session: Session,
        *,
        organization_id: int,
        user_id: int,
        include_inactive: bool = False,
    ) -> Organization | None:
        """Return an organization accessible to one user."""

        membership_exists = exists(
            select(OrganizationUser.id).where(
                OrganizationUser.organization_id
                == Organization.id,
                OrganizationUser.user_id == user_id,
                OrganizationUser.is_active.is_(True),
            ),
        )

        conditions = [
            Organization.id == organization_id,
            or_(
                Organization.owner_user_id == user_id,
                membership_exists,
            ),
        ]

        if not include_inactive:
            conditions.append(
                Organization.is_active.is_(True),
            )

        statement = select(Organization).where(
            *conditions,
        )

        return database_session.scalar(statement)

    @staticmethod
    def list_organizations_for_user(
        database_session: Session,
        *,
        user_id: int,
    ) -> list[Organization]:
        """Return active organizations accessible to a user."""

        membership_exists = exists(
            select(OrganizationUser.id).where(
                OrganizationUser.organization_id
                == Organization.id,
                OrganizationUser.user_id == user_id,
                OrganizationUser.is_active.is_(True),
            ),
        )

        statement = (
            select(Organization)
            .where(
                Organization.is_active.is_(True),
                or_(
                    Organization.owner_user_id
                    == user_id,
                    membership_exists,
                ),
            )
            .order_by(
                Organization.created_at.desc(),
            )
        )

        return list(
            database_session.scalars(statement),
        )

    @staticmethod
    def update_organization(
        database_session: Session,
        organization: Organization,
        *,
        name: str | None = None,
        slug: str | None = None,
        industry: str | None = None,
        update_industry: bool = False,
    ) -> Organization:
        """Update organization fields."""

        if name is not None:
            organization.name = name

        if slug is not None:
            organization.slug = slug

        if update_industry:
            organization.industry = industry

        database_session.flush()

        return organization

    @staticmethod
    def get_active_canonical_product(
        database_session: Session,
        canonical_product_id: int,
    ) -> CanonicalProduct | None:
        """Return one active canonical product."""

        statement = select(
            CanonicalProduct,
        ).where(
            CanonicalProduct.id
            == canonical_product_id,
            CanonicalProduct.is_active.is_(True),
        )

        return database_session.scalar(statement)

    @staticmethod
    def business_product_sku_exists(
        database_session: Session,
        *,
        organization_id: int,
        sku: str,
        exclude_product_id: int | None = None,
    ) -> bool:
        """Check whether an SKU already exists in an organization."""

        conditions = [
            BusinessProduct.organization_id
            == organization_id,
            func.lower(BusinessProduct.sku)
            == sku.strip().lower(),
        ]

        if exclude_product_id is not None:
            conditions.append(
                BusinessProduct.id
                != exclude_product_id,
            )

        statement = select(
            exists().where(*conditions),
        )

        return bool(
            database_session.scalar(statement),
        )

    @staticmethod
    def create_business_product(
        database_session: Session,
        *,
        organization_id: int,
        canonical_product_id: int | None,
        name: str,
        sku: str | None,
        cost_price,
        selling_price,
        currency: str,
        stock_level: int,
        reorder_level: int,
    ) -> BusinessProduct:
        """Create an SME business product."""

        product = BusinessProduct(
            organization_id=organization_id,
            canonical_product_id=(
                canonical_product_id
            ),
            name=name,
            sku=sku,
            cost_price=cost_price,
            selling_price=selling_price,
            currency=currency,
            stock_level=stock_level,
            reorder_level=reorder_level,
            is_active=True,
        )

        database_session.add(product)
        database_session.flush()

        return product

    @staticmethod
    def get_business_product(
        database_session: Session,
        *,
        organization_id: int,
        product_id: int,
        include_inactive: bool = False,
    ) -> BusinessProduct | None:
        """Return one product belonging to an organization."""

        conditions = [
            BusinessProduct.id == product_id,
            BusinessProduct.organization_id
            == organization_id,
        ]

        if not include_inactive:
            conditions.append(
                BusinessProduct.is_active.is_(True),
            )

        statement = select(
            BusinessProduct,
        ).where(*conditions)

        return database_session.scalar(statement)

    @staticmethod
    def list_business_products(
        database_session: Session,
        *,
        organization_id: int,
        query: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[int, list[BusinessProduct]]:
        """Return filtered and paginated organization products."""

        conditions = [
            BusinessProduct.organization_id
            == organization_id,
        ]

        if query:
            search_term = (
                f"%{query.strip()}%"
            )

            conditions.append(
                or_(
                    BusinessProduct.name.ilike(
                        search_term,
                    ),
                    BusinessProduct.sku.ilike(
                        search_term,
                    ),
                ),
            )

        if is_active is not None:
            conditions.append(
                BusinessProduct.is_active
                == is_active,
            )

        total_statement = select(
            func.count(BusinessProduct.id),
        ).where(*conditions)

        total = int(
            database_session.scalar(
                total_statement,
            )
            or 0
        )

        statement = (
            select(BusinessProduct)
            .where(*conditions)
            .order_by(
                BusinessProduct.created_at.desc(),
            )
            .offset(
                (page - 1) * page_size,
            )
            .limit(page_size)
        )

        items = list(
            database_session.scalars(statement),
        )

        return total, items

    @staticmethod
    def update_business_product(
        database_session: Session,
        product: BusinessProduct,
        *,
        update_data: dict[str, object],
    ) -> BusinessProduct:
        """Apply validated fields to a business product."""

        for field_name, field_value in (
            update_data.items()
        ):
            setattr(
                product,
                field_name,
                field_value,
            )

        database_session.flush()

        return product

    @staticmethod
    def get_marketplace_listing(
        database_session: Session,
        listing_id: int,
    ) -> ProductListing | None:
        """Return one marketplace listing."""

        statement = select(
            ProductListing,
        ).where(
            ProductListing.id == listing_id,
        )

        return database_session.scalar(statement)

    @staticmethod
    def get_watchlist_entry(
        database_session: Session,
        *,
        organization_id: int,
        watchlist_id: int,
    ) -> CompetitorWatchlist | None:
        """Return one competitor watchlist entry."""

        statement = select(
            CompetitorWatchlist,
        ).where(
            CompetitorWatchlist.id
            == watchlist_id,
            CompetitorWatchlist.organization_id
            == organization_id,
        )

        return database_session.scalar(statement)

    @staticmethod
    def find_duplicate_watchlist_entry(
        database_session: Session,
        *,
        organization_id: int,
        business_product_id: int,
        listing_id: int,
    ) -> CompetitorWatchlist | None:
        """Find an existing competitor mapping."""

        statement = select(
            CompetitorWatchlist,
        ).where(
            CompetitorWatchlist.organization_id
            == organization_id,
            CompetitorWatchlist.business_product_id
            == business_product_id,
            CompetitorWatchlist.listing_id
            == listing_id,
        )

        return database_session.scalar(statement)

    @staticmethod
    def create_watchlist_entry(
        database_session: Session,
        *,
        organization_id: int,
        business_product_id: int,
        listing_id: int,
        risk_threshold_percentage,
    ) -> CompetitorWatchlist:
        """Create a competitor watchlist entry."""

        entry = CompetitorWatchlist(
            organization_id=organization_id,
            business_product_id=(
                business_product_id
            ),
            listing_id=listing_id,
            risk_threshold_percentage=risk_threshold_percentage,
            is_active=True,
        )

        database_session.add(entry)
        database_session.flush()

        return entry

    @staticmethod
    def list_watchlist_entries(
        database_session: Session,
        *,
        organization_id: int,
        is_active: bool | None = None,
    ) -> list[CompetitorWatchlist]:
        """Return competitor entries for an organization."""

        conditions = [
            CompetitorWatchlist.organization_id
            == organization_id,
        ]

        if is_active is not None:
            conditions.append(
                CompetitorWatchlist.is_active
                == is_active,
            )

        statement = (
            select(CompetitorWatchlist)
            .where(*conditions)
            .order_by(
                CompetitorWatchlist.created_at.desc(),
            )
        )

        return list(
            database_session.scalars(statement),
        )

    @staticmethod
    def update_watchlist_status(
        database_session: Session,
        entry: CompetitorWatchlist,
        *,
        is_active: bool,
    ) -> CompetitorWatchlist:
        """Activate or deactivate competitor monitoring."""

        entry.is_active = is_active

        if is_active:
            entry.last_risk_level = None

        database_session.flush()

        return entry

    @staticmethod
    def get_lowest_competitor_price(
        database_session: Session,
        *,
        organization_id: int,
        business_product_id: int,
    ):
        """Return the lowest active available monitored price."""

        statement = (
            select(func.min(ProductListing.current_price))
            .join(
                CompetitorWatchlist,
                CompetitorWatchlist.listing_id
                == ProductListing.id,
            )
            .where(
                CompetitorWatchlist.organization_id
                == organization_id,
                CompetitorWatchlist.business_product_id
                == business_product_id,
                CompetitorWatchlist.is_active.is_(True),
                ProductListing.is_available.is_(True),
            )
        )

        return database_session.scalar(statement)

    @staticmethod
    def list_competitor_intelligence_records(
        database_session: Session,
        *,
        organization_id: int,
    ) -> list[CompetitorIntelligenceRecord]:
        """Return active monitored listings with recent price history."""

        statement = (
            select(
                CompetitorWatchlist,
                BusinessProduct,
                ProductListing,
                Platform.name,
                Seller.name,
            )
            .join(
                BusinessProduct,
                BusinessProduct.id
                == CompetitorWatchlist.business_product_id,
            )
            .join(
                ProductListing,
                ProductListing.id
                == CompetitorWatchlist.listing_id,
            )
            .join(
                Platform,
                Platform.id == ProductListing.platform_id,
            )
            .outerjoin(
                Seller,
                Seller.id == ProductListing.seller_id,
            )
            .where(
                CompetitorWatchlist.organization_id
                == organization_id,
                CompetitorWatchlist.is_active.is_(True),
                BusinessProduct.is_active.is_(True),
            )
            .order_by(
                BusinessProduct.name.asc(),
                ProductListing.current_price.asc(),
            )
        )

        rows = database_session.execute(statement).all()
        listing_ids = [row[2].id for row in rows]
        history_by_listing: dict[int, list[PriceHistory]] = {
            listing_id: []
            for listing_id in listing_ids
        }

        if listing_ids:
            history_statement = (
                select(PriceHistory)
                .where(
                    PriceHistory.listing_id.in_(listing_ids),
                )
                .order_by(
                    PriceHistory.listing_id.asc(),
                    PriceHistory.captured_at.desc(),
                )
            )

            for point in database_session.scalars(history_statement):
                points = history_by_listing[point.listing_id]

                if len(points) < 30:
                    points.append(point)

        return [
            CompetitorIntelligenceRecord(
                watchlist=row[0],
                business_product=row[1],
                listing=row[2],
                platform_name=row[3],
                seller_name=row[4],
                history=tuple(
                    reversed(history_by_listing[row[2].id])
                ),
            )
            for row in rows
        ]
