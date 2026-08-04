from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.canonical_product import CanonicalProduct
from app.models.price_alert import PriceAlert
from app.models.product_listing import ProductListing
from app.models.role import Role
from app.models.user import User


class AdminRepository:
    """Database queries used by the administration service."""

    @staticmethod
    def _count(
        database_session: Session,
        statement,
    ) -> int:
        result = database_session.scalar(statement)

        return int(result or 0)

    @classmethod
    def count_users_by_role(
        cls,
        database_session: Session,
        role_name: str,
    ) -> int:
        normalized_role = role_name.strip().lower()

        statement = (
            select(func.count(func.distinct(User.id)))
            .select_from(User)
            .join(User.roles)
            .where(
                func.lower(Role.name) == normalized_role,
            )
        )

        return cls._count(
            database_session,
            statement,
        )

    @classmethod
    def get_dashboard_statistics(
        cls,
        database_session: Session,
    ) -> dict[str, int]:
        """Return statistics supported by current database tables."""

        return {
            "total_users": cls._count(
                database_session,
                select(func.count())
                .select_from(User),
            ),
            "active_users": cls._count(
                database_session,
                select(func.count())
                .select_from(User)
                .where(User.is_active.is_(True)),
            ),
            "consumer_users": cls.count_users_by_role(
                database_session,
                "consumer",
            ),
            "sme_users": cls.count_users_by_role(
                database_session,
                "sme",
            ),
            "admin_users": cls.count_users_by_role(
                database_session,
                "admin",
            ),
            "canonical_products": cls._count(
                database_session,
                select(func.count())
                .select_from(CanonicalProduct),
            ),
            "active_products": cls._count(
                database_session,
                select(func.count())
                .select_from(CanonicalProduct)
                .where(
                    CanonicalProduct.is_active.is_(True),
                ),
            ),
            "marketplace_listings": cls._count(
                database_session,
                select(func.count())
                .select_from(ProductListing),
            ),
            "available_listings": cls._count(
                database_session,
                select(func.count())
                .select_from(ProductListing)
                .where(
                    ProductListing.is_available.is_(True),
                ),
            ),
            "total_price_alerts": cls._count(
                database_session,
                select(func.count())
                .select_from(PriceAlert),
            ),
            "active_price_alerts": cls._count(
                database_session,
                select(func.count())
                .select_from(PriceAlert)
                .where(
                    PriceAlert.is_active.is_(True),
                ),
            ),
            "triggered_price_alerts": cls._count(
                database_session,
                select(func.count())
                .select_from(PriceAlert)
                .where(
                    PriceAlert.is_triggered.is_(True),
                ),
            ),
        }