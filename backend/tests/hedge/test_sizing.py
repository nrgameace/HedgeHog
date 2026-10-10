from decimal import Decimal

import pytest

from app.hedge.sizing import Constraint, Exposure, MarketQuote, Side, size_position

UNLIMITED = Decimal("1e12")


def quote(**overrides) -> MarketQuote:
    defaults = {
        "ticker": "KXRAINKC-26OCT12",
        "yes_ask": Decimal("0.30"),
        "no_ask": Decimal("0.72"),
        "yes_ask_size": 1_000_000,
        "no_ask_size": 1_000_000,
    }
    return MarketQuote(**{**defaults, **overrides})


def exposure(**overrides) -> Exposure:
    defaults = {
        "baseline_revenue": Decimal("10000"),
        "revenue_impact_pct": Decimal("0.20"),
        "hurts_when": Side.YES,
    }
    return Exposure(**{**defaults, **overrides})


def test_unconstrained_hedge_buys_one_contract_per_dollar_of_shortfall():
    position = size_position(quote(), exposure(), budget=UNLIMITED)

    assert position.shortfall == Decimal("2000")
    assert position.contracts == 2000
    assert position.hedge_ratio == Decimal("1")
    assert position.binding_constraint is Constraint.FULL_HEDGE


@pytest.mark.parametrize("yes_ask", ["0.01", "0.30", "0.50", "0.99"])
def test_contract_count_is_independent_of_price(yes_ask):
    position = size_position(quote(yes_ask=Decimal(yes_ask)), exposure(), budget=UNLIMITED)

    assert position.contracts == 2000
    assert position.premium == 2000 * Decimal(yes_ask)


def test_buys_the_side_that_pays_when_the_business_is_hurt():
    hurt_by_yes = size_position(quote(), exposure(hurts_when=Side.YES), budget=UNLIMITED)
    hurt_by_no = size_position(quote(), exposure(hurts_when=Side.NO), budget=UNLIMITED)

    assert hurt_by_yes.side is Side.YES
    assert hurt_by_yes.entry_price == Decimal("0.30")
    assert hurt_by_no.side is Side.NO
    assert hurt_by_no.entry_price == Decimal("0.72")


def test_budget_caps_contracts_and_reports_partial_hedge():
    position = size_position(quote(), exposure(), budget=Decimal("100"))

    assert position.contracts == 333
    assert position.premium == Decimal("99.90")
    assert position.hedge_ratio == Decimal("0.1665")
    assert position.binding_constraint is Constraint.BUDGET


def test_resting_book_depth_caps_contracts():
    position = size_position(quote(yes_ask_size=500), exposure(), budget=UNLIMITED)

    assert position.contracts == 500
    assert position.binding_constraint is Constraint.LIQUIDITY


def test_depth_factor_takes_only_part_of_the_resting_book():
    position = size_position(
        quote(yes_ask_size=500), exposure(), budget=UNLIMITED, depth_factor=Decimal("0.5")
    )

    assert position.contracts == 250


def test_tightest_constraint_wins():
    position = size_position(quote(yes_ask_size=400), exposure(), budget=Decimal("60"))

    assert position.contracts == 200
    assert position.binding_constraint is Constraint.BUDGET


def test_fees_raise_unit_cost_and_reduce_affordable_contracts():
    position = size_position(
        quote(), exposure(), budget=Decimal("100"), fee_per_contract=Decimal("0.02")
    )

    assert position.contracts == 312
    assert position.premium == Decimal("99.84")


def test_zero_revenue_impact_opens_no_position():
    position = size_position(quote(), exposure(revenue_impact_pct=Decimal("0")), budget=UNLIMITED)

    assert position.contracts == 0
    assert position.premium == Decimal("0")
    assert position.hedge_ratio == Decimal("0")


def test_payoff_if_hit_covers_the_shortfall_on_a_full_hedge():
    position = size_position(quote(), exposure(), budget=UNLIMITED)

    assert position.payoff_if_hit == position.shortfall == Decimal("2000")


def test_notional_value_above_one_dollar_needs_fewer_contracts():
    position = size_position(
        quote(notional_value=Decimal("100"), yes_ask=Decimal("30")), exposure(), budget=UNLIMITED
    )

    assert position.contracts == 20
    assert position.payoff_if_hit == Decimal("2000")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("baseline_revenue", Decimal("-1")),
        ("revenue_impact_pct", Decimal("-0.1")),
        ("revenue_impact_pct", Decimal("1.5")),
    ],
)
def test_rejects_nonsensical_exposure(field, value):
    with pytest.raises(ValueError):
        size_position(quote(), exposure(**{field: value}), budget=UNLIMITED)


def test_rejects_negative_budget():
    with pytest.raises(ValueError):
        size_position(quote(), exposure(), budget=Decimal("-1"))


def test_rejects_market_with_no_resting_offer():
    """A yes_ask of 0 means nobody is offering - seen live on illiquid Kalshi markets."""
    with pytest.raises(ValueError):
        size_position(quote(yes_ask=Decimal("0")), exposure(), budget=UNLIMITED)


def test_rejects_ask_above_notional_value():
    with pytest.raises(ValueError):
        size_position(quote(yes_ask=Decimal("1.01")), exposure(), budget=UNLIMITED)
