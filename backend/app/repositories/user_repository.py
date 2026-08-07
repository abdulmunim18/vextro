from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.role import Role
from app.models.user import User

from sqlalchemy.orm import Session, selectinload

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
    password_hash: str,
    role: Role,
) -> User:
    """Create a user and assign the selected application role."""

    user = User(
        full_name=full_name,
        email=email,
        password_hash=password_hash,
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