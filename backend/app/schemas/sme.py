"""Pydantic schemas for SME business intelligence."""

from datetime import datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


class SMEInputModel(BaseModel):
    """Shared validation rules for SME request schemas."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class OrganizationCreate(SMEInputModel):
    """Request for creating an SME organization."""

    name: str = Field(
        min_length=2,
        max_length=180,
    )

    industry: str | None = Field(
        default=None,
        max_length=120,
    )


class OrganizationUpdate(SMEInputModel):
    """Request for updating an SME organization."""

    name: str | None = Field(
        default=None,
        min_length=2,
        max_length=180,
    )

    industry: str | None = Field(
        default=None,
        max_length=120,
    )

    @model_validator(mode="after")
    def require_update_field(
        self,
    ) -> "OrganizationUpdate":
        """Require at least one valid update field."""

        if not self.model_fields_set:
            raise ValueError(
                "At least one organization field "
                "must be provided."
            )

        if (
            "name" in self.model_fields_set
            and self.name is None
        ):
            raise ValueError(
                "Organization name cannot be null."
            )

        return self


class OrganizationResponse(BaseModel):
    """Organization information returned by the API."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int

    owner_user_id: int

    name: str

    slug: str

    industry: str | None

    is_active: bool

    created_at: datetime

    updated_at: datetime


class OrganizationListResponse(BaseModel):
    """Organizations available to the authenticated SME."""

    total: int = Field(
        ge=0,
    )

    items: list[OrganizationResponse] = Field(
        default_factory=list,
    )


class BusinessProductCreate(SMEInputModel):
    """Request for creating an organization's product."""

    canonical_product_id: int | None = Field(
        default=None,
        ge=1,
    )

    name: str = Field(
        min_length=1,
        max_length=255,
    )

    sku: str | None = Field(
        default=None,
        max_length=120,
    )

    cost_price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    selling_price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    currency: str = Field(
        default="PKR",
        min_length=3,
        max_length=3,
    )

    stock_level: int = Field(
        default=0,
        ge=0,
    )

    reorder_level: int = Field(
        default=0,
        ge=0,
    )

    @field_validator("currency")
    @classmethod
    def normalize_currency(
        cls,
        value: str,
    ) -> str:
        """Store currency as a three-letter uppercase code."""

        normalized_value = value.upper()

        if not normalized_value.isalpha():
            raise ValueError(
                "Currency must contain exactly "
                "three letters."
            )

        return normalized_value


class BusinessProductUpdate(SMEInputModel):
    """Request for updating an organization's product."""

    canonical_product_id: int | None = Field(
        default=None,
        ge=1,
    )

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    sku: str | None = Field(
        default=None,
        max_length=120,
    )

    cost_price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    selling_price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    currency: str | None = Field(
        default=None,
        min_length=3,
        max_length=3,
    )

    stock_level: int | None = Field(
        default=None,
        ge=0,
    )

    reorder_level: int | None = Field(
        default=None,
        ge=0,
    )

    is_active: bool | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(
        cls,
        value: str | None,
    ) -> str | None:
        """Normalize an optional currency code."""

        if value is None:
            return None

        normalized_value = value.upper()

        if not normalized_value.isalpha():
            raise ValueError(
                "Currency must contain exactly "
                "three letters."
            )

        return normalized_value

    @model_validator(mode="after")
    def require_update_field(
        self,
    ) -> "BusinessProductUpdate":
        """Require at least one product field to update."""

        supplied_fields = self.model_fields_set

        if not supplied_fields:
            raise ValueError(
                "At least one business product field "
                "must be provided."
            )

        return self


class BusinessProductResponse(BaseModel):
    """Business product returned by the API."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int

    organization_id: int

    canonical_product_id: int | None

    name: str

    sku: str | None

    cost_price: Decimal | None

    selling_price: Decimal | None

    currency: str

    stock_level: int

    reorder_level: int

    is_active: bool

    created_at: datetime

    updated_at: datetime


class BusinessProductListResponse(BaseModel):
    """Paginated products belonging to one organization."""

    total: int = Field(
        ge=0,
    )

    page: int = Field(
        ge=1,
    )

    page_size: int = Field(
        ge=1,
        le=100,
    )

    total_pages: int = Field(
        ge=0,
    )

    items: list[BusinessProductResponse] = Field(
        default_factory=list,
    )


class CompetitorWatchlistCreate(SMEInputModel):
    """Request for monitoring a marketplace competitor listing."""

    business_product_id: int = Field(
        ge=1,
    )

    listing_id: int = Field(
        ge=1,
    )

    risk_threshold_percentage: Decimal = Field(
        default=Decimal("5.00"),
        gt=0,
        le=100,
    )


class CompetitorWatchlistStatusUpdate(
    SMEInputModel,
):
    """Request for activating or deactivating monitoring."""

    is_active: bool


class CompetitorWatchlistResponse(BaseModel):
    """Competitor watchlist entry returned by the API."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int

    organization_id: int

    business_product_id: int

    listing_id: int

    is_active: bool

    risk_threshold_percentage: Decimal

    last_risk_level: str | None

    last_alerted_at: datetime | None

    created_at: datetime

    updated_at: datetime


class CompetitorWatchlistListResponse(
    BaseModel,
):
    """Competitor entries belonging to an organization."""

    total: int = Field(
        ge=0,
    )

    items: list[
        CompetitorWatchlistResponse
    ] = Field(
        default_factory=list,
    )


class CompetitorTimelinePoint(BaseModel):
    """One historical competitor-price observation."""

    price: Decimal
    is_available: bool
    captured_at: datetime


class CompetitorInsightResponse(BaseModel):
    """Actionable pricing insight for one monitored listing."""

    watchlist_id: int
    business_product_id: int
    listing_id: int
    own_product_name: str
    own_price: Decimal | None
    competitor_price: Decimal
    currency: str
    platform_name: str
    seller_name: str | None
    price_gap: Decimal | None
    price_gap_percentage: Decimal | None
    price_position: str
    risk_level: str
    risk_reasons: list[str] = Field(default_factory=list)
    estimated_own_market_share_percentage: Decimal | None
    timeline: list[CompetitorTimelinePoint] = Field(
        default_factory=list,
    )


class CompetitorIntelligenceSummary(BaseModel):
    """Headline SME competitor-monitoring metrics."""

    tracked_competitors: int = Field(ge=0)
    tracked_products: int = Field(ge=0)
    average_price_gap: Decimal | None
    products_at_risk: int = Field(ge=0)
    estimated_average_market_share_percentage: Decimal | None
    risk_threshold_percentage: Decimal
    estimation_note: str


class CompetitorIntelligenceResponse(BaseModel):
    """Complete competitor dashboard response."""

    organization_id: int
    generated_at: datetime
    summary: CompetitorIntelligenceSummary
    items: list[CompetitorInsightResponse] = Field(
        default_factory=list,
    )
