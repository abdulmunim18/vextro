from fastapi import Depends, HTTPException, status

from app.api.dependencies.auth import get_current_user
from app.models.user import User


class RequireRoles:
    """Allow access only to users having an approved role."""

    def __init__(self, *allowed_roles: str) -> None:
        normalized_roles = {
            role.strip().lower()
            for role in allowed_roles
            if role.strip()
        }

        if not normalized_roles:
            raise ValueError(
                "At least one allowed role must be provided."
            )

        self.allowed_roles = frozenset(normalized_roles)

    def __call__(
        self,
        current_user: User = Depends(get_current_user),
    ) -> User:
        current_roles = {
            role.name.strip().lower()
            for role in current_user.roles
        }

        if current_roles.isdisjoint(self.allowed_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "ROLE_NOT_ALLOWED",
                    "message": (
                        "You do not have permission "
                        "to access this resource."
                    ),
                },
            )

        return current_user


consumer_or_admin = RequireRoles(
    "consumer",
    "admin",
)

sme_or_admin = RequireRoles(
    "sme",
    "admin",
)

admin_only = RequireRoles(
    "admin",
)