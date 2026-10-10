import random
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.hedge.metrics import Scenario, compare_hedge, distribution_stats, two_state_scenarios
from app.hedge.sizing import (
    Constraint,
    ContractWindow,
    Exposure,
    MarketQuote,
    Side,
    size_position,
)

UNLIMITED = Decimal("1e12")
DEEP_BOOK = 10_000_000
TOLERANCE = Decimal("0.0000001")

THIRTY_DAYS = ContractWindow(opens=date(2026, 10, 1), settles=date(2026, 10, 30))
ONE_DAY = ContractWindow(opens=date(2026, 10, 12), settles=date(2026, 10, 12))

EXPOSURE = Exposure(
    daily_revenue=Decimal("1000"),
    revenue_impact_pct=Decimal("0.20"),
    hurts_when=Side.YES,
)


def quote(yes_ask: str = "0.30", window: ContractWindow = THIRTY_DAYS, ask_size: int = 1_000_000) -> MarketQuote:
    return MarketQuote(
        ticker="KXRAINKC-26OCT12",
        yes_ask=Decimal(yes_ask),
        no_ask=Decimal("0.72"),
        yes_ask_size=ask_size,
        no_ask_size=ask_size,
        exposure_window=window,
    )


def test_two_state_scenarios_split_revenue_over_the_contract_window():
    bad, good = two_state_scenarios(EXPOSURE, THIRTY_DAYS, event_probability=Decimal("0.30"))

    assert (bad.probability, bad.revenue, bad.hedge_pays) == (
        Decimal("0.30"),
        Decimal("24000"),
        True,
    )
    assert (good.probability, good.revenue, good.hedge_pays) == (
        Decimal("0.70"),
        Decimal("30000"),
        False,
    )


def test_two_state_scenarios_shrink_with_a_shorter_window():
    bad, good = two_state_scenarios(EXPOSURE, ONE_DAY, event_probability=Decimal("0.30"))

    assert bad.revenue == Decimal("800")
    assert good.revenue == Decimal("1000")


def test_distribution_stats_on_a_two_point_distribution():
    stats = distribution_stats(two_state_scenarios(EXPOSURE, THIRTY_DAYS, Decimal("0.30")))

    assert stats.mean == Decimal("28200")
    assert abs(stats.stdev * stats.stdev - Decimal("7560000")) < TOLERANCE
    assert stats.worst_case == Decimal("24000")


def test_percentile_5_ignores_the_mildest_outcomes():
    scenarios = (
        Scenario(label="washout", probability=Decimal("0.04"), revenue=Decimal("5000")),
        Scenario(label="rain", probability=Decimal("0.26"), revenue=Decimal("8000")),
        Scenario(label="dry", probability=Decimal("0.70"), revenue=Decimal("10000")),
    )

    stats = distribution_stats(scenarios)

    assert stats.worst_case == Decimal("5000")
    assert stats.percentile_5 == Decimal("8000")


def test_full_hedge_eliminates_volatility_entirely():
    scenarios = two_state_scenarios(EXPOSURE, THIRTY_DAYS, Decimal("0.30"))
    position = size_position(quote(), EXPOSURE, budget=UNLIMITED)

    comparison = compare_hedge(scenarios, position)

    assert comparison.hedged.stdev == Decimal("0")
    assert comparison.volatility_reduction_pct == Decimal("100")


def test_full_hedge_locks_in_the_market_implied_mean():
    """R_good - p*dR, which is also E[R] when the market price equals the true probability."""
    scenarios = two_state_scenarios(EXPOSURE, THIRTY_DAYS, Decimal("0.30"))
    position = size_position(quote("0.30"), EXPOSURE, budget=UNLIMITED)

    comparison = compare_hedge(scenarios, position)

    assert comparison.hedged.mean == Decimal("28200")
    assert comparison.hedged.worst_case == Decimal("28200")
    assert comparison.expected_cost == Decimal("0")


def test_hedge_gains_expected_value_when_the_market_underprices_the_risk():
    scenarios = two_state_scenarios(EXPOSURE, THIRTY_DAYS, event_probability=Decimal("0.30"))
    position = size_position(quote("0.20"), EXPOSURE, budget=UNLIMITED)

    comparison = compare_hedge(scenarios, position)

    assert comparison.hedged.mean == Decimal("28800")
    assert comparison.expected_cost == Decimal("-600")


def test_volatility_reduction_tracks_the_hedge_ratio():
    scenarios = two_state_scenarios(EXPOSURE, THIRTY_DAYS, Decimal("0.30"))
    position = size_position(quote(), EXPOSURE, budget=Decimal("900"))

    comparison = compare_hedge(scenarios, position)

    assert position.contracts == 3000
    assert abs(comparison.volatility_reduction_pct - Decimal("50")) < TOLERANCE
    assert comparison.hedged.worst_case == Decimal("26100")


def test_partial_hedge_still_lifts_the_worst_case():
    scenarios = two_state_scenarios(EXPOSURE, THIRTY_DAYS, Decimal("0.30"))
    position = size_position(quote(), EXPOSURE, budget=Decimal("900"))

    comparison = compare_hedge(scenarios, position)

    assert comparison.unhedged.worst_case == Decimal("24000")
    assert comparison.hedged.worst_case > comparison.unhedged.worst_case


def test_a_daily_contract_fully_hedges_its_own_day():
    """Period matching means a one-day contract still reaches a complete hedge of that day."""
    scenarios = two_state_scenarios(EXPOSURE, ONE_DAY, Decimal("0.30"))
    position = size_position(quote(window=ONE_DAY), EXPOSURE, budget=UNLIMITED)

    comparison = compare_hedge(scenarios, position)

    assert position.contracts == 200
    assert comparison.hedged.stdev == Decimal("0")


def test_empty_hedge_leaves_the_distribution_untouched():
    scenarios = two_state_scenarios(EXPOSURE, THIRTY_DAYS, Decimal("0.30"))
    position = size_position(quote(), EXPOSURE, budget=Decimal("0"))

    comparison = compare_hedge(scenarios, position)

    assert position.contracts == 0
    assert comparison.hedged == comparison.unhedged
    assert comparison.volatility_reduction_pct == Decimal("0")


def test_rejects_probabilities_that_do_not_sum_to_one():
    scenarios = (
        Scenario(label="rain", probability=Decimal("0.3"), revenue=Decimal("8000")),
        Scenario(label="dry", probability=Decimal("0.5"), revenue=Decimal("10000")),
    )

    with pytest.raises(ValueError):
        distribution_stats(scenarios)


def test_rejects_an_empty_scenario_set():
    with pytest.raises(ValueError):
        distribution_stats(())


@pytest.mark.parametrize("probability", ["-0.1", "1.1"])
def test_rejects_event_probability_outside_zero_to_one(probability):
    with pytest.raises(ValueError):
        two_state_scenarios(EXPOSURE, THIRTY_DAYS, Decimal(probability))


def _random_case(rng: random.Random) -> tuple[Exposure, MarketQuote]:
    """A daily revenue that is a multiple of 100 keeps the shortfall whole at any window length."""
    exposure = Exposure(
        daily_revenue=Decimal(rng.randrange(1, 500)) * 100,
        revenue_impact_pct=Decimal(rng.randrange(1, 100)) / 100,
        hurts_when=Side.YES,
    )
    opens = date(2026, 10, 1)
    window = ContractWindow(opens=opens, settles=opens + timedelta(days=rng.randrange(0, 90)))
    price = str(Decimal(rng.randrange(1, 100)) / 100)
    return exposure, quote(price, window, ask_size=DEEP_BOOK)


@pytest.mark.parametrize("seed", range(25))
def test_full_hedge_always_eliminates_volatility_at_any_window_length(seed):
    """The invariant the whole approach rests on, across arbitrary sizes, prices and horizons."""
    exposure, market = _random_case(random.Random(seed))
    scenarios = two_state_scenarios(exposure, market.exposure_window, Decimal("0.4"))

    position = size_position(market, exposure, budget=UNLIMITED)
    comparison = compare_hedge(scenarios, position)

    assert position.binding_constraint is Constraint.FULL_HEDGE
    assert comparison.hedged.stdev == Decimal("0")


@pytest.mark.parametrize("seed", range(25))
def test_fees_do_not_reintroduce_volatility(seed):
    """Premium leaves the account in every state, so fees shift the level, not the spread."""
    exposure, market = _random_case(random.Random(seed))
    scenarios = two_state_scenarios(exposure, market.exposure_window, Decimal("0.4"))
    position = size_position(
        market, exposure, budget=UNLIMITED, fee_per_contract=Decimal("0.0175")
    )

    comparison = compare_hedge(scenarios, position)

    assert position.binding_constraint is Constraint.FULL_HEDGE
    assert comparison.hedged.stdev == Decimal("0")


@pytest.mark.parametrize("seed", range(25))
def test_a_fee_raises_expected_cost_by_exactly_the_fee_on_every_contract(seed):
    """The sign of expected_cost is set by mispricing; a fee only shifts it, per contract."""
    fee = Decimal("0.0175")
    exposure, market = _random_case(random.Random(seed))
    scenarios = two_state_scenarios(exposure, market.exposure_window, Decimal("0.4"))
    charged_position = size_position(market, exposure, budget=UNLIMITED, fee_per_contract=fee)

    free = compare_hedge(scenarios, size_position(market, exposure, budget=UNLIMITED))
    charged = compare_hedge(scenarios, charged_position)

    assert charged.expected_cost - free.expected_cost == charged_position.contracts * fee


def test_rounding_residual_after_a_full_hedge_stays_under_one_contract():
    """A fractional shortfall cannot be hedged exactly, but the leftover is bounded by rounding."""
    exposure = Exposure(
        daily_revenue=Decimal("411.52"),
        revenue_impact_pct=Decimal("0.137"),
        hurts_when=Side.YES,
    )
    scenarios = two_state_scenarios(exposure, THIRTY_DAYS, Decimal("0.3"))
    position = size_position(quote(), exposure, budget=UNLIMITED)

    comparison = compare_hedge(scenarios, position)

    assert position.ideal_contracts != position.contracts
    assert Decimal("0") < comparison.hedged.stdev < quote().notional_value
