"""Position sizing for a single binary-contract hedge.

A Kalshi contract pays its notional value if the event resolves in your favour
and nothing otherwise, so buying `n` contracts that pay in the state where
revenue falls short by `dR` equalises both states when `n * notional == dR`:

    event happens:  R_bad  + n*(notional - price)
    event doesn't:  R_good - n*price

Setting those equal cancels the price terms, leaving `n * notional = dR`. The
contract count therefore depends only on the revenue shortfall, never on the
price - price decides what the hedge *costs*, not how large it is.

Pure functions only: no network, no model calls, no Kalshi types.
"""

from dataclasses import dataclass
from decimal import ROUND_FLOOR, Decimal
from enum import Enum

ONE_DOLLAR = Decimal("1")
WHOLE_BOOK = Decimal("1")


class Side(Enum):
    YES = "yes"
    NO = "no"


class Constraint(Enum):
    """Which limit decided the final contract count. Ordered so ties resolve to the mildest."""

    FULL_HEDGE = 0
    BUDGET = 1
    LIQUIDITY = 2


@dataclass(frozen=True)
class MarketQuote:
    """Ask-side snapshot of one Kalshi market. Prices are per contract, in dollars."""

    ticker: str
    yes_ask: Decimal
    no_ask: Decimal
    yes_ask_size: int
    no_ask_size: int
    notional_value: Decimal = ONE_DOLLAR


@dataclass(frozen=True)
class Exposure:
    """What the business stands to lose, as produced by the position-sizing model call."""

    baseline_revenue: Decimal
    revenue_impact_pct: Decimal
    hurts_when: Side


@dataclass(frozen=True)
class HedgePosition:
    ticker: str
    side: Side
    contracts: int
    entry_price: Decimal
    premium: Decimal
    payoff_if_hit: Decimal
    shortfall: Decimal
    ideal_contracts: Decimal
    hedge_ratio: Decimal
    binding_constraint: Constraint


def size_position(quote: MarketQuote, exposure: Exposure, budget: Decimal, fee_per_contract: Decimal = Decimal("0"), depth_factor: Decimal = WHOLE_BOOK) -> HedgePosition:
    """Size the hedge that pays when `exposure` bites, capped by budget and resting book depth."""
    _validate(quote, exposure, budget, fee_per_contract, depth_factor)

    side = exposure.hurts_when
    ask, ask_size = _ask_side(quote, side)
    shortfall = exposure.baseline_revenue * exposure.revenue_impact_pct
    ideal = shortfall / quote.notional_value

    unit_cost = ask + fee_per_contract
    caps = {
        Constraint.FULL_HEDGE: ideal,
        Constraint.BUDGET: budget / unit_cost,
        Constraint.LIQUIDITY: depth_factor * ask_size,
    }
    binding_constraint = min(caps, key=lambda limit: (_floor(caps[limit]), limit.value))
    contracts = int(_floor(caps[binding_constraint]))

    return HedgePosition(
        ticker=quote.ticker,
        side=side,
        contracts=contracts,
        entry_price=ask,
        premium=contracts * unit_cost,
        payoff_if_hit=contracts * quote.notional_value,
        shortfall=shortfall,
        ideal_contracts=ideal,
        hedge_ratio=(contracts / ideal if ideal > 0 else Decimal("0")),
        binding_constraint=binding_constraint,
    )


def _validate(quote: MarketQuote, exposure: Exposure, budget: Decimal, fee_per_contract: Decimal, depth_factor: Decimal) -> None:
    """Reject inputs that would make the sizing math meaningless rather than merely wrong."""
    if exposure.baseline_revenue < 0:
        raise ValueError(f"baseline_revenue must be non-negative, got {exposure.baseline_revenue}")
    if not 0 <= exposure.revenue_impact_pct <= 1:
        raise ValueError(
            f"revenue_impact_pct must fall in [0, 1], got {exposure.revenue_impact_pct}"
        )
    if budget < 0:
        raise ValueError(f"budget must be non-negative, got {budget}")
    if fee_per_contract < 0:
        raise ValueError(f"fee_per_contract must be non-negative, got {fee_per_contract}")
    if not 0 <= depth_factor <= 1:
        raise ValueError(f"depth_factor must fall in [0, 1], got {depth_factor}")
    if quote.notional_value <= 0:
        raise ValueError(f"notional_value must be positive, got {quote.notional_value}")

    ask, ask_size = _ask_side(quote, exposure.hurts_when)
    if ask <= 0:
        raise ValueError(f"{quote.ticker}: no resting {exposure.hurts_when.value} offer to buy")
    if ask > quote.notional_value:
        raise ValueError(
            f"{quote.ticker}: {exposure.hurts_when.value} ask {ask} exceeds notional "
            f"{quote.notional_value}"
        )
    if ask_size < 0:
        raise ValueError(f"{quote.ticker}: ask size must be non-negative, got {ask_size}")


def _ask_side(quote: MarketQuote, side: Side) -> tuple[Decimal, int]:
    """The price we pay and the depth available on the side we are buying."""
    if side is Side.YES:
        return quote.yes_ask, quote.yes_ask_size
    return quote.no_ask, quote.no_ask_size


def _floor(contracts: Decimal) -> Decimal:
    """Contracts are indivisible, and rounding up would overshoot the cap that bound."""
    return contracts.to_integral_value(rounding=ROUND_FLOOR)
