from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


class NotificationResponse(BaseModel):
    """One in-app notification belonging to the authenticated user."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    user_id: int

    price_alert_id: int | None
    canonical_product_id: int | None

    notification_type: str

    title: str
    message: str
    action_path: str | None

    is_read: bool
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    """Paginated notifications for the authenticated user."""

    total: int = Field(
        ge=0,
    )

    unread_count: int = Field(
        ge=0,
    )

    limit: int = Field(
        ge=1,
    )

    offset: int = Field(
        ge=0,
    )

    items: list[NotificationResponse] = Field(
        default_factory=list,
    )


class NotificationUnreadCountResponse(BaseModel):
    """Unread notification count for the authenticated user."""

    unread_count: int = Field(
        ge=0,
    )


class NotificationMarkAllReadResponse(BaseModel):
    """Result of marking all user notifications as read."""

    updated_count: int = Field(
        ge=0,
    )

    unread_count: int = Field(
        ge=0,
    )


class NotificationPreferenceResponse(BaseModel):
    """Delivery channel choices for the authenticated user."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    price_alert_in_app: bool = Field(
        default=True,
        description=(
            "In-app price alerts are always delivered and cannot be "
            "disabled."
        ),
    )

    price_alert_email: bool
    price_alert_push: bool

    competitor_alert_in_app: bool = Field(
        default=True,
        description=(
            "In-app competitor alerts are always delivered and cannot "
            "be disabled."
        ),
    )

    competitor_alert_email: bool
    competitor_alert_push: bool

    digest_frequency: Literal["off", "daily", "weekly"]

    digest_timezone: str = Field(
        description="Timezone used to schedule digest delivery.",
    )

    is_email_configured: bool = Field(
        description="Whether the server can currently send email.",
    )

    is_push_configured: bool = Field(
        description="Whether the server has VAPID keys configured.",
    )

    active_push_subscription_count: int = Field(
        ge=0,
    )

    vapid_public_key: str | None = Field(
        default=None,
        description=(
            "Public VAPID application server key for browser "
            "subscription. The private key is never exposed."
        ),
    )


class NotificationPreferenceUpdate(BaseModel):
    """Requested preference changes; omitted fields stay unchanged."""

    model_config = ConfigDict(
        extra="forbid",
    )

    price_alert_email: bool | None = None
    price_alert_push: bool | None = None
    competitor_alert_email: bool | None = None
    competitor_alert_push: bool | None = None
    digest_frequency: Literal["off", "daily", "weekly"] | None = None


class PushSubscriptionKeys(BaseModel):
    """Encryption keys supplied by the browser PushSubscription."""

    model_config = ConfigDict(
        extra="ignore",
    )

    p256dh: str = Field(
        min_length=16,
        max_length=255,
    )

    auth: str = Field(
        min_length=8,
        max_length=255,
    )


class PushSubscriptionCreate(BaseModel):
    """A browser Web Push subscription registered by its owner."""

    model_config = ConfigDict(
        extra="ignore",
    )

    endpoint: str = Field(
        min_length=12,
        max_length=2000,
    )

    keys: PushSubscriptionKeys

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, value: str) -> str:
        """Accept only absolute HTTPS push endpoints.

        The endpoint is supplied by the browser and is later contacted by
        the server, so an arbitrary scheme or a relative value must never
        reach the Web Push client.
        """

        endpoint = value.strip()
        parsed_endpoint = urlparse(endpoint)

        if parsed_endpoint.scheme != "https":
            raise ValueError(
                "endpoint must be an absolute HTTPS URL"
            )

        if not parsed_endpoint.netloc:
            raise ValueError(
                "endpoint must include a host"
            )

        return endpoint


class PushSubscriptionResponse(BaseModel):
    """A stored push subscription owned by the authenticated user."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class PushUnsubscribeRequest(BaseModel):
    """Identify the browser subscription to disable."""

    model_config = ConfigDict(
        extra="ignore",
    )

    endpoint: str = Field(
        min_length=12,
        max_length=2000,
    )


class PushUnsubscribeResponse(BaseModel):
    """Result of disabling one browser subscription."""

    deactivated: bool
