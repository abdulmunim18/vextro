"""Pydantic schemas for SME sales CSV imports."""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


SalesImportStatus = Literal[
    "pending",
    "processing",
    "completed",
    "completed_with_errors",
    "failed",
]


class SalesCSVRowError(BaseModel):
    """Validation error produced for one rejected CSV row."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    row_number: int = Field(
        ge=2,
        description=(
            "Physical CSV row number including "
            "the header row."
        ),
    )

    field: str | None = Field(
        default=None,
        max_length=100,
    )

    message: str = Field(
        min_length=1,
        max_length=500,
    )

    value: str | None = Field(
        default=None,
        max_length=500,
    )


class SalesImportResponse(BaseModel):
    """One stored SME sales-import operation."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    organization_id: int
    uploaded_by_user_id: int
    original_filename: str
    status: SalesImportStatus

    total_rows: int = Field(
        ge=0,
    )

    accepted_rows: int = Field(
        ge=0,
    )

    rejected_rows: int = Field(
        ge=0,
    )

    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class SalesImportResultResponse(BaseModel):
    """Result returned immediately after processing a CSV file."""

    sales_import: SalesImportResponse

    required_columns: list[str] = Field(
        default_factory=lambda: [
            "sku",
            "sale_date",
            "quantity",
            "unit_price",
        ],
    )

    optional_columns: list[str] = Field(
        default_factory=lambda: [
            "currency",
        ],
    )

    row_errors: list[SalesCSVRowError] = Field(
        default_factory=list,
    )


class SalesImportListResponse(BaseModel):
    """Paginated sales imports belonging to an organization."""

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

    items: list[SalesImportResponse] = Field(
        default_factory=list,
    )


class SalesRecordResponse(BaseModel):
    """One accepted sales row stored in the database."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    sales_import_id: int
    business_product_id: int

    source_row_number: int = Field(
        ge=2,
    )

    sale_date: date

    quantity: int = Field(
        gt=0,
    )

    unit_price: Decimal = Field(
        ge=0,
        max_digits=14,
        decimal_places=2,
    )

    total_revenue: Decimal = Field(
        ge=0,
        max_digits=16,
        decimal_places=2,
    )

    currency: str = Field(
        min_length=3,
        max_length=3,
    )

    created_at: datetime


class SalesRecordListResponse(BaseModel):
    """Paginated sales records from one import operation."""

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

    items: list[SalesRecordResponse] = Field(
        default_factory=list,
    )
class SalesAnalyticsSummaryResponse(BaseModel):
    """Headline sales metrics for one SME organization."""

    total_revenue: Decimal = Field(
        ge=0,
        max_digits=18,
        decimal_places=2,
    )

    total_units_sold: int = Field(
        ge=0,
    )

    total_sales_records: int = Field(
        ge=0,
    )

    average_selling_price: Decimal = Field(
        ge=0,
        max_digits=18,
        decimal_places=2,
    )

    products_sold: int = Field(
        ge=0,
    )


class SalesRevenueTrendPointResponse(BaseModel):
    """Aggregated sales metrics for one calendar date."""

    sale_date: date

    revenue: Decimal = Field(
        ge=0,
        max_digits=18,
        decimal_places=2,
    )

    units_sold: int = Field(
        ge=0,
    )

    sales_records: int = Field(
        ge=0,
    )


class SalesProductPerformanceResponse(BaseModel):
    """Aggregated sales performance for one business product."""

    business_product_id: int = Field(
        ge=1,
    )

    product_name: str = Field(
        min_length=1,
        max_length=255,
    )

    sku: str | None = Field(
        default=None,
        max_length=120,
    )

    revenue: Decimal = Field(
        ge=0,
        max_digits=18,
        decimal_places=2,
    )

    units_sold: int = Field(
        ge=0,
    )

    sales_records: int = Field(
        ge=0,
    )

    average_selling_price: Decimal = Field(
        ge=0,
        max_digits=18,
        decimal_places=2,
    )


class SalesAnalyticsResponse(BaseModel):
    """Sales analytics for one SME organization."""

    organization_id: int = Field(
        ge=1,
    )

    currency: str = Field(
        min_length=3,
        max_length=3,
    )

    start_date: date | None = None
    end_date: date | None = None

    summary: SalesAnalyticsSummaryResponse

    revenue_trend: list[
        SalesRevenueTrendPointResponse
    ] = Field(
        default_factory=list,
    )

    product_performance: list[
        SalesProductPerformanceResponse
    ] = Field(
        default_factory=list,
    )