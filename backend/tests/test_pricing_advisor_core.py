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


def test_pricing_advisor_uses_user_selected_scenario_range() -> None:
    result = calculate_pricing_scenarios(
        current_price=Decimal("1000"),
        cost_price=Decimal("600"),
        competitor_price=Decimal("950"),
        baseline_units=Decimal("100"),
        demand_sensitivity=Decimal("1"),
        scenario_range_percentage=Decimal("12.5"),
    )

    assert [
        scenario.price_change_percentage
        for scenario in result.scenarios
    ] == [Decimal("-12.5"), Decimal("0"), Decimal("12.5")]
    assert result.scenarios[0].proposed_price == Decimal("875.00")
    assert result.scenarios[2].proposed_price == Decimal("1125.00")


def test_pricing_advisor_does_not_recommend_a_high_risk_scenario() -> None:
    """An unsafe profit winner must not be presented as a recommendation."""

    result = calculate_pricing_scenarios(
        current_price=Decimal("74999"),
        cost_price=Decimal("69500"),
        competitor_price=Decimal("119999"),
        baseline_units=Decimal("10"),
        demand_sensitivity=Decimal("1"),
        scenario_range_percentage=Decimal("2"),
    )

    assert all(
        scenario.risk_level == "high"
        for scenario in result.scenarios
    )
    assert result.recommended_change_percentage is None
    assert "No safe scenario" in result.recommendation
    assert "PKR 77,222.22" in result.recommendation


def test_pricing_advisor_returns_whole_expected_units() -> None:
    """Physical-product demand and dependent totals use whole units."""

    result = calculate_pricing_scenarios(
        current_price=Decimal("1000"),
        cost_price=Decimal("600"),
        competitor_price=Decimal("1100"),
        baseline_units=Decimal("11"),
        demand_sensitivity=Decimal("1"),
        scenario_range_percentage=Decimal("5"),
    )

    assert [
        scenario.expected_units
        for scenario in result.scenarios
    ] == [Decimal("12"), Decimal("11"), Decimal("10")]

    increased_price = result.scenarios[2]
    assert increased_price.expected_revenue == Decimal("10500.00")
    assert increased_price.gross_profit == Decimal("4500.00")
