"""Unit tests for the dynamic pricing advisor calculations."""

from decimal import Decimal

from app.services.pricing_advisor_service import (
    calculate_pricing_scenarios,
)


def test_pricing_advisor_returns_three_transparent_scenarios() -> None:
    result = calculate_pricing_scenarios(
        current_price=Decimal("120000"),
        cost_price=Decimal("100000"),
        competitor_price=Decimal("118000"),
        baseline_units=Decimal("100"),
        demand_sensitivity=Decimal("1"),
        product_name="Test Phone",
    )

    assert [
        scenario.price_change_percentage
        for scenario in result.scenarios
    ] == [
        Decimal("-5"),
        Decimal("0"),
        Decimal("5"),
    ]
    assert all(
        scenario.expected_revenue > 0
        for scenario in result.scenarios
    )
    assert result.disclaimer.startswith("Advisory simulation")


def test_pricing_advisor_flags_below_cost_scenario() -> None:
    result = calculate_pricing_scenarios(
        current_price=Decimal("100"),
        cost_price=Decimal("98"),
        competitor_price=Decimal("95"),
        baseline_units=Decimal("10"),
        demand_sensitivity=Decimal("1"),
    )

    discounted = result.scenarios[0]

    assert discounted.risk_level == "high"
    assert discounted.gross_profit < 0
