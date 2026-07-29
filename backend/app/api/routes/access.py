from fastapi import APIRouter, Depends

from app.api.dependencies.roles import (
    admin_only,
    consumer_or_admin,
    sme_or_admin,
)
from app.models.user import User


router = APIRouter(
    prefix="/api/v1/access",
    tags=["Access Control"],
)


def build_access_response(
    *,
    area: str,
    current_user: User,
) -> dict[str, object]:
    """Build a standard successful authorization response."""

    return {
        "status": "allowed",
        "area": area,
        "user_id": current_user.id,
        "email": current_user.email,
        "roles": sorted(
            role.name for role in current_user.roles
        ),
    }


@router.get("/consumer")
def check_consumer_access(
    current_user: User = Depends(consumer_or_admin),
) -> dict[str, object]:
    """Check access to Consumer resources."""

    return build_access_response(
        area="consumer",
        current_user=current_user,
    )


@router.get("/sme")
def check_sme_access(
    current_user: User = Depends(sme_or_admin),
) -> dict[str, object]:
    """Check access to SME resources."""

    return build_access_response(
        area="sme",
        current_user=current_user,
    )


@router.get("/admin")
def check_admin_access(
    current_user: User = Depends(admin_only),
) -> dict[str, object]:
    """Check access to Administrator resources."""

    return build_access_response(
        area="admin",
        current_user=current_user,
    )