"""Kalshi payloads, parsed into the shapes the hedge math needs.

Every field here was checked against live production responses on 2026-10-10,
because several diverge from the published docs:

- Prices arrive as dollar *strings* (`"0.6400"`), parsed to Decimal so money
  never touches a float.
- Sizes and volumes arrive as `*_fp` decimal strings (`"191.00"`, `"81.61"`),
  not scaled integers. Fractional sizes floor, since a partial contract cannot
  be bought.
- `status` is one of `initialized` / `active` / `inactive` / `finalized`. None
  of the documented `unopened/paused/open/closed/settled` values appear, so
  tradeability is decided by `active` alone.
- The orderbook publishes two *bid* ladders. An ask on one side is a bid on the
  other at `notional - price`, which `OrderBook` mirrors in one place.
"""

import calendar
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import ROUND_FLOOR, Decimal

from app.hedge.sizing import ContractWindow, MarketQuote, Side

ONE_DOLLAR = Decimal("1")
TRADEABLE_STATUS = "active"

# Categories a small business can plausibly hedge against. Dropping the rest
# removes roughly 11,700 of the 14,942 live series before any scoring.
BUSINESS_CATEGORIES = frozenset(
    {
        "Climate and Weather",
        "Commodities",
        "Companies",
        "Economics",
        "Financials",
        "Science and Technology",
        "Transportation",
        "World",
    }
)

# Nominal horizon per series frequency. `custom` and `one_off` are deliberately
# absent: without a known horizon the shortfall cannot be period-matched, and
# guessing one would silently mis-size the hedge.
NOMINAL_WINDOW_DAYS = {
    "hourly": 1,
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "quarterly": 91,
    "annual": 365,
}

_MONTHS = {m.upper(): i for i, m in enumerate(calendar.month_abbr) if m}


@dataclass(frozen=True)
class Series:
    ticker: str
    title: str
    frequency: str
    categories: tuple[str, ...]

    @classmethod
    def from_api(cls, payload: dict) -> "Series":
        return cls(
            ticker=payload["ticker"],
            title=payload.get("title") or "",
            frequency=payload.get("frequency") or "",
            categories=tuple(payload.get("categories") or ()),
        )

    @property
    def is_business_relevant(self) -> bool:
        return any(category in BUSINESS_CATEGORIES for category in self.categories)

    @property
    def is_test_series(self) -> bool:
        """Test series sit beside the real ones in live responses and carry no book."""
        return "TEST" in self.ticker.upper()


@dataclass(frozen=True)
class Market:
    ticker: str
    event_ticker: str
    title: str
    status: str
    close_time: datetime | None
    yes_ask: Decimal
    no_ask: Decimal
    yes_ask_size: int
    no_ask_size: int
    notional_value: Decimal
    strike_type: str

    @classmethod
    def from_api(cls, payload: dict) -> "Market":
        return cls(
            ticker=payload["ticker"],
            event_ticker=payload.get("event_ticker") or "",
            title=payload.get("title") or "",
            status=payload.get("status") or "",
            strike_type=payload.get("strike_type") or "",
            close_time=_timestamp(payload.get("close_time")),
            yes_ask=_dollars(payload.get("yes_ask_dollars")),
            no_ask=_dollars(payload.get("no_ask_dollars")),
            yes_ask_size=_contracts(payload.get("yes_ask_size_fp")),
            no_ask_size=_contracts(payload.get("no_ask_size_fp")),
            notional_value=_dollars(payload.get("notional_value_dollars")) or ONE_DOLLAR,
        )

    @property
    def is_tradeable(self) -> bool:
        return self.status == TRADEABLE_STATUS

    def to_quote(self, window: ContractWindow) -> MarketQuote:
        """Top-of-book quote. Prefer `OrderBook.to_quote` - top-of-book understates depth."""
        return MarketQuote(
            ticker=self.ticker,
            yes_ask=self.yes_ask,
            no_ask=self.no_ask,
            yes_ask_size=self.yes_ask_size,
            no_ask_size=self.no_ask_size,
            exposure_window=window,
            notional_value=self.notional_value,
        )


@dataclass(frozen=True)
class PriceLevel:
    price: Decimal
    contracts: int


@dataclass(frozen=True)
class Fill:
    """The result of walking an ask ladder up to a limit price."""

    contracts: int
    cost: Decimal
    average_price: Decimal | None
    worst_price: Decimal | None


@dataclass(frozen=True)
class OrderBook:
    ticker: str
    yes_bids: tuple[PriceLevel, ...]
    no_bids: tuple[PriceLevel, ...]
    notional_value: Decimal = ONE_DOLLAR

    @classmethod
    def from_api(cls, ticker: str, payload: dict) -> "OrderBook":
        book = payload.get("orderbook_fp") or payload.get("orderbook") or {}
        return cls(
            ticker=ticker,
            yes_bids=_levels(book.get("yes_dollars")),
            no_bids=_levels(book.get("no_dollars")),
        )

    def asks(self, side: Side) -> tuple[PriceLevel, ...]:
        """Buying one side means lifting the other side's bids at `notional - price`."""
        opposing = self.no_bids if side is Side.YES else self.yes_bids
        mirrored = (
            PriceLevel(self.notional_value - level.price, level.contracts) for level in opposing
        )
        return tuple(sorted(mirrored, key=lambda level: level.price))

    def best_ask(self, side: Side) -> PriceLevel | None:
        ladder = self.asks(side)
        return ladder[0] if ladder else None

    def depth_up_to(self, side: Side, limit_price: Decimal) -> Fill:
        """Everything buyable at or below `limit_price`, with the average price paid."""
        fills = [level for level in self.asks(side) if level.price <= limit_price]
        contracts = sum(level.contracts for level in fills)
        cost = sum((level.price * level.contracts for level in fills), start=Decimal("0"))

        return Fill(
            contracts=contracts,
            cost=cost,
            average_price=(cost / contracts if contracts else None),
            worst_price=(fills[-1].price if fills else None),
        )

    def to_quote(self, window: ContractWindow, limit_price: Decimal | None = None) -> MarketQuote:
        """Quote both sides at the depth a limit price actually reaches.

        A side the limit cannot reach is reported as a zero ask, which `size_position`
        rejects as having no resting offer rather than sizing against a phantom book.
        """
        limit = self.notional_value if limit_price is None else limit_price
        yes, no = self.depth_up_to(Side.YES, limit), self.depth_up_to(Side.NO, limit)

        return MarketQuote(
            ticker=self.ticker,
            yes_ask=yes.average_price or Decimal("0"),
            no_ask=no.average_price or Decimal("0"),
            yes_ask_size=yes.contracts,
            no_ask_size=no.contracts,
            exposure_window=window,
            notional_value=self.notional_value,
        )


def event_window(ticker: str, frequency: str) -> ContractWindow | None:
    """Derive the period a market's event covers from its ticker and series frequency.

    The date segment of a ticker is the event date, which is the only reliable
    source: `close_time` is in UTC and rolls past the local event date
    (`KXHIGHNY-26OCT11-T62` closes `2026-10-12T05:00Z`), while `open_time` is when
    trading opened, not when the measured period began.

    Month-only segments (`KXB200MS-27APR-12.000`) cover that whole calendar month.
    Day-precise segments span the frequency's nominal length ending on that day -
    checked against `KXB200MON-26AUG31`, whose live `open_time` was 2026-08-02,
    exactly the 30-day window this produces.
    """
    settles = _event_date(ticker)
    if settles is None:
        return None

    if _is_month_only(ticker):
        last_day = calendar.monthrange(settles.year, settles.month)[1]
        return ContractWindow(
            opens=settles.replace(day=1), settles=settles.replace(day=last_day)
        )

    days = NOMINAL_WINDOW_DAYS.get(frequency)
    if days is None:
        return None
    return ContractWindow(opens=settles - timedelta(days=days - 1), settles=settles)


def _event_date(ticker: str) -> date | None:
    segments = ticker.split("-")
    if len(segments) < 2:
        return None
    return _parse_ticker_date(segments[1])


def _is_month_only(ticker: str) -> bool:
    segments = ticker.split("-")
    return len(segments) >= 2 and len(segments[1]) == 5


def _parse_ticker_date(segment: str) -> date | None:
    """`26OCT11` -> 2026-10-11, `27APR` -> 2027-04-01 (day filled in by the caller)."""
    if len(segment) not in (5, 7):
        return None
    year, month, day = segment[:2], segment[2:5].upper(), segment[5:]
    if not year.isdigit() or month not in _MONTHS or (day and not day.isdigit()):
        return None
    try:
        return date(2000 + int(year), _MONTHS[month], int(day) if day else 1)
    except ValueError:
        return None


def _levels(raw: list | None) -> tuple[PriceLevel, ...]:
    """Ladders arrive as [price, size] string pairs, ascending by price, or null."""
    return tuple(
        PriceLevel(price=_dollars(price), contracts=_contracts(size)) for price, size in (raw or [])
    )


def _dollars(value: str | None) -> Decimal:
    """Prices are dollar strings; a missing one becomes zero so validation can reject it."""
    return Decimal(value) if value not in (None, "") else Decimal("0")


def _contracts(value: str | None) -> int:
    """`*_fp` sizes are decimal strings and can be fractional; a partial contract is unbuyable."""
    if value in (None, ""):
        return 0
    return int(Decimal(value).to_integral_value(rounding=ROUND_FLOOR))


def _timestamp(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None
