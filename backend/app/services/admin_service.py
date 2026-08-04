from sqlalchemy.orm import Session

from app.repositories.admin_repository import (
    AdminRepository,
)
from app.schemas.admin import AdminDashboardResponse


class AdminService:
    """Administration-related business operations."""

    @staticmethod
    def get_dashboard(
        database_session: Session,
    ) -> AdminDashboardResponse:
        statistics = (
            AdminRepository.get_dashboard_statistics(
                database_session,
            )
        )

        return AdminDashboardResponse(
            **statistics,
        )