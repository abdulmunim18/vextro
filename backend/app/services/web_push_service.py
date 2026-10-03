"""Standards-based Web Push delivery using VAPID authentication.

VAPID keys come from configuration only. The private key is never logged
and never returned through the API; only the public key is exposed to the
frontend, which is safe by design.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, settings as default_settings


logger = logging.getLogger(__name__)


# Endpoints that return these statuses will never accept another message,
# so the stored subscription must be deactivated.
PERMANENT_FAILURE_STATUS_CODES = frozenset({404, 410})


class WebPushNotConfiguredError(Exception):
    """Raised when VAPID settings are incomplete for delivery."""


class WebPushDeliveryError(Exception):
    """Raised when one Web Push delivery attempt fails."""

    def __init__(
        self,
        message: str,
        *,
        is_permanent: bool = False,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)

        self.is_permanent = is_permanent
        self.status_code = status_code


@dataclass(frozen=True)
class WebPushSubscriptionInfo:
    """The browser-supplied data needed to encrypt one push message."""

    endpoint: str
    p256dh_key: str
    auth_key: str

    def as_subscription_info(self) -> dict[str, Any]:
        """Return the Push API subscription shape pywebpush expects."""

        return {
            "endpoint": self.endpoint,
            "keys": {
                "p256dh": self.p256dh_key,
                "auth": self.auth_key,
            },
        }


@dataclass(frozen=True)
class WebPushMessage:
    """A short browser notification payload."""

    title: str
    body: str
    action_path: str | None = None
    tag: str | None = None

    def as_json(self) -> str:
        """Serialize the payload handled by the service worker."""

        return json.dumps(
            {
                "title": self.title,
                "body": self.body,
                "action_path": self.action_path,
                "tag": self.tag,
            },
            separators=(",", ":"),
        )

    def as_payload(self) -> bytes:
        """Return the payload as bytes.

        The aes128gcm encryption layer concatenates raw bytes, so a str
        payload fails at encryption time. Encoding here keeps that
        requirement in one place.
        """

        return self.as_json().encode("utf-8")


def send_web_push(
    *,
    subscription: WebPushSubscriptionInfo,
    message: WebPushMessage,
    settings: Settings | None = None,
) -> None:
    """Deliver one encrypted Web Push message to a browser endpoint."""

    active_settings = settings or default_settings

    if not active_settings.is_web_push_configured:
        raise WebPushNotConfiguredError(
            "VAPID Web Push delivery is not configured."
        )

    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info=subscription.as_subscription_info(),
            data=message.as_payload(),
            vapid_private_key=active_settings.vapid_private_key,
            vapid_claims={
                "sub": active_settings.vapid_subject,
            },
            timeout=10,
            ttl=86400,
        )

    except WebPushException as error:
        # ``status_code`` is the library's common interface over both
        # sync and async responses. It is None for a failure raised
        # before the request, such as a malformed subscription key.
        status_code = getattr(error, "status_code", None)

        if status_code is None:
            status_code = getattr(
                getattr(error, "response", None),
                "status_code",
                None,
            )

        is_permanent = status_code in PERMANENT_FAILURE_STATUS_CODES

        raise WebPushDeliveryError(
            (
                "Web Push endpoint rejected the message"
                f" (status={status_code})"
            ),
            is_permanent=is_permanent,
            status_code=status_code,
        ) from error

    except Exception as error:  # noqa: BLE001 - transport level failure
        raise WebPushDeliveryError(
            f"Web Push delivery failed: {type(error).__name__}",
        ) from error
