from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class AdminDashboardResponse(BaseModel):
    """Operational statistics visible to a VEXTRO administrator."""

    total_users: int = Field(ge=0)
    active_users: int = Field(ge=0)

    consumer_users: int = Field(ge=0)
    sme_users: int = Field(ge=0)
    admin_users: int = Field(ge=0)

    canonical_products: int = Field(ge=0)
    active_products: int = Field(ge=0)

    marketplace_listings: int = Field(ge=0)
    available_listings: int = Field(ge=0)

    total_price_alerts: int = Field(ge=0)
    active_price_alerts: int = Field(ge=0)
    triggered_price_alerts: int = Field(ge=0)


class AdminUserResponse(BaseModel):
    """Safe user information returned to an administrator."""

    id: int
    full_name: str
    email: EmailStr
    roles: list[str]

    is_active: bool
    is_verified: bool

    created_at: datetime
    updated_at: datetime


class AdminUserListResponse(BaseModel):
    """Paginated administrator user-list response."""

    items: list[AdminUserResponse]

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)

    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class AdminUserStatusUpdate(BaseModel):
    """Activate or deactivate one VEXTRO user."""

    is_active: bool