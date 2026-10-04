from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.models.oauth_account import OAuthAccount
from app.models.role import Role
from app.models.user import User


def get_user_by_email(
    database_session: Session,
    email: str,
) -> User | None:
    """Return a user and assigned roles by email."""

    statement = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.email == email)
    )

    return database_session.scalar(statement)


def get_role_by_name(
    database_session: Session,
    role_name: str,
) -> Role | None:
    """Return an application role by name."""

    statement = select(Role).where(Role.name == role_name)

    return database_session.scalar(statement)


def create_user(
    database_session: Session,
    *,
    full_name: str,
    email: str,
    password_hash: str | None,
    role: Role,
    is_verified: bool = False,
) -> User:
    """Create a user and assign the selected application role."""

    user = User(
        full_name=full_name,
        email=email,
        password_hash=password_hash,
        is_verified=is_verified,
    )

    user.roles.append(role)
    database_session.add(user)

    try:
        database_session.commit()
    except IntegrityError:
        database_session.rollback()
        raise

    database_session.refresh(user)

    return user


def get_user_by_id(
    database_session: Session,
    user_id: int,
) -> User | None:
    """Return a user and assigned roles by user ID."""

    statement = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == user_id)
    )

    return database_session.scalar(statement)


def get_oauth_account(
    database_session: Session,
    *,
    provider: str,
    provider_account_id: str,
) -> OAuthAccount | None:
    """Return a provider identity mapping when it already exists."""

    return database_session.scalar(
        select(OAuthAccount).where(
            OAuthAccount.provider == provider,
            OAuthAccount.provider_account_id == provider_account_id,
        )
    )


def link_oauth_account(
    database_session: Session,
    *,
    user_id: int,
    provider: str,
    provider_account_id: str,
) -> OAuthAccount:
    """Link a verified external identity to an existing user."""

    account = OAuthAccount(
        user_id=user_id,
        provider=provider,
        provider_account_id=provider_account_id,
    )
    database_session.add(account)
    database_session.commit()
    database_session.refresh(account)
    return account
