from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.database import get_db
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import (
    EmailVerificationRequest,
    ForgotPasswordRequest,
    MessageResponse,
    OAuthExchangeRequest,
    RefreshTokenRequest,
    RegistrationPendingResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
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
    InvalidOrExpiredAuthTokenError,
    OtpResendCooldownError,
    RegistrationRoleNotFoundError,
    TooManyOtpAttemptsError,
    UnverifiedAccountError,
    authenticate_user,
    issue_refresh_token,
    logout_user_session,
    refresh_user_session,
    request_password_reset,
    resend_registration_otp,
    reset_password,
    start_registration,
    verify_registration_otp,
)
from app.services.email_service import (
    EmailDeliveryError,
    EmailNotConfiguredError,
)
from app.services.oauth_service import (
    InvalidOAuthLoginCodeError,
    InvalidOAuthStateError,
    OAuthEmailUnavailableError,
    OAuthNotConfiguredError,
    OAuthProviderError,
    UnsupportedOAuthProviderError,
    build_oauth_authorization_url,
    complete_oauth_callback,
    exchange_oauth_login_code,
)
from app.core.config import settings


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
    response_model=RegistrationPendingResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def register_account(
    registration_data: UserRegister,
    database_session: Session = Depends(get_db),
) -> RegistrationPendingResponse:
    """Start signup and send a one-time email verification code."""

    try:
        email, expires_in = start_registration(
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
    except (EmailNotConfiguredError, EmailDeliveryError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "VERIFICATION_EMAIL_UNAVAILABLE",
                "message": "We could not send the verification email. Please try again later.",
            },
        ) from error

    return RegistrationPendingResponse(
        email=email,
        expires_in=expires_in,
        message="We sent a 6-digit verification code to your email.",
    )


@router.post(
    "/verify-email",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def verify_email(
    verification_data: EmailVerificationRequest,
    database_session: Session = Depends(get_db),
) -> UserResponse:
    """Complete signup by verifying the emailed OTP."""

    try:
        user = verify_registration_otp(
            database_session,
            email=str(verification_data.email),
            otp=verification_data.otp,
        )
    except InvalidOrExpiredAuthTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_OR_EXPIRED_OTP", "message": "The verification code is invalid or expired."},
        ) from error
    except TooManyOtpAttemptsError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "OTP_ATTEMPTS_EXHAUSTED", "message": "Too many incorrect attempts. Request a new code."},
        ) from error
    except EmailAlreadyRegisteredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "EMAIL_ALREADY_REGISTERED", "message": "An account with this email already exists."},
        ) from error
    except RegistrationRoleNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"code": "REGISTRATION_ROLE_NOT_FOUND", "message": "The selected account role is unavailable."},
        ) from error
    except OtpResendCooldownError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "OTP_RESEND_COOLDOWN",
                "message": "A verification code was just sent. Please wait before requesting another one.",
            },
        ) from error
    return build_user_response(user)


@router.post(
    "/resend-verification",
    response_model=RegistrationPendingResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def resend_verification(
    payload: ResendVerificationRequest,
    database_session: Session = Depends(get_db),
) -> RegistrationPendingResponse:
    try:
        email, expires_in = resend_registration_otp(
            database_session,
            email=str(payload.email),
        )
    except OtpResendCooldownError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "OTP_RESEND_COOLDOWN", "message": "Please wait before requesting another code."},
        ) from error
    except (InvalidOrExpiredAuthTokenError, EmailAlreadyRegisteredError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "NO_PENDING_REGISTRATION", "message": "No pending registration was found for this email."},
        ) from error
    except (EmailNotConfiguredError, EmailDeliveryError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "VERIFICATION_EMAIL_UNAVAILABLE", "message": "We could not send the verification email. Please try again later."},
        ) from error
    return RegistrationPendingResponse(
        email=email,
        expires_in=expires_in,
        message="A new verification code has been sent.",
    )


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
    except UnverifiedAccountError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "EMAIL_NOT_VERIFIED",
                "message": "Verify your email before logging in.",
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


@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def forgot_password(
    payload: ForgotPasswordRequest,
    database_session: Session = Depends(get_db),
) -> MessageResponse:
    """Email a reset link while preventing account enumeration."""

    request_password_reset(
        database_session,
        email=str(payload.email),
    )
    return MessageResponse(
        message="If an active account exists for that email, a password reset link has been sent."
    )


@router.post(
    "/reset-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
)
def apply_password_reset(
    payload: ResetPasswordRequest,
    database_session: Session = Depends(get_db),
) -> MessageResponse:
    try:
        reset_password(
            database_session,
            token=payload.token,
            new_password=payload.new_password,
        )
    except InvalidOrExpiredAuthTokenError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "INVALID_OR_EXPIRED_RESET_TOKEN", "message": "This password reset link is invalid or expired."},
        ) from error
    return MessageResponse(message="Your password has been changed successfully.")


@router.get("/oauth/{provider}/authorize", response_class=RedirectResponse)
def authorize_oauth(
    provider: str,
    account_type: str = Query(default="consumer", pattern="^(consumer|sme)$"),
    database_session: Session = Depends(get_db),
) -> RedirectResponse:
    try:
        authorization_url = build_oauth_authorization_url(
            database_session,
            provider=provider,
            account_type=account_type,
        )
    except UnsupportedOAuthProviderError as error:
        raise HTTPException(status_code=404, detail={"code": "OAUTH_PROVIDER_UNSUPPORTED", "message": "Unsupported login provider."}) from error
    except OAuthNotConfiguredError as error:
        raise HTTPException(status_code=503, detail={"code": "OAUTH_PROVIDER_NOT_CONFIGURED", "message": "This login provider is not configured yet."}) from error
    return RedirectResponse(authorization_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/oauth/{provider}/callback", response_class=RedirectResponse)
def oauth_callback(
    provider: str,
    state: str | None = None,
    code: str | None = None,
    error: str | None = None,
    database_session: Session = Depends(get_db),
) -> RedirectResponse:
    if error or not state or not code:
        return RedirectResponse(
            f"{settings.frontend_base_url_normalized}/login?oauth_error=invalid_request",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        login_code = complete_oauth_callback(
            database_session,
            provider=provider,
            state=state,
            code=code,
        )
    except OAuthEmailUnavailableError:
        error_code = "email_unavailable"
    except (InvalidOAuthStateError, UnsupportedOAuthProviderError):
        error_code = "invalid_request"
    except (OAuthProviderError, OAuthNotConfiguredError):
        error_code = "provider_error"
    else:
        return RedirectResponse(
            f"{settings.frontend_base_url_normalized}/oauth/callback?code={login_code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(
        f"{settings.frontend_base_url_normalized}/login?oauth_error={error_code}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/oauth/exchange",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
)
def exchange_oauth_code(
    payload: OAuthExchangeRequest,
    database_session: Session = Depends(get_db),
) -> TokenResponse:
    try:
        user = exchange_oauth_login_code(database_session, code=payload.code)
    except InvalidOAuthLoginCodeError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_OAUTH_LOGIN_CODE", "message": "This social login session is invalid or expired."},
        ) from error

    roles = sorted(role.name for role in user.roles)
    access_token, expires_in = create_access_token(user_id=user.id, roles=roles)
    refresh_token = issue_refresh_token(database_session, user_id=user.id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=expires_in,
        user=build_user_response(user),
    )
