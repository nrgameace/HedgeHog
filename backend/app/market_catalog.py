import re
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass

import httpx

from app.kalshi_client import KalshiApiError, KalshiMarket, fetch_open_markets

KALSHI_REQUEST_TIMEOUT_SECONDS = 5.0
KALSHI_DEADLINE_SECONDS = 6.0

MARKET_FAMILIES = ("rain", "heat", "gas", "oil", "inflation", "food_prices", "interest_rates", "jobs", "economy", "none")
CITY_WEATHER_FAMILIES = {"rain", "heat"}

# How much one contract of a series covers. Taken from Kalshi's own `/series`
# frequency rather than inferred: the ticker cannot be trusted for this, since
# KXAAAGASM-26OCT31 looks day-precise but settles a monthly average, while
# KXHIGHAUS-26OCT11 really does settle one day. Anything covering a month or
# longer counts as MONTHLY; only a genuinely per-day series is DAILY.
DAILY = "daily"
MONTHLY = "monthly"


@dataclass(frozen=True)
class SeriesInfo:
    ticker: str
    family: str
    city: str | None = None
    cadence: str = MONTHLY


SERIES = (
    SeriesInfo("KXRAINAUSM", "rain", "austin"), SeriesInfo("KXRAINNYCM", "rain", "nyc"), SeriesInfo("KXRAINCHIM", "rain", "chicago"),
    SeriesInfo("KXRAINLAXM", "rain", "los_angeles"), SeriesInfo("KXRAINMIAM", "rain", "miami"), SeriesInfo("KXRAINSFOM", "rain", "san_francisco"),
    SeriesInfo("KXRAINSEAM", "rain", "seattle"),
    SeriesInfo("KXHIGHAUS", "heat", "austin", DAILY), SeriesInfo("KXHIGHNY", "heat", "nyc", DAILY), SeriesInfo("KXHIGHCHI", "heat", "chicago", DAILY),
    SeriesInfo("KXHIGHLAX", "heat", "los_angeles", DAILY), SeriesInfo("KXHIGHMIA", "heat", "miami", DAILY),
    SeriesInfo("KXAAAGASM", "gas"), SeriesInfo("KXWTI", "oil", None, DAILY), SeriesInfo("KXCPI", "inflation"), SeriesInfo("KXEGGS", "food_prices"),
    SeriesInfo("KXFED", "interest_rates"), SeriesInfo("KXFEDDECISION", "interest_rates"),
    SeriesInfo("KXU3", "jobs"), SeriesInfo("KXPAYROLLS", "jobs"), SeriesInfo("KXGDP", "economy"),
)

CITY_ALIASES = {
    "austin": ("austin",),
    "nyc": ("new york", "nyc", "manhattan", "brooklyn"),
    "chicago": ("chicago",),
    "los_angeles": ("los angeles",),
    "miami": ("miami",),
    "san_francisco": ("san francisco", "sf", "bay area"),
    "seattle": ("seattle",),
}

# "LA" only as a capitalised abbreviation, and not as a state code after a comma ("New Orleans, LA").
_LOS_ANGELES_ABBREVIATION = re.compile(r"(?<!,)(?<!,\s)\bLA\b")

_SERIES_BY_TICKER = {series.ticker: series for series in SERIES}

# MOCK DATA: used only when Kalshi's live API returns nothing, so the demo never breaks.
FALLBACK_MARKETS = [
    KalshiMarket("KXRAINAUSM-26OCT-4", "Rain in Austin in Oct 2026?", "Above 4 inches", 0.20),
    KalshiMarket("KXRAINNYCM-26OCT-4", "Rain in NYC in Oct 2026?", "Above 4 inches", 0.30),
    KalshiMarket("KXRAINCHIM-26OCT-4", "Rain in Chicago in Oct 2026?", "Above 4 inches", 0.25),
    KalshiMarket("KXRAINLAXM-26OCT-1", "Rain in Los Angeles in Oct 2026?", "Above 1 inch", 0.10),
    KalshiMarket("KXRAINMIAM-26OCT-6", "Rain in Miami in Oct 2026?", "Above 6 inches", 0.30),
    KalshiMarket("KXRAINSFOM-26OCT-1", "Rain in San Francisco in Oct 2026?", "Above 1 inch", 0.15),
    KalshiMarket("KXRAINSEAM-26OCT-4", "Rain in Seattle in Oct 2026?", "Above 4 inches", 0.35),
    KalshiMarket("KXHIGHAUS-26OCT11-T95", "Will the maximum temperature be >95° in Austin?", "96° or above", 0.10),
    KalshiMarket("KXHIGHNY-26OCT11-T80", "Will the maximum temperature be >80° in NYC?", "81° or above", 0.10),
    KalshiMarket("KXHIGHCHI-26OCT11-T80", "Will the maximum temperature be >80° in Chicago?", "81° or above", 0.10),
    KalshiMarket("KXHIGHLAX-26OCT11-T85", "Will the maximum temperature be >85° in Los Angeles?", "86° or above", 0.10),
    KalshiMarket("KXHIGHMIA-26OCT11-T92", "Will the maximum temperature be >92° in Miami?", "93° or above", 0.15),
    KalshiMarket("KXAAAGASM-26OCT31-3.50", "Will average gas prices be above $3.50?", "Above $3.50", 0.30),
    KalshiMarket("KXWTI-26OCT31-T80", "Will the WTI crude oil price be above 80 USD/Bbl?", "Above $80", 0.30),
    KalshiMarket("KXCPI-26OCT-T0.3", "Will CPI rise more than 0.3% in October 2026?", "Above 0.3%", 0.40),
    KalshiMarket("KXEGGS-OCT26-0", "Will egg prices rise by more than 0% in Oct 2026?", "Above 0%", 0.50),
    KalshiMarket("KXFED-26DEC-T4.50", "Will the upper bound of the federal funds rate be above 4.50% after the Dec 2026 meeting?", "Above 4.50%", 0.20),
    KalshiMarket("KXFEDDECISION-26DEC-H25", "Will the Federal Reserve hike rates by 25bps at their December 2026 meeting?", "Hike 25bps", 0.10),
    KalshiMarket("KXU3-26NOV-T4.5", "Will the unemployment rate (U-3) be above 4.5% in November?", "Above 4.5%", 0.35),
    KalshiMarket("KXPAYROLLS-26NOV-T90000", "Will above 90000 jobs be added in November 2026?", "Above 90,000", 0.40),
    KalshiMarket("KXGDP-27JAN-T2.0", "Will real GDP increase by more than 2.0% in Q4 2026?", "Above 2.0%", 0.45),
]


def match_city(location: str) -> str | None:
    found = []
    for city, aliases in CITY_ALIASES.items():
        for alias in aliases:
            match = re.search(rf"\b{re.escape(alias)}\b", location, re.IGNORECASE)
            if match:
                found.append((match.start(), city))
    if abbreviation := _LOS_ANGELES_ABBREVIATION.search(location):
        found.append((abbreviation.start(), "los_angeles"))
    return min(found)[1] if found else None


def series_for(families: set[str], city: str | None) -> list[str]:
    return [series.ticker for series in SERIES if series.family in families and (series.family not in CITY_WEATHER_FAMILIES or series.city == city)]


def family_of(ticker: str) -> str | None:
    series = _SERIES_BY_TICKER.get(ticker.split("-")[0])
    return series.family if series else None


def cadence_of(ticker: str) -> str:
    """How much one of this series' contracts covers. Unknown series read as monthly.

    Monthly is the safe default: it under-scales a stake rather than over-scaling
    it, risking too little cover instead of overspending on a per-day cadence
    that was never there.
    """
    series = _SERIES_BY_TICKER.get(ticker.split("-")[0])
    return series.cadence if series else MONTHLY


def _fetch_or_empty(series_ticker: str, client: httpx.Client) -> list[KalshiMarket]:
    try:
        return fetch_open_markets(series_ticker, client)
    except KalshiApiError:
        return []


def _fetch_series(series_tickers: list[str], client: httpx.Client, deadline_seconds: float) -> list[KalshiMarket]:
    executor = ThreadPoolExecutor(max_workers=len(series_tickers))
    futures = [executor.submit(_fetch_or_empty, series_ticker, client) for series_ticker in series_tickers]
    finished, _ = wait(futures, timeout=deadline_seconds)
    executor.shutdown(wait=False, cancel_futures=True)
    return [market for future in futures if future in finished for market in future.result()]


def _fallback_for(series_tickers: list[str]) -> list[KalshiMarket]:
    return [market for market in FALLBACK_MARKETS if market.ticker.split("-")[0] in series_tickers]


def load_candidate_markets(series_tickers: list[str], client: httpx.Client | None = None, deadline_seconds: float = KALSHI_DEADLINE_SECONDS) -> list[KalshiMarket]:
    if not series_tickers:
        return []
    owns_client = client is None
    client = client or httpx.Client(timeout=KALSHI_REQUEST_TIMEOUT_SECONDS)
    try:
        return _fetch_series(series_tickers, client, deadline_seconds) or _fallback_for(series_tickers)
    finally:
        if owns_client:
            client.close()
