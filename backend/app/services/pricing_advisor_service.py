"""Advisory-only dynamic pricing scenario calculations."""

from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.sme_repository import SMERepository
from app.schemas.pricing_advisor import (
    PricingAdvisorResponse,
    PricingScenarioInput,
    PricingScenarioResult,
)


MONEY = Decimal("0.01")
PERCENT = Decimal("0.01")
UNIT = Decimal("0.01")
SCENARIO_CHANGES = (
    Decimal("-5"),
    Decimal("0"),
    Decimal("5"),
)


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _percent(value: Decimal) -> Decimal:
    return value.quantize(PERCENT, rounding=ROUND_HALF_UP)


def _units(value: Decimal) -> Decimal:
    return max(Decimal("0"), value).quantize(
        UNIT,
        rounding=ROUND_HALF_UP,
    )


def calculate_pricing_scenarios(
    *,
    current_price: Decimal,
    cost_price: Decimal,
    competitor_price: Decimal,
    baseline_units: Decimal,
    demand_sensitivity: Decimal,
    business_product_id: int | None = None,
    product_name: str | None = None,
    currency: str = "PKR",
) -> PricingAdvisorResponse:
    """Return three transparent price scenarios and a recommendation."""

    if cost_price >= current_price * Decimal("3"):
        raise ValueError(
            "Cost price is implausibly high compared with the current price."
        )

    scenarios: list[PricingScenarioResult] = []

    for change in SCENARIO_CHANGES:
        proposed_price = _money(
            current_price
            * (Decimal("1") + change / Decimal("100"))
        )
        demand_multiplier = (
            Decimal("1")
            - (change / Decimal("100")) * demand_sensitivity
        )
        expected_units = _units(
            baseline_units * demand_multiplier
        )
        revenue = _money(proposed_price * expected_units)
        gross_profit = _money(
            (proposed_price - cost_price) * expected_units
        )
        margin = (
            _percent(
                (proposed_price - cost_price)
                / proposed_price
                * Decimal("100")
            )
            if proposed_price > 0
            else Decimal("0")
        )
        competitor_gap = _money(
            proposed_price - competitor_price
        )
        competitor_gap_percentage = _percent(
            competitor_gap
            / competitor_price
            * Decimal("100")
        )

        risk_reasons: list[str] = []

        if proposed_price <= cost_price:
            risk_reasons.append(
                "Proposed price does not preserve a positive unit margin."
            )

        if competitor_gap_percentage > Decimal("10"):
            risk_reasons.append(
                "Price is more than 10% above the monitored competitor."
            )

        if margin < Decimal("10"):
            risk_reasons.append(
                "Gross margin is below the 10% safety threshold."
            )

        if risk_reasons:
            risk_level = "high"
        elif (
            competitor_gap_percentage > Decimal("5")
            or margin < Decimal("20")
        ):
            risk_level = "medium"
            risk_reasons.append(
                "Scenario needs monitoring because its price or margin "
                "is close to a configured threshold."
            )
        else:
            risk_level = "low"

        scenarios.append(
            PricingScenarioResult(
                price_change_percentage=change,
                proposed_price=proposed_price,
                expected_units=expected_units,
                expected_revenue=revenue,
                gross_profit=gross_profit,
                gross_margin_percentage=margin,
                competitor_gap=competitor_gap,
                competitor_gap_percentage=competitor_gap_percentage,
                risk_level=risk_level,
                risk_reasons=risk_reasons,
            )
        )

    viable_scenarios = [
        scenario
        for scenario in scenarios
        if scenario.gross_profit >= 0
        and scenario.risk_level != "high"
    ]
    recommendation_pool = viable_scenarios or scenarios
    recommended = max(
        recommendation_pool,
        key=lambda scenario: scenario.gross_profit,
    )

    change_label = (
        "keep the current price"
        if recommended.price_change_percentage == 0
        else (
            f"change price by "
            f"{recommended.price_change_percentage}%"
        )
    )

    return PricingAdvisorResponse(
        business_product_id=business_product_id,
        product_name=product_name,
        currency=currency,
        current_price=_money(current_price),
        cost_price=_money(cost_price),
        competitor_price=_money(competitor_price),
        baseline_units=_units(baseline_units),
        demand_sensitivity=_percent(demand_sensitivity),
        recommended_change_percentage=(
            recommended.price_change_percentage
        ),
        recommendation=(
            f"Based on the supplied assumptions, {change_label}. "
            f"This scenario estimates gross profit of {currency} "
            f"{recommended.gross_profit}."
        ),
        disclaimer=(
            "Advisory simulation only. VEXTRO does not automatically "
            "change marketplace prices, and actual demand may differ."
        ),
        scenarios=scenarios,
    )


class PricingAdvisorService:
    """Resolve SME product data before running pricing simulations."""

    def __init__(self, repository: SMERepository | None = None) -> None:
        self.repository = repository or SMERepository()

    def simulate(
        self,
        database_session: Session,
        *,
        organization_id: int,
        user_id: int,
        payload: PricingScenarioInput,
    ) -> PricingAdvisorResponse:
        organization = self.repository.get_organization_for_user(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        if organization is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="The requested organization was not found.",
            )

        product_name: str | None = None
        currency = "PKR"
        current_price = payload.current_price
        cost_price = payload.cost_price
        competitor_price = payload.competitor_price

        if payload.business_product_id is not None:
            product = self.repository.get_business_product(
                database_session,
                organization_id=organization_id,
                product_id=payload.business_product_id,
            )

            if product is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="The requested business product was not found.",
                )

            product_name = product.name
            currency = product.currency
            current_price = current_price or product.selling_price
            cost_price = (
                cost_price
                if cost_price is not None
                else product.cost_price
            )
            competitor_price = (
                competitor_price
                or self.repository.get_lowest_competitor_price(
                    database_session,
                    organization_id=organization_id,
                    business_product_id=product.id,
                )
            )

        missing_labels = [
            label
            for label, value in (
                ("current selling price", current_price),
                ("cost price", cost_price),
                ("active competitor price", competitor_price),
            )
            if value is None
        ]

        if missing_labels:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Pricing simulation needs "
                    + ", ".join(missing_labels)
                    + "."
                ),
            )

        try:
            return calculate_pricing_scenarios(
                current_price=Decimal(current_price),
                cost_price=Decimal(cost_price),
                competitor_price=Decimal(competitor_price),
                baseline_units=payload.baseline_units,
                demand_sensitivity=payload.demand_sensitivity,
                business_product_id=payload.business_product_id,
                product_name=product_name,
                currency=currency,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(error),
            ) from error
