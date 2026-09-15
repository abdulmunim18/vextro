"""Contracts for authenticated scraper run monitoring."""

from datetime import datetime
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


PlatformCode = Literal["daraz", "priceoye"]
TriggerType = Literal["manual", "scheduler", "test"]
RunStatus = Literal["running", "completed", "partial", "failed"]
ErrorStage = Literal[
    "fetch",
    "parse",
    "validation",
    "matching",
    "delivery",
    "ingestion",
]
ErrorOutcome = Literal["rejected", "failed"]


class ScrapeRunStartInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    platform: PlatformCode
    spider_name: str = Field(min_length=1, max_length=100)
    trigger_type: TriggerType = "manual"
    parser_version: str = Field(min_length=1, max_length=50)


class ScrapeRunFinishInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crawl_succeeded: bool
    items_discovered: int = Field(ge=0)
    items_ingested: int = Field(ge=0)
    items_rejected: int = Field(ge=0)
    items_failed: int = Field(ge=0)
    error_count: int = Field(ge=0)


class ScrapeErrorInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    outcome: ErrorOutcome
    item_discovered: bool = True
    external_listing_id: str | None = Field(default=None, max_length=150)
    product_url: str | None = Field(default=None, max_length=2000)
    error_type: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    error_stage: ErrorStage
    message: str = Field(min_length=1, max_length=500)
    raw_value: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata")
    @classmethod
    def bound_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Keep monitoring metadata deliberately small."""

        if len(value) > 20:
            raise ValueError("metadata must contain at most 20 fields")
        try:
            serialized = json.dumps(value, default=str)
        except (TypeError, ValueError) as exc:
            raise ValueError("metadata must be JSON serializable") from exc
        if len(serialized) > 4000:
            raise ValueError("metadata must not exceed 4000 characters")
        return value


class ScrapeErrorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    scrape_run_id: int
    external_listing_id: str | None
    product_url: str | None
    error_type: str
    error_stage: ErrorStage
    message: str
    raw_value: str | None
    error_metadata: dict[str, Any]
    created_at: datetime


class ScrapeRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: PlatformCode
    spider_name: str
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    items_discovered: int
    items_ingested: int
    items_rejected: int
    items_failed: int
    error_count: int
    trigger_type: TriggerType
    parser_version: str
    created_at: datetime
    updated_at: datetime


class ScrapeRunDetailResponse(ScrapeRunResponse):
    errors: list[ScrapeErrorResponse] = Field(default_factory=list)
