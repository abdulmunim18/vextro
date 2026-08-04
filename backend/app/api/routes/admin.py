from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies.roles import admin_only
from app.core.database import get_db
from app.models.user import User
from app.schemas.admin import AdminDashboardResponse
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