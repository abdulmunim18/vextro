from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    Path,
    Query,
)
from sqlalchemy.orm import Session

from app.api.dependencies.roles import admin_only
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin import (
    AdminDashboardResponse,
    AdminUserListResponse,
    AdminUserResponse,
    AdminUserStatusUpdate,
)
from app.services.admin_service import AdminService


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["admin"],
)


@router.get(
    "/dashboard",
    response_model=AdminDashboardResponse,
    summary="Read Admin Dashboard",
    description=(
        "Return operational statistics available "
        "to authenticated VEXTRO administrators."
    ),
)
def read_admin_dashboard(
    database_session: Session = Depends(get_db),
    current_admin: User = Depends(admin_only),
) -> AdminDashboardResponse:
    del current_admin

    return AdminService.get_dashboard(
        database_session,
    )


@router.get(
    "/users",
    response_model=AdminUserListResponse,
    summary="List Admin Users",
    description=(
        "Search and filter registered VEXTRO "
        "users. Admin access is required."
    ),
)
def read_admin_users(
    q: str | None = Query(
        default=None,
        min_length=1,
        max_length=120,
        description=(
            "Search by full name or email address."
        ),
    ),
    role: Literal[
        "consumer",
        "sme",
        "admin",
    ]
    | None = Query(
        default=None,
        description="Filter users by role.",
    ),
    is_active: bool | None = Query(
        default=None,
        description=(
            "Filter active or inactive users."
        ),
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Results page number.",
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Users returned per page.",
    ),
    database_session: Session = Depends(get_db),
    current_admin: User = Depends(admin_only),
) -> AdminUserListResponse:
    del current_admin

    return AdminService.list_users(
        database_session,
        query=q,
        role=role,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.patch(
    "/users/{user_id}/status",
    response_model=AdminUserResponse,
    summary="Update Admin User Status",
    description=(
        "Activate or deactivate one registered "
        "VEXTRO user."
    ),
)
def update_admin_user_status(
    payload: AdminUserStatusUpdate,
    user_id: int = Path(
        ge=1,
        description="User ID.",
    ),
    database_session: Session = Depends(get_db),
    current_admin: User = Depends(admin_only),
) -> AdminUserResponse:
    return AdminService.update_user_status(
        database_session,
        current_admin=current_admin,
        user_id=user_id,
        payload=payload,
    )