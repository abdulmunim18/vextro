from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

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
                select(func.count()).select_from(User),
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
                select(func.count()).select_from(
                    CanonicalProduct
                ),
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
                select(func.count()).select_from(
                    ProductListing
                ),
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
                select(func.count()).select_from(
                    PriceAlert
                ),
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

    @staticmethod
    def list_users(
        database_session: Session,
        *,
        query: str | None,
        role: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[User], int]:
        """Return filtered users and their total matching count."""

        user_statement = select(User).options(
            selectinload(User.roles)
        )

        count_statement = (
            select(func.count(func.distinct(User.id)))
            .select_from(User)
        )

        filters = []

        if query:
            normalized_query = query.strip()

            if normalized_query:
                search_pattern = (
                    f"%{normalized_query}%"
                )

                filters.append(
                    or_(
                        User.full_name.ilike(
                            search_pattern
                        ),
                        User.email.ilike(
                            search_pattern
                        ),
                    )
                )

        if role:
            normalized_role = role.strip().lower()

            user_statement = user_statement.join(
                User.roles
            )

            count_statement = count_statement.join(
                User.roles
            )

            filters.append(
                func.lower(Role.name)
                == normalized_role
            )

        if is_active is not None:
            filters.append(
                User.is_active.is_(is_active)
            )

        if filters:
            user_statement = user_statement.where(
                *filters
            )

            count_statement = count_statement.where(
                *filters
            )

        total_items = int(
            database_session.scalar(
                count_statement
            )
            or 0
        )

        offset = (page - 1) * page_size

        user_statement = (
            user_statement.distinct()
            .order_by(
                User.created_at.desc(),
                User.id.desc(),
            )
            .offset(offset)
            .limit(page_size)
        )

        users = list(
            database_session.scalars(
                user_statement
            )
            .unique()
            .all()
        )

        return users, total_items

    @staticmethod
    def get_user_by_id(
        database_session: Session,
        user_id: int,
    ) -> User | None:
        """Return one user with roles loaded."""

        statement = (
            select(User)
            .options(selectinload(User.roles))
            .where(User.id == user_id)
        )

        return database_session.scalar(statement)

    @classmethod
    def update_user_status(
        cls,
        database_session: Session,
        *,
        user: User,
        is_active: bool,
    ) -> User:
        """Update one user status and return the refreshed user."""

        try:
            user.is_active = is_active

            database_session.commit()
        except Exception:
            database_session.rollback()
            raise

        refreshed_user = cls.get_user_by_id(
            database_session,
            user.id,
        )

        if refreshed_user is None:
            raise RuntimeError(
                "Updated user could not be reloaded."
            )

        return refreshed_user