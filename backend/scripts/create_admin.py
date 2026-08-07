from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.core.security import (
    hash_password,
    validate_password_strength,
)
from app.repositories.user_repository import (
    create_user,
    get_role_by_name,
    get_user_by_email,
)


email_validator = TypeAdapter(EmailStr)


def read_full_name() -> str:
    """Read and validate the administrator's name."""

    full_name = " ".join(
        input("Admin full name: ").strip().split()
    )

    if len(full_name) < 2:
        raise ValueError(
            "Full name must contain at least 2 characters."
        )

    if len(full_name) > 120:
        raise ValueError(
            "Full name cannot exceed 120 characters."
        )

    return full_name


def read_email() -> str:
    """Read and validate the administrator's email."""

    raw_email = input("Admin email: ").strip().lower()

    try:
        validated_email = email_validator.validate_python(
            raw_email
        )
    except ValidationError as error:
        raise ValueError(
            "A valid email address is required."
        ) from error

    return str(validated_email).lower()


def read_password() -> str:
    """Read and confirm a secure password."""

    password = getpass("Admin password: ")
    validate_password_strength(password)

    confirmation = getpass("Confirm password: ")

    if password != confirmation:
        raise ValueError(
            "Password confirmation does not match."
        )

    return password


def create_initial_admin() -> None:
    """Create an administrator without public registration."""

    try:
        full_name = read_full_name()
        email = read_email()
        password = read_password()
    except ValueError as error:
        raise SystemExit(f"Admin creation failed: {error}") from error

    with SessionLocal() as database_session:
        existing_user = get_user_by_email(
            database_session,
            email,
        )

        if existing_user is not None:
            raise SystemExit(
                "Admin creation failed: "
                "this email is already registered."
            )

        admin_role = get_role_by_name(
            database_session,
            "admin",
        )

        if admin_role is None:
            raise SystemExit(
                "Admin creation failed: "
                "the admin role does not exist."
            )

        try:
            admin_user = create_user(
                database_session,
                full_name=full_name,
                email=email,
                password_hash=hash_password(password),
                role=admin_role,
            )
        except IntegrityError as error:
            raise SystemExit(
                "Admin creation failed because of "
                "a database conflict."
            ) from error

    print()
    print("Administrator created successfully.")
    print(f"User ID: {admin_user.id}")
    print(f"Email: {admin_user.email}")
    print("Role: admin")


if __name__ == "__main__":
    create_initial_admin()