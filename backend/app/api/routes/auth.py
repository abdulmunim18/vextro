from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
)
from app.services.auth_service import (
    EmailAlreadyRegisteredError,
    ExpiredRefreshTokenError,
    InactiveAccountError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    RegistrationRoleNotFoundError,
    authenticate_user,
    issue_refresh_token,
    logout_user_session,
    refresh_user_session,
    register_user,
)


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["Authentication"],
)


def build_user_response(user: User) -> UserResponse:
    """Create a safe API response for a user."""

    return UserResponse(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        roles=sorted(
            role.name for role in user.roles
        ),
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_account(
    registration_data: UserRegister,
    database_session: Session = Depends(get_db),
) -> UserResponse:
    """Register a new Consumer or SME user."""

    try:
        user = register_user(
            database_session,
            registration_data,
        )
    except EmailAlreadyRegisteredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "EMAIL_ALREADY_REGISTERED",
                "message": (
                    "An account with this email already exists."
                ),
            },
        ) from error
    except RegistrationRoleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "REGISTRATION_ROLE_NOT_FOUND",
                "message": (
                    "The selected account role is unavailable."
                ),
            },
        ) from error

    return build_user_response(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def login_account(
    login_data: UserLogin,
    database_session: Session = Depends(get_db),
) -> TokenResponse:
    """Authenticate a user and issue access and refresh tokens."""

    try:
        user = authenticate_user(
            database_session,
            login_data,
        )
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Email or password is incorrect.",
            },
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from error
    except InactiveAccountError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ACCOUNT_INACTIVE",
                "message": (
                    "This account has been deactivated."
                ),
            },
        ) from error

    role_names = sorted(
        role.name for role in user.roles
    )

    access_token, expires_in = create_access_token(
        user_id=user.id,
        roles=role_names,
    )

    refresh_token = issue_refresh_token(
        database_session,
        user_id=user.id,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=build_user_response(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
def get_current_account(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Return the currently authenticated user."""

    return build_user_response(current_user)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def refresh_access_token(
    token_data: RefreshTokenRequest,
    database_session: Session = Depends(get_db),
) -> TokenResponse:
    """Rotate a refresh token and issue a new session."""

    try:
        user, new_refresh_token = refresh_user_session(
            database_session,
            raw_refresh_token=token_data.refresh_token,
        )
    except ExpiredRefreshTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "REFRESH_TOKEN_EXPIRED",
                "message": "The refresh token has expired.",
            },
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from error
    except InvalidRefreshTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_REFRESH_TOKEN",
                "message": (
                    "The refresh token is invalid or revoked."
                ),
            },
            headers={
                "WWW-Authenticate": "Bearer",
            },
        ) from error
    except InactiveAccountError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "ACCOUNT_INACTIVE",
                "message": (
                    "This account has been deactivated."
                ),
            },
        ) from error

    role_names = sorted(
        role.name for role in user.roles
    )

    access_token, expires_in = create_access_token(
        user_id=user.id,
        roles=role_names,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=build_user_response(user),
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def logout_account(
    token_data: RefreshTokenRequest,
    database_session: Session = Depends(get_db),
) -> Response:
    """Revoke the supplied refresh-token session."""

    logout_user_session(
        database_session,
        raw_refresh_token=token_data.refresh_token,
    )

    return Response(
        status_code=status.HTTP_204_NO_CONTENT
    )