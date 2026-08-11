from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


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