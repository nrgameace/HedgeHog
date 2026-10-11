"""Assembling the `HedgeReport` the results page expects.

The frontend wants a *retrospective* story: twelve months of actual profit
against a normal year, and what each trade would have netted month by month
(`frontend/src/types.ts`). Sizing and metrics answer a forward-looking question
instead, so this module builds the backward-looking view from the uploaded CSV.

Two numbers here are honest reconstructions rather than measurements, and both
are labelled as such:

- **`expected`** is the same calendar month averaged over the business's *other*
  years, so a seasonal business is compared against its own seasonality rather
  than a flat line. That is what makes a washed-out May show up as a shortfall.
- **`monthlyNetUsd`** needs to know which months the factor actually bit, and
  Kalshi cannot say: the markets being recommended did not exist last year. So
  `proxy_hit_months` reads it off the business's own financials - the months a
  cost column sat in its worst quartile - which is real data about real harm,
  but is a stand-in for resolving the market itself. `simulated` in the payload
  says so.

Pure functions only: no network, no model calls.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.hedge.exposure import parse_money

MONTH_LABELS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MONTHS_IN_YEAR = 12

# A month in the worst quarter of a cost column's history counts as the factor
# biting. Loose enough to catch real spikes without firing most months.
DEFAULT_SPIKE_QUANTILE = Decimal("0.75")


@dataclass(frozen=True)
class ProfitPoint:
    period: str
    expected: int
    actual: int

    def as_payload(self) -> dict:
        return {"period": self.period, "expected": self.expected, "actual": self.actual}


@dataclass(frozen=True)
class BetReport:
    risk_factor: str
    risk_explanation: str
    market: str
    ticker: str
    side: str
    amount_usd: int
    frequency: str
    trade_months: tuple[int, ...]
    rationale: str
    monthly_net_usd: tuple[int, ...]

    def as_payload(self) -> dict:
        return {
            "risk": {"factor": self.risk_factor, "explanation": self.risk_explanation},
            "market": self.market,
            "ticker": self.ticker,
            "side": self.side,
            "amountUsd": self.amount_usd,
            "frequency": self.frequency,
            "tradeMonths": list(self.trade_months),
            "rationale": self.rationale,
            "monthlyNetUsd": list(self.monthly_net_usd),
        }


def month_index(row: dict[str, str], month_column: str = "month") -> tuple[int, int] | None:
    """`2024-05` -> (2024, 4). None when the cell is not a year-month."""
    raw = (row.get(month_column) or "").strip()
    parts = raw.split("-")
    if len(parts) < 2 or not parts[0].isdigit() or not parts[1].isdigit():
        return None

    year, month = int(parts[0]), int(parts[1])
    if not 1 <= month <= MONTHS_IN_YEAR:
        return None
    return year, month - 1


def latest_full_year(rows: Sequence[dict[str, str]], month_column: str = "month") -> int | None:
    """The most recent year with all twelve months present, so a partial year is not compared."""
    counts: dict[int, set[int]] = {}
    for row in rows:
        parsed = month_index(row, month_column)
        if parsed is None:
            continue
        year, month = parsed
        counts.setdefault(year, set()).add(month)

    complete = [year for year, months in counts.items() if len(months) == MONTHS_IN_YEAR]
    return max(complete) if complete else None


def worst_full_year(rows: Sequence[dict[str, str]], profit_column: str, month_column: str = "month") -> int | None:
    """The complete year whose profit fell furthest below its own seasonal normal.

    Offered alongside `latest_full_year` because the two answer different
    questions and the choice should be deliberate. The most recent year is the
    neutral default; a year the risk actually materialised in shows what the
    hedge is for, but picking it is an illustration and should be labelled as
    one rather than passed off as typical. On the ice cream demo data the latest
    complete year is a good one, where the honest answer is that these trades
    would not have helped.
    """
    years = {
        parsed[0]
        for row in rows
        if (parsed := month_index(row, month_column)) is not None
    }
    complete = [year for year in years if _is_complete(rows, year, month_column)]
    if not complete:
        return None

    return max(complete, key=lambda year: _downside(monthly_profit(rows, profit_column, year)))


def monthly_profit(rows: Sequence[dict[str, str]], profit_column: str, year: int, month_column: str = "month") -> list[ProfitPoint]:
    """Twelve months of actual profit against the same months in the business's other years."""
    by_year: dict[int, dict[int, Decimal]] = {}
    for row in rows:
        parsed = month_index(row, month_column)
        value = parse_money(row.get(profit_column, ""))
        if parsed is None or value is None:
            continue
        by_year.setdefault(parsed[0], {})[parsed[1]] = value

    actuals = by_year.get(year, {})
    points = []
    for month, label in enumerate(MONTH_LABELS):
        actual = actuals.get(month, Decimal("0"))
        points.append(
            ProfitPoint(
                period=label,
                expected=int(_seasonal_normal(by_year, year, month, actual)),
                actual=int(actual),
            )
        )
    return points


def proxy_hit_months(rows: Sequence[dict[str, str]], proxy_column: str, year: int, month_column: str = "month", quantile: Decimal = DEFAULT_SPIKE_QUANTILE) -> tuple[int, ...]:
    """Months of `year` where `proxy_column` sat in the worst tail of its own history.

    A stand-in for resolving the recommended market historically, which cannot be
    done: those markets did not exist then. This at least keys the payouts to
    something that really happened to this business.
    """
    history: list[Decimal] = []
    in_year: dict[int, Decimal] = {}
    for row in rows:
        parsed = month_index(row, month_column)
        value = parse_money(row.get(proxy_column, ""))
        if parsed is None or value is None:
            continue
        history.append(value)
        if parsed[0] == year:
            in_year[parsed[1]] = value

    if not history or not in_year:
        return ()

    threshold = _quantile(history, quantile)
    return tuple(sorted(month for month, value in in_year.items() if value >= threshold))


def simulate_net(stake: Decimal, price: Decimal, trade_months: Sequence[int], hit_months: Sequence[int]) -> tuple[int, ...]:
    """Payouts minus stakes per month: staked every trade month, paid only when it also hit.

    A payout needs a position, so a hit in a month with no trade pays nothing -
    the alternative would credit winnings on a bet that was never placed.
    """
    traded, hit = set(trade_months), set(hit_months)
    net = []
    for month in range(MONTHS_IN_YEAR):
        if month not in traded:
            net.append(0)
            continue
        payout = stake / price if (month in hit and price > 0) else Decimal("0")
        net.append(int(payout - stake))
    return tuple(net)


def build_report(bets: Sequence[BetReport], profit_series: Sequence[ProfitPoint], year: int) -> dict:
    """The payload shape `frontend/src/types.ts` declares, plus how it was produced."""
    return {
        "bets": [bet.as_payload() for bet in bets],
        "profitSeries": [point.as_payload() for point in profit_series],
        "simulatedPeriod": str(year),
        "simulated": True,
    }


def _is_complete(rows: Sequence[dict[str, str]], year: int, month_column: str) -> bool:
    months = {
        parsed[1]
        for row in rows
        if (parsed := month_index(row, month_column)) is not None and parsed[0] == year
    }
    return len(months) == MONTHS_IN_YEAR


def _downside(points: Sequence[ProfitPoint]) -> int:
    """How far the year fell short of normal, counting only the months that did."""
    return sum(max(point.expected - point.actual, 0) for point in points)


def _seasonal_normal(by_year: dict[int, dict[int, Decimal]], year: int, month: int, fallback: Decimal) -> Decimal:
    """What this month usually earns, averaged over the business's other years."""
    others = [
        months[month] for other, months in by_year.items() if other != year and month in months
    ]
    if not others:
        return fallback
    return sum(others, start=Decimal("0")) / len(others)


def _quantile(values: Sequence[Decimal], fraction: Decimal) -> Decimal:
    """Linearly interpolated quantile.

    Interpolating matters where values tie: picking the nearest index instead
    lands on a repeated low value, which drags the threshold down until every
    month counts as a spike.
    """
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]

    position = (len(ordered) - 1) * fraction
    lower = int(position)
    if lower >= len(ordered) - 1:
        return ordered[-1]
    return ordered[lower] + (position - lower) * (ordered[lower + 1] - ordered[lower])
