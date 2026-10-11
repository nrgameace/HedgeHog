"""Sizing a stake to the period it is supposed to cover.

A trade row reading "Extreme heat, $1, monthly, Jun-Aug" implies the summer is
covered. But `KXHIGHAUS` settles daily, so one contract covers one day of June,
not June - about a thirtieth of the protection the row claims, bought for a
thirtieth of the honest price. `KXRAINAUSM` settles on the whole month, so one
contract really does cover it. Both land in the same report, sized identically.

So a monthly stake is scaled by how many of a series' contracts a month
contains: about thirty for a daily series, one for a monthly one. That makes the
price of cover honest, which is what the budget is then measured against.

Cadence comes from `market_catalog`, which takes it from Kalshi's own `/series`
frequency. It is deliberately not inferred from the ticker: `KXAAAGASM-26OCT31`
looks day-precise but settles a monthly average, while `KXHIGHAUS-26OCT11`
really does settle a single day, so the ticker gets it wrong in both directions.

Scaling cannot invent cover, because the shortfall cap still bounds the payout
by the hole the month actually had.
"""

from app.market_catalog import DAILY, cadence_of

# The calendar average, so a month of daily cover is not short by half a week.
DAYS_PER_MONTH = 365 / 12


def contracts_per_month(ticker: str) -> float:
    """How many contracts of this series it takes to cover one month."""
    return DAYS_PER_MONTH if cadence_of(ticker) == DAILY else 1.0


def stake_for_month(per_contract_usd: int, ticker: str) -> int:
    """What covering a month with this series actually costs, given a per-contract stake."""
    return max(round(per_contract_usd * contracts_per_month(ticker)), 1)


def covers_whole_month(ticker: str) -> bool:
    return cadence_of(ticker) != DAILY
