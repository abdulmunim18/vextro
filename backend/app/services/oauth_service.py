from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import generate_opaque_token, hash_auth_token
from app.models.user import User
from app.repositories.auth_token_repository import (
    consume_auth_token,
    create_auth_token,
    get_active_auth_token_by_hash,
)
from app.repositories.user_repository import (
    create_user,
    get_oauth_account,
    get_role_by_name,
    get_user_by_email,
    get_user_by_id,
    link_oauth_account,
)


SUPPORTED_PROVIDERS = {"google", "facebook"}


class UnsupportedOAuthProviderError(Exception):
    pass


class OAuthNotConfiguredError(Exception):
    pass


class InvalidOAuthStateError(Exception):
    pass


class OAuthProviderError(Exception):
    pass


class OAuthEmailUnavailableError(Exception):
    pass


class InvalidOAuthLoginCodeError(Exception):
    pass


@dataclass(frozen=True)
class OAuthIdentity:
    provider: str
    subject: str
    email: str
    full_name: str


def _provider_credentials(provider: str) -> tuple[str, str]:
    if provider == "google":
        client_id = settings.google_oauth_client_id
        client_secret = settings.google_oauth_client_secret
    elif provider == "facebook":
        client_id = settings.facebook_oauth_client_id
        client_secret = settings.facebook_oauth_client_secret
    else:
        raise UnsupportedOAuthProviderError

    if not client_id or not client_secret:
        raise OAuthNotConfiguredError
    return client_id, client_secret


def oauth_callback_url(provider: str) -> str:
    return (
        f"{settings.api_public_base_url.rstrip('/')}"
        f"/api/v1/auth/oauth/{provider}/callback"
    )


def build_oauth_authorization_url(
    database_session: Session,
    *,
    provider: str,
    account_type: str,
) -> str:
    """Create a provider authorization URL backed by one-time state."""

    provider = provider.lower()
    client_id, _ = _provider_credentials(provider)
    if account_type not in {"consumer", "sme"}:
        account_type = "consumer"

    state = generate_opaque_token()
    create_auth_token(
        database_session,
        purpose="oauth_state",
        token_hash=hash_auth_token(state),
        expires_at=datetime.now(timezone.utc) + timedelta(
            minutes=settings.oauth_state_expire_minutes
        ),
        payload={
            "provider": provider,
            "account_type": account_type,
        },
    )

    if provider == "google":
        base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        query = {
            "client_id": client_id,
            "redirect_uri": oauth_callback_url(provider),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "prompt": "select_account",
        }
    else:
        base_url = "https://www.facebook.com/dialog/oauth"
        query = {
            "client_id": client_id,
            "redirect_uri": oauth_callback_url(provider),
            "response_type": "code",
            "scope": "email,public_profile",
            "state": state,
        }
    return f"{base_url}?{urlencode(query)}"


def _fetch_google_identity(code: str) -> OAuthIdentity:
    client_id, client_secret = _provider_credentials("google")
    with httpx.Client(timeout=15.0) as client:
        token_response = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": oauth_callback_url("google"),
                "grant_type": "authorization_code",
            },
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise OAuthProviderError

        profile_response = client.get(
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        profile_response.raise_for_status()
        profile = profile_response.json()

    if not profile.get("email") or profile.get("email_verified") is not True:
        raise OAuthEmailUnavailableError
    return OAuthIdentity(
        provider="google",
        subject=str(profile["sub"]),
        email=str(profile["email"]).strip().lower(),
        full_name=str(profile.get("name") or profile["email"].split("@")[0]),
    )


def _fetch_facebook_identity(code: str) -> OAuthIdentity:
    client_id, client_secret = _provider_credentials("facebook")
    with httpx.Client(timeout=15.0) as client:
        token_response = client.get(
            "https://graph.facebook.com/oauth/access_token",
            params={
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": oauth_callback_url("facebook"),
                "code": code,
            },
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise OAuthProviderError

        profile_response = client.get(
            "https://graph.facebook.com/me",
            params={
                "fields": "id,name,email",
                "access_token": access_token,
            },
        )
        profile_response.raise_for_status()
        profile = profile_response.json()

    if not profile.get("email"):
        raise OAuthEmailUnavailableError
    return OAuthIdentity(
        provider="facebook",
        subject=str(profile["id"]),
        email=str(profile["email"]).strip().lower(),
        full_name=str(profile.get("name") or profile["email"].split("@")[0]),
    )


def _resolve_oauth_user(
    database_session: Session,
    *,
    identity: OAuthIdentity,
    account_type: str,
) -> User:
    account = get_oauth_account(
        database_session,
        provider=identity.provider,
        provider_account_id=identity.subject,
    )
    if account is not None:
        user = get_user_by_id(database_session, account.user_id)
        if user is None:
            raise OAuthProviderError
        return user

    user = get_user_by_email(database_session, identity.email)
    if user is None:
        role = get_role_by_name(database_session, account_type)
        if role is None:
            raise OAuthProviderError
        user = create_user(
            database_session,
            full_name=identity.full_name,
            email=identity.email,
            password_hash=None,
            role=role,
            is_verified=True,
        )
    elif not user.is_verified:
        user.is_verified = True
        database_session.add(user)
        database_session.commit()

    try:
        link_oauth_account(
            database_session,
            user_id=user.id,
            provider=identity.provider,
            provider_account_id=identity.subject,
        )
    except IntegrityError as error:
        database_session.rollback()
        raise OAuthProviderError from error
    return get_user_by_id(database_session, user.id) or user


def complete_oauth_callback(
    database_session: Session,
    *,
    provider: str,
    state: str,
    code: str,
) -> str:
    """Validate state, resolve an identity, and issue a one-time login code."""

    provider = provider.lower()
    state_record = get_active_auth_token_by_hash(
        database_session,
        purpose="oauth_state",
        token_hash=hash_auth_token(state),
    )
    if (
        state_record is None
        or state_record.payload.get("provider") != provider
    ):
        raise InvalidOAuthStateError

    try:
        identity = (
            _fetch_google_identity(code)
            if provider == "google"
            else _fetch_facebook_identity(code)
            if provider == "facebook"
            else None
        )
    except (httpx.HTTPError, ValueError, KeyError) as error:
        raise OAuthProviderError from error
    if identity is None:
        raise UnsupportedOAuthProviderError

    user = _resolve_oauth_user(
        database_session,
        identity=identity,
        account_type=str(state_record.payload.get("account_type", "consumer")),
    )
    consume_auth_token(database_session, state_record)

    login_code = generate_opaque_token()
    create_auth_token(
        database_session,
        purpose="oauth_login",
        token_hash=hash_auth_token(login_code),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(
            minutes=settings.oauth_login_code_expire_minutes
        ),
    )
    return login_code


def exchange_oauth_login_code(
    database_session: Session,
    *,
    code: str,
) -> User:
    record = get_active_auth_token_by_hash(
        database_session,
        purpose="oauth_login",
        token_hash=hash_auth_token(code),
    )
    if record is None or record.user_id is None:
        raise InvalidOAuthLoginCodeError
    user = get_user_by_id(database_session, record.user_id)
    if user is None or not user.is_active:
        raise InvalidOAuthLoginCodeError
    consume_auth_token(database_session, record)
    return user
