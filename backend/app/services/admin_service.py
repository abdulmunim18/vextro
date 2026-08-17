from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.admin_repository import (
    AdminRepository,
)
from app.schemas.admin import (
    AdminDashboardResponse,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserStatusUpdate,
)


class AdminService:
    """Administration-related business operations."""

    @staticmethod
    def _serialize_user(
        user: User,
    ) -> AdminUserResponse:
        role_names = sorted(
            role.name.strip().lower()
            for role in user.roles
        )

        return AdminUserResponse(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            roles=role_names,
            is_active=user.is_active,
            is_verified=user.is_verified,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

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

    @classmethod
    def list_users(
        cls,
        database_session: Session,
        *,
        query: str | None,
        role: str | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> AdminUserListResponse:
        users, total_items = (
            AdminRepository.list_users(
                database_session,
                query=query,
                role=role,
                is_active=is_active,
                page=page,
                page_size=page_size,
            )
        )

        total_pages = (
            (total_items + page_size - 1)
            // page_size
            if total_items > 0
            else 0
        )

        return AdminUserListResponse(
            items=[
                cls._serialize_user(user)
                for user in users
            ],
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        )

    @classmethod
    def update_user_status(
        cls,
        database_session: Session,
        *,
        current_admin: User,
        user_id: int,
        payload: AdminUserStatusUpdate,
    ) -> AdminUserResponse:
        target_user = (
            AdminRepository.get_user_by_id(
                database_session,
                user_id,
            )
        )

        if target_user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "USER_NOT_FOUND",
                    "message": (
                        "The requested user does not exist."
                    ),
                },
            )

        if (
            target_user.id == current_admin.id
            and payload.is_active is False
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": (
                        "CANNOT_DEACTIVATE_SELF"
                    ),
                    "message": (
                        "An administrator cannot "
                        "deactivate their own account."
                    ),
                },
            )

        if (
            target_user.is_active
            == payload.is_active
        ):
            return cls._serialize_user(
                target_user
            )

        updated_user = (
            AdminRepository.update_user_status(
                database_session,
                user=target_user,
                is_active=payload.is_active,
            )
        )

        return cls._serialize_user(
            updated_user
        )