"""Schemas for the SME dynamic pricing strategy advisor."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PricingScenarioInput(BaseModel):
    """Inputs used to simulate advisory price changes."""

    model_config = ConfigDict(
        extra="forbid",
    )

    business_product_id: int | None = Field(
        default=None,
        ge=1,
    )
    current_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=14,
        decimal_places=2,
    )
    cost_price: Decimal | None = Field(
        default=None,
        ge=0,
        max_digits=14,
        decimal_places=2,
    )
    competitor_price: Decimal | None = Field(
        default=None,
        gt=0,
        max_digits=14,
        decimal_places=2,
    )
    baseline_units: Decimal = Field(
        default=Decimal("100"),
        gt=0,
        le=1_000_000,
    )
    demand_sensitivity: Decimal = Field(
        default=Decimal("1.00"),
        ge=0,
        le=5,
        description=(
            "Estimated percentage demand response to a one-percent "
            "price change."
        ),
    )

    @model_validator(mode="after")
    def require_manual_or_product_prices(self) -> "PricingScenarioInput":
        """Require complete manual inputs when no business product is used."""

        if self.business_product_id is None:
            missing = [
                field_name
                for field_name in (
                    "current_price",
                    "cost_price",
                    "competitor_price",
                )
                if getattr(self, field_name) is None
            ]

            if missing:
                raise ValueError(
                    "Manual scenarios require current_price, cost_price "
                    "and competitor_price."
                )

        return self


class PricingScenarioResult(BaseModel):
    """One simulated pricing option."""

    price_change_percentage: Decimal
    proposed_price: Decimal
    expected_units: Decimal
    expected_revenue: Decimal
    gross_profit: Decimal
    gross_margin_percentage: Decimal
    competitor_gap: Decimal
    competitor_gap_percentage: Decimal
    risk_level: str
    risk_reasons: list[str] = Field(default_factory=list)


class PricingAdvisorResponse(BaseModel):
    """Complete advisory response for one SME pricing decision."""

    business_product_id: int | None = None
    product_name: str | None = None
    currency: str = "PKR"
    current_price: Decimal
    cost_price: Decimal
    competitor_price: Decimal
    baseline_units: Decimal
    demand_sensitivity: Decimal
    recommended_change_percentage: Decimal
    recommendation: str
    disclaimer: str
    scenarios: list[PricingScenarioResult]
