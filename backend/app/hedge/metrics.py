"""Before/after statistics for a hedge, in the shape the results dashboard needs.

Scenarios are a discrete, probability-weighted set of revenue outcomes. Keeping
the statistics defined over that set (rather than over a closed-form two-state
model) means the same functions serve the multi-factor portfolio later, where
scenarios come from enumerating joint event outcomes.

Pure functions only: no network, no model calls.
"""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.hedge.sizing import ContractWindow, Exposure, HedgePosition, revenue_at_risk

PROBABILITY_TOLERANCE = Decimal("0.000001")
DOWNSIDE_PERCENTILE = Decimal("0.05")


@dataclass(frozen=True)
class Scenario:
    """One possible revenue outcome. `hedge_pays` marks the states the hedge settles in favour of."""

    label: str
    probability: Decimal
    revenue: Decimal
    hedge_pays: bool = False


@dataclass(frozen=True)
class DistributionStats:
    mean: Decimal
    stdev: Decimal
    worst_case: Decimal
    percentile_5: Decimal


@dataclass(frozen=True)
class HedgeComparison:
    unhedged: DistributionStats
    hedged: DistributionStats
    volatility_reduction_pct: Decimal
    expected_cost: Decimal
    premium: Decimal


def two_state_scenarios(exposure: Exposure, window: ContractWindow, event_probability: Decimal, as_of: date | None = None) -> tuple[Scenario, Scenario]:
    """Collapse an exposure into the bad state (the risk factor bites) and the good state.

    Revenue is measured over whatever of `window` is still ahead on `as_of`, matching
    how `size_position` clips the same window, so the scenarios and the hedge sized
    against them describe the same exposure.
    """
    if not 0 <= event_probability <= 1:
        raise ValueError(f"event_probability must fall in [0, 1], got {event_probability}")

    today = as_of or date.today()
    at_risk = revenue_at_risk(exposure, window, today)
    shortfall = at_risk * exposure.revenue_impact_pct
    horizon = f"{window.remaining_days(today)}d to {window.settles}"
    return (
        Scenario(
            label=f"risk factor hits ({horizon})",
            probability=event_probability,
            revenue=at_risk - shortfall,
            hedge_pays=True,
        ),
        Scenario(
            label=f"risk factor misses ({horizon})",
            probability=1 - event_probability,
            revenue=at_risk,
            hedge_pays=False,
        ),
    )


def distribution_stats(scenarios: tuple[Scenario, ...]) -> DistributionStats:
    """Probability-weighted mean, standard deviation and downside of a scenario set."""
    _validate_scenarios(scenarios)

    mean = sum((s.probability * s.revenue for s in scenarios), start=Decimal("0"))
    variance = sum(
        (s.probability * (s.revenue - mean) ** 2 for s in scenarios), start=Decimal("0")
    )

    return DistributionStats(
        mean=mean,
        stdev=variance.sqrt(),
        worst_case=min(s.revenue for s in scenarios),
        percentile_5=_percentile(scenarios, DOWNSIDE_PERCENTILE),
    )


def compare_hedge(scenarios: tuple[Scenario, ...], position: HedgePosition) -> HedgeComparison:
    """Contrast the unhedged revenue distribution with the one the position produces."""
    unhedged = distribution_stats(scenarios)
    hedged = distribution_stats(tuple(_apply(s, position) for s in scenarios))

    return HedgeComparison(
        unhedged=unhedged,
        hedged=hedged,
        volatility_reduction_pct=_reduction_pct(unhedged.stdev, hedged.stdev),
        expected_cost=unhedged.mean - hedged.mean,
        premium=position.premium,
    )


def _apply(scenario: Scenario, position: HedgePosition) -> Scenario:
    """Premium leaves the account in every state; the payoff only arrives where the hedge settles."""
    settlement = position.payoff_if_hit if scenario.hedge_pays else Decimal("0")
    return Scenario(
        label=scenario.label,
        probability=scenario.probability,
        revenue=scenario.revenue + settlement - position.premium,
        hedge_pays=scenario.hedge_pays,
    )


def _percentile(scenarios: tuple[Scenario, ...], target: Decimal) -> Decimal:
    """Inverse CDF of a discrete distribution: the worst revenue still inside the target tail."""
    cumulative = Decimal("0")
    for scenario in sorted(scenarios, key=lambda s: s.revenue):
        cumulative += scenario.probability
        if cumulative >= target:
            return scenario.revenue
    return max(s.revenue for s in scenarios)


def _reduction_pct(before: Decimal, after: Decimal) -> Decimal:
    """How much of the revenue volatility the hedge removed, as a percentage."""
    if before == 0:
        return Decimal("0")
    return (1 - after / before) * 100


def _validate_scenarios(scenarios: tuple[Scenario, ...]) -> None:
    if not scenarios:
        raise ValueError("need at least one scenario to describe a distribution")

    total = sum((s.probability for s in scenarios), start=Decimal("0"))
    if abs(total - 1) > PROBABILITY_TOLERANCE:
        raise ValueError(f"scenario probabilities must sum to 1, got {total}")
    if any(s.probability < 0 for s in scenarios):
        raise ValueError("scenario probabilities must be non-negative")
