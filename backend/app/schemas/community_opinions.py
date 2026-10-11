"""Contracts for community ratings and opinions from guide sites."""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.services.contact_redaction import redact_contact_numbers


CommunitySource = Literal["whatmobile"]

SOURCE_NAMES: dict[str, str] = {
    "whatmobile": "WhatMobile",
}


class CommunityOpinionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    position: int | None = Field(default=None, ge=1, le=10000)
    author: str | None = Field(default=None, max_length=120)
    posted_at: datetime | None = None
    text: str = Field(min_length=1, max_length=2000)
    contact_removed: bool = False

    @model_validator(mode="after")
    def remove_contact_numbers(self) -> "CommunityOpinionInput":
        """Strip any phone number the crawler let through."""

        text, removed = redact_contact_numbers(self.text)
        self.text = text
        self.contact_removed = self.contact_removed or removed

        return self


class CommunityOpinionsInput(BaseModel):
    """One phone's rating and opinions as a guide site published them."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source: CommunitySource
    product_name: str = Field(min_length=2, max_length=255)
    # The VEXTRO phone this page was looked up for, when the crawler knows.
    catalog_name: str | None = Field(default=None, max_length=255)
    brand: str | None = Field(default=None, max_length=120)
    source_url: str = Field(min_length=8, max_length=2000)
    opinions_url: str | None = Field(default=None, max_length=2000)
    rating: Decimal | None = Field(default=None, ge=0, le=5)
    rating_count: int = Field(default=0, ge=0)
    reference_price: Decimal | None = Field(default=None, gt=0)
    opinions: list[CommunityOpinionInput] = Field(default_factory=list)
    scraped_at: datetime | None = None

    @field_validator("opinions")
    @classmethod
    def bound_opinions(
        cls,
        value: list[CommunityOpinionInput],
    ) -> list[CommunityOpinionInput]:
        if len(value) > 200:
            raise ValueError("at most 200 opinions per phone are accepted")
        return value


class CommunityOpinionsIngestResponse(BaseModel):
    matched: bool
    canonical_product_id: int | None = None
    product_name: str | None = None
    created_count: int = 0
    duplicate_count: int = 0
    reason: str | None = None


class CommunityOpinionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    author_display_name: str | None
    posted_at: datetime | None
    opinion_text: str
    contact_removed: bool
    suspicion_score: int | None
    suspicion_level: str | None
    opinion_kind: str | None
    analysis_reasons: list[str] = Field(default_factory=list)


class CommunitySourceResponse(BaseModel):
    """Everything one guide site says about a phone."""

    source: str
    source_name: str
    source_url: str
    opinions_url: str | None
    rating: Decimal | None
    rating_count: int
    reference_price: Decimal | None
    last_seen_at: datetime
    opinion_count: int
    # How the posts divide: views of the phone, buy-and-sell adverts, and
    # questions. Unscored posts are in none of the three.
    genuine_opinion_count: int = 0
    advert_count: int = 0
    question_count: int = 0
    # Posts withheld from readers because they insult a person.
    hidden_count: int = 0
    opinions: list[CommunityOpinionResponse] = Field(default_factory=list)


class ProductCommunityOpinionsResponse(BaseModel):
    product_id: int
    sources: list[CommunitySourceResponse] = Field(default_factory=list)
