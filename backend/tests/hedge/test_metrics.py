import random
from decimal import Decimal

import pytest

from app.hedge.metrics import Scenario, compare_hedge, distribution_stats, two_state_scenarios
from app.hedge.sizing import Exposure, MarketQuote, Side, size_position

UNLIMITED = Decimal("1e12")
TOLERANCE = Decimal("0.0000001")

EXPOSURE = Exposure(
    baseline_revenue=Decimal("10000"),
    revenue_impact_pct=Decimal("0.20"),
    hurts_when=Side.YES,
)


def quote(yes_ask: str = "0.30") -> MarketQuote:
    return MarketQuote(
        ticker="KXRAINKC-26OCT12",
        yes_ask=Decimal(yes_ask),
        no_ask=Decimal("0.72"),
        yes_ask_size=1_000_000,
        no_ask_size=1_000_000,
    )


def test_two_state_scenarios_split_revenue_around_the_shortfall():
    bad, good = two_state_scenarios(EXPOSURE, event_probability=Decimal("0.30"))

    assert (bad.probability, bad.revenue, bad.hedge_pays) == (Decimal("0.30"), Decimal("8000"), True)
    assert (good.probability, good.revenue, good.hedge_pays) == (
        Decimal("0.70"),
        Decimal("10000"),
        False,
    )


def test_distribution_stats_on_a_two_point_distribution():
    stats = distribution_stats(two_state_scenarios(EXPOSURE, Decimal("0.30")))

    assert stats.mean == Decimal("9400")
    assert abs(stats.stdev - Decimal("916.5151389911680")) < TOLERANCE
    assert stats.worst_case == Decimal("8000")


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
    scenarios = two_state_scenarios(EXPOSURE, Decimal("0.30"))
    position = size_position(quote(), EXPOSURE, budget=UNLIMITED)

    comparison = compare_hedge(scenarios, position)

    assert comparison.hedged.stdev == Decimal("0")
    assert comparison.volatility_reduction_pct == Decimal("100")


def test_full_hedge_locks_in_the_market_implied_mean():
    """R_good - p*dR, which is also E[R] when the market price equals the true probability."""
    scenarios = two_state_scenarios(EXPOSURE, Decimal("0.30"))
    position = size_position(quote("0.30"), EXPOSURE, budget=UNLIMITED)

    comparison = compare_hedge(scenarios, position)

    assert comparison.hedged.mean == Decimal("9400")
    assert comparison.hedged.worst_case == Decimal("9400")
    assert comparison.expected_cost == Decimal("0")


def test_hedge_gains_expected_value_when_the_market_underprices_the_risk():
    scenarios = two_state_scenarios(EXPOSURE, event_probability=Decimal("0.30"))
    position = size_position(quote("0.20"), EXPOSURE, budget=UNLIMITED)

    comparison = compare_hedge(scenarios, position)

    assert comparison.hedged.mean == Decimal("9600")
    assert comparison.expected_cost == Decimal("-200")


def test_volatility_reduction_tracks_the_hedge_ratio():
    scenarios = two_state_scenarios(EXPOSURE, Decimal("0.30"))
    position = size_position(quote(), EXPOSURE, budget=Decimal("300"))

    comparison = compare_hedge(scenarios, position)

    assert position.contracts == 1000
    assert abs(comparison.volatility_reduction_pct - Decimal("50")) < TOLERANCE
    assert comparison.hedged.worst_case == Decimal("8700")


def test_partial_hedge_still_lifts_the_worst_case():
    scenarios = two_state_scenarios(EXPOSURE, Decimal("0.30"))
    position = size_position(quote(), EXPOSURE, budget=Decimal("300"))

    comparison = compare_hedge(scenarios, position)

    assert comparison.unhedged.worst_case == Decimal("8000")
    assert comparison.hedged.worst_case > comparison.unhedged.worst_case


def test_empty_hedge_leaves_the_distribution_untouched():
    scenarios = two_state_scenarios(EXPOSURE, Decimal("0.30"))
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
        two_state_scenarios(EXPOSURE, Decimal(probability))


def _random_case(rng: random.Random) -> tuple[Exposure, MarketQuote]:
    """A baseline that is a multiple of 100 against a two-decimal impact keeps the shortfall whole."""
    exposure = Exposure(
        baseline_revenue=Decimal(rng.randrange(1, 5_000)) * 100,
        revenue_impact_pct=Decimal(rng.randrange(1, 100)) / 100,
        hurts_when=Side.YES,
    )
    return exposure, quote(str(Decimal(rng.randrange(1, 100)) / 100))


@pytest.mark.parametrize("seed", range(25))
def test_full_hedge_always_eliminates_volatility_for_whole_contract_shortfalls(seed):
    """The invariant the whole approach rests on, checked against arbitrary sizes and prices."""
    exposure, market = _random_case(random.Random(seed))
    scenarios = two_state_scenarios(exposure, Decimal("0.4"))

    comparison = compare_hedge(scenarios, size_position(market, exposure, budget=UNLIMITED))

    assert comparison.hedged.stdev == Decimal("0")


@pytest.mark.parametrize("seed", range(25))
def test_fees_do_not_reintroduce_volatility(seed):
    """Premium leaves the account in every state, so fees shift the level, not the spread."""
    exposure, market = _random_case(random.Random(seed))
    scenarios = two_state_scenarios(exposure, Decimal("0.4"))
    position = size_position(
        market, exposure, budget=UNLIMITED, fee_per_contract=Decimal("0.0175")
    )

    comparison = compare_hedge(scenarios, position)

    assert comparison.hedged.stdev == Decimal("0")


@pytest.mark.parametrize("seed", range(25))
def test_a_fee_raises_expected_cost_by_exactly_the_fee_on_every_contract(seed):
    """The sign of expected_cost is set by mispricing; a fee only shifts it, per contract."""
    fee = Decimal("0.0175")
    exposure, market = _random_case(random.Random(seed))
    scenarios = two_state_scenarios(exposure, Decimal("0.4"))
    charged_position = size_position(
        market, exposure, budget=UNLIMITED, fee_per_contract=fee
    )

    free = compare_hedge(scenarios, size_position(market, exposure, budget=UNLIMITED))
    charged = compare_hedge(scenarios, charged_position)

    assert charged.expected_cost - free.expected_cost == charged_position.contracts * fee


def test_rounding_residual_after_a_full_hedge_stays_under_one_contract():
    """A fractional shortfall cannot be hedged exactly, but the leftover is bounded by rounding."""
    exposure = Exposure(
        baseline_revenue=Decimal("12345.67"),
        revenue_impact_pct=Decimal("0.137"),
        hurts_when=Side.YES,
    )
    scenarios = two_state_scenarios(exposure, Decimal("0.3"))
    position = size_position(quote(), exposure, budget=UNLIMITED)

    comparison = compare_hedge(scenarios, position)

    assert position.ideal_contracts != position.contracts
    assert Decimal("0") < comparison.hedged.stdev < quote().notional_value
