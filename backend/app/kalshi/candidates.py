"""Assembling the tradeable markets a model gets to choose between.

Relevance scoring ranks *series*; the model has to choose a *market*, which
means a specific strike with a real price and a real book behind it. This walks
from one to the other and throws away everything that cannot actually be traded.

The filtering is the point. Live, 171 of 190 active `KXB200MS` markets have no
reachable offer at all, and depth concentrates heavily in the nearest-settling
contracts. A model shown the unfiltered list will confidently pick a topically
perfect market with an empty book, which then sizes to nothing while every
number still looks reasonable.

One side offered is enough. Kalshi quotes out-of-the-money strikes on a single
side as a matter of course - `KXHIGHAUS-26OCT10-T91` had 66,321 contracts on
YES and nothing on NO - so demanding both discards most of the real depth in
the weather markets. When the factor's direction is already known, pass
`required_side` and only markets tradeable on that side are returned.

Ranking knows nothing about tradeability, so `series_limit` has to be generous:
for "Gasoline Prices" the four best-scoring series had no active markets at all
while the live `AAAGAS*` ones ranked below them. Checking a series costs one
cheap market listing, and orderbooks are only fetched for markets that pass.

Each orderbook is one HTTP request, so the scan is bounded by `series_limit`
and `markets_per_series` rather than walking the whole catalogue. Kalshi has a
batch orderbook endpoint that would collapse these into one call per series -
worth moving to if the demo needs the latency back.
"""

from collections.abc import Mapping, Sequence
from datetime import date

from app.hedge.sizing import Side
from app.kalshi.client import KalshiClient
from app.kalshi.models import Series, event_window
from app.kalshi.search import EXPANSIONS, rank_series
from app.model.selection import MarketOption

DEFAULT_SERIES_LIMIT = 10
DEFAULT_MARKETS_PER_SERIES = 6
DEFAULT_OPTION_LIMIT = 12


def find_options(api: KalshiClient, factor: str, catalogue: Sequence[Series], *, expansions: Mapping[str, Sequence[str]] = EXPANSIONS, as_of: date | None = None, required_side: Side | None = None, series_limit: int = DEFAULT_SERIES_LIMIT, markets_per_series: int = DEFAULT_MARKETS_PER_SERIES, limit: int = DEFAULT_OPTION_LIMIT) -> list[MarketOption]:
    """Tradeable markets related to `factor`, nearest settlement first."""
    today = as_of or date.today()
    options: list[MarketOption] = []

    for candidate in rank_series(factor, catalogue, limit=series_limit, expansions=expansions):
        for market in _nearest_markets(api, candidate.series, today, markets_per_series):
            window = event_window(market.ticker, candidate.series.frequency)
            quote = api.get_orderbook(market.ticker).to_quote(window)
            if not _is_tradeable(quote, required_side):
                continue

            options.append(
                MarketOption(
                    series_ticker=candidate.series.ticker,
                    series_title=candidate.series.title,
                    frequency=candidate.series.frequency,
                    market=market,
                    quote=quote,
                )
            )
            if len(options) >= limit:
                return options

    return options


def _is_tradeable(quote, required_side: Side | None) -> bool:
    """Depth on the side we will buy, or on either side when that is not settled yet."""
    if required_side is Side.YES:
        return quote.yes_ask_size > 0
    if required_side is Side.NO:
        return quote.no_ask_size > 0
    return quote.yes_ask_size > 0 or quote.no_ask_size > 0


def _nearest_markets(api: KalshiClient, series: Series, as_of: date, count: int):
    """Markets whose window still has exposure left, soonest-settling first.

    Sorted before the book is fetched so the bounded number of orderbook requests
    is spent on the contracts most likely to have depth.
    """
    hedgeable = []
    for market in api.list_markets(series_ticker=series.ticker, tradeable_only=True):
        window = event_window(market.ticker, series.frequency)
        if window is None or window.remaining_days(as_of) == 0:
            continue
        hedgeable.append((window.settles, market))

    hedgeable.sort(key=lambda pair: pair[0])
    return [market for _, market in hedgeable[:count]]
