from pydantic import BaseModel, Field


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