from datetime import date
from decimal import Decimal

import pytest

from app.hedge.sizing import (
    Constraint,
    ContractWindow,
    Exposure,
    MarketQuote,
    Side,
    revenue_at_risk,
    size_position,
)

UNLIMITED = Decimal("1e12")

ONE_DAY = ContractWindow(opens=date(2026, 10, 12), settles=date(2026, 10, 12))
ONE_WEEK = ContractWindow(opens=date(2026, 10, 5), settles=date(2026, 10, 11))
THIRTY_DAYS = ContractWindow(opens=date(2026, 10, 1), settles=date(2026, 10, 30))

# Early enough that none of the windows above has begun elapsing, so these tests
# isolate sizing from the partial-window clipping exercised in TestRemainingExposure.
AS_OF = date(2026, 10, 1)


def quote(**overrides) -> MarketQuote:
    defaults = {
        "ticker": "KXRAINKC-26OCT12",
        "yes_ask": Decimal("0.30"),
        "no_ask": Decimal("0.72"),
        "yes_ask_size": 1_000_000,
        "no_ask_size": 1_000_000,
        "exposure_window": THIRTY_DAYS,
    }
    return MarketQuote(**{**defaults, **overrides})


def exposure(**overrides) -> Exposure:
    defaults = {
        "daily_revenue": Decimal("1000"),
        "revenue_impact_pct": Decimal("0.20"),
        "hurts_when": Side.YES,
    }
    return Exposure(**{**defaults, **overrides})


def size(market=None, exp=None, budget=UNLIMITED, as_of=AS_OF, **kwargs):
    return size_position(market or quote(), exp or exposure(), budget, as_of=as_of, **kwargs)


def test_window_length_counts_both_end_days():
    assert ONE_DAY.days == 1
    assert ONE_WEEK.days == 7
    assert THIRTY_DAYS.days == 30


def test_revenue_at_risk_scales_with_the_contract_window():
    assert revenue_at_risk(exposure(), ONE_DAY, AS_OF) == Decimal("1000")
    assert revenue_at_risk(exposure(), ONE_WEEK, AS_OF) == Decimal("7000")
    assert revenue_at_risk(exposure(), THIRTY_DAYS, AS_OF) == Decimal("30000")


class TestRemainingExposure:
    """A contract whose window has partly elapsed can only hedge what is still ahead."""

    def test_a_window_still_entirely_ahead_is_fully_exposed(self):
        assert THIRTY_DAYS.remaining_days(date(2026, 9, 20)) == 30

    def test_a_partly_elapsed_window_counts_only_the_remainder(self):
        assert THIRTY_DAYS.remaining_days(date(2026, 10, 10)) == 21

    def test_the_settlement_day_itself_still_counts(self):
        assert THIRTY_DAYS.remaining_days(date(2026, 10, 30)) == 1

    def test_an_elapsed_window_has_nothing_left_to_hedge(self):
        assert THIRTY_DAYS.remaining_days(date(2026, 10, 31)) == 0

    def test_sizing_uses_remaining_days_not_the_whole_window(self):
        position = size(as_of=date(2026, 10, 10))

        assert position.days_hedged == 21
        assert position.revenue_at_risk == Decimal("21000")
        assert position.contracts == 4200

    def test_the_live_october_monthly_case(self):
        """KXB200MS-26OCT covers Oct 1-31. Bought on Oct 10, 10 days are already spent."""
        october = ContractWindow(opens=date(2026, 10, 1), settles=date(2026, 10, 31))

        clipped = size(quote(exposure_window=october), as_of=date(2026, 10, 10))
        unclipped = size(quote(exposure_window=october), as_of=date(2026, 10, 1))

        assert clipped.days_hedged == 22
        assert unclipped.days_hedged == 31
        assert unclipped.contracts > clipped.contracts
        assert clipped.contracts == 4400

    def test_an_elapsed_window_opens_no_position(self):
        position = size(as_of=date(2026, 11, 1))

        assert position.days_hedged == 0
        assert position.contracts == 0
        assert position.premium == Decimal("0")

    def test_position_reports_the_date_it_was_sized_on(self):
        position = size(as_of=date(2026, 10, 10))

        assert position.as_of == date(2026, 10, 10)
        assert position.window == THIRTY_DAYS


@pytest.mark.parametrize(
    ("window", "expected_contracts"),
    [(ONE_DAY, 200), (ONE_WEEK, 1400), (THIRTY_DAYS, 6000)],
)
def test_contract_count_is_period_matched_to_the_contract_window(window, expected_contracts):
    """A daily contract hedges one day of revenue, not a month of it."""
    position = size(quote(exposure_window=window))

    assert position.contracts == expected_contracts
    assert position.days_hedged == window.days


def test_unconstrained_hedge_buys_one_contract_per_dollar_of_shortfall():
    position = size()

    assert position.revenue_at_risk == Decimal("30000")
    assert position.shortfall == Decimal("6000")
    assert position.contracts == 6000
    assert position.hedge_ratio == Decimal("1")
    assert position.binding_constraint is Constraint.FULL_HEDGE


def test_position_reports_its_window_so_output_can_state_the_horizon():
    position = size(quote(exposure_window=ONE_WEEK))

    assert position.window == ONE_WEEK
    assert position.days_hedged == 7
    assert position.revenue_at_risk == Decimal("7000")


@pytest.mark.parametrize("yes_ask", ["0.01", "0.30", "0.50", "0.99"])
def test_contract_count_is_independent_of_price(yes_ask):
    position = size(quote(yes_ask=Decimal(yes_ask)))

    assert position.contracts == 6000
    assert position.premium == 6000 * Decimal(yes_ask)


def test_buys_the_side_that_pays_when_the_business_is_hurt():
    hurt_by_yes = size(exp=exposure(hurts_when=Side.YES))
    hurt_by_no = size(exp=exposure(hurts_when=Side.NO))

    assert hurt_by_yes.side is Side.YES
    assert hurt_by_yes.entry_price == Decimal("0.30")
    assert hurt_by_no.side is Side.NO
    assert hurt_by_no.entry_price == Decimal("0.72")


def test_budget_caps_contracts_and_reports_partial_hedge():
    position = size(budget=Decimal("100"))

    assert position.contracts == 333
    assert position.premium == Decimal("99.90")
    assert position.hedge_ratio == Decimal("0.0555")
    assert position.binding_constraint is Constraint.BUDGET


def test_resting_book_depth_caps_contracts():
    position = size(quote(yes_ask_size=500))

    assert position.contracts == 500
    assert position.binding_constraint is Constraint.LIQUIDITY


def test_depth_factor_takes_only_part_of_the_resting_book():
    position = size(quote(yes_ask_size=500), depth_factor=Decimal("0.5"))

    assert position.contracts == 250


def test_tightest_constraint_wins():
    position = size(quote(yes_ask_size=400), budget=Decimal("60"))

    assert position.contracts == 200
    assert position.binding_constraint is Constraint.BUDGET


def test_fees_raise_unit_cost_and_reduce_affordable_contracts():
    position = size(budget=Decimal("100"), fee_per_contract=Decimal("0.02"))

    assert position.contracts == 312
    assert position.premium == Decimal("99.84")


def test_zero_revenue_impact_opens_no_position():
    position = size(exp=exposure(revenue_impact_pct=Decimal("0")))

    assert position.contracts == 0
    assert position.premium == Decimal("0")
    assert position.hedge_ratio == Decimal("0")


def test_payoff_if_hit_covers_the_shortfall_on_a_full_hedge():
    position = size()

    assert position.payoff_if_hit == position.shortfall == Decimal("6000")


def test_notional_value_above_one_dollar_needs_fewer_contracts():
    position = size(quote(notional_value=Decimal("100"), yes_ask=Decimal("30")))

    assert position.contracts == 60
    assert position.payoff_if_hit == Decimal("6000")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("daily_revenue", Decimal("-1")),
        ("revenue_impact_pct", Decimal("-0.1")),
        ("revenue_impact_pct", Decimal("1.5")),
    ],
)
def test_rejects_nonsensical_exposure(field, value):
    with pytest.raises(ValueError):
        size(exp=exposure(**{field: value}))


def test_rejects_a_window_that_settles_before_it_opens():
    with pytest.raises(ValueError):
        ContractWindow(opens=date(2026, 10, 12), settles=date(2026, 10, 1))


def test_rejects_negative_budget():
    with pytest.raises(ValueError):
        size(budget=Decimal("-1"))


def test_rejects_market_with_no_resting_offer():
    """A yes_ask of 0 means nobody is offering - seen live on illiquid Kalshi markets."""
    with pytest.raises(ValueError):
        size(quote(yes_ask=Decimal("0")))


def test_rejects_ask_above_notional_value():
    with pytest.raises(ValueError):
        size(quote(yes_ask=Decimal("1.01")))
