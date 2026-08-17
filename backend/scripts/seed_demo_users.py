"""Create or refresh local-only browser testing accounts.

Usage from backend directory:
    $env:VEXTRO_DEMO_PASSWORD = "choose-a-local-demo-password"
    python scripts/seed_demo_users.py
"""

import os
import sys
from pathlib import Path

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.organization import Organization
from app.models.organization_user import OrganizationUser
from app.models.role import Role
from app.models.user import User


DEMO_USERS = (
    ("VEXTRO Demo Consumer", "demo.consumer@vextro.com", "consumer"),
    ("VEXTRO Demo SME", "demo.sme@vextro.com", "sme"),
    ("VEXTRO Demo Admin", "demo.admin@vextro.com", "admin"),
)

LEGACY_EMAILS = {
    "demo.consumer@vextro.com": "demo.consumer@vextro.local",
    "demo.sme@vextro.com": "demo.sme@vextro.local",
    "demo.admin@vextro.com": "demo.admin@vextro.local",
}


def seed_demo_users() -> None:
    """Upsert dedicated local demo users without changing real accounts."""

    password = os.getenv("VEXTRO_DEMO_PASSWORD", "")

    if len(password) < 8:
        raise RuntimeError(
            "Set VEXTRO_DEMO_PASSWORD to a password of at least 8 characters."
        )

    with SessionLocal() as database_session:
        roles = {
            role.name: role
            for role in database_session.scalars(select(Role)).all()
        }
        missing_roles = {
            role_name
            for _name, _email, role_name in DEMO_USERS
            if role_name not in roles
        }

        if missing_roles:
            raise RuntimeError(
                "Required roles are missing: " + ", ".join(sorted(missing_roles))
            )

        demo_users: dict[str, User] = {}

        for full_name, email, role_name in DEMO_USERS:
            user = database_session.scalar(
                select(User).where(
                    User.email.in_([email, LEGACY_EMAILS[email]])
                )
            )

            if user is None:
                user = User(full_name=full_name, email=email)
                database_session.add(user)

            user.full_name = full_name
            user.email = email
            user.password_hash = hash_password(password)
            user.is_active = True
            user.is_verified = True
            user.roles.clear()
            user.roles.append(roles[role_name])
            database_session.flush()
            demo_users[role_name] = user

        sme_user = demo_users["sme"]
        organization = database_session.scalar(
            select(Organization).where(
                Organization.slug == "vextro-demo-store"
            )
        )

        if organization is None:
            organization = Organization(
                owner_user_id=sme_user.id,
                name="VEXTRO Demo Store",
                slug="vextro-demo-store",
                industry="Consumer Electronics",
                is_active=True,
            )
            database_session.add(organization)
            database_session.flush()
        else:
            organization.owner_user_id = sme_user.id
            organization.is_active = True

        membership = database_session.scalar(
            select(OrganizationUser).where(
                OrganizationUser.organization_id == organization.id,
                OrganizationUser.user_id == sme_user.id,
            )
        )

        if membership is None:
            membership = OrganizationUser(
                organization_id=organization.id,
                user_id=sme_user.id,
            )
            database_session.add(membership)

        membership.membership_role = "owner"
        membership.is_active = True
        database_session.commit()

    print("Local VEXTRO demo users are ready:")
    for full_name, email, role_name in DEMO_USERS:
        print(f"- {role_name}: {email} ({full_name})")


if __name__ == "__main__":
    seed_demo_users()
