import httpx

from app.kalshi_client import KalshiApiError, KalshiMarket, fetch_open_markets

KALSHI_REQUEST_TIMEOUT_SECONDS = 5.0

SERIES_TICKERS = (
    "KXRAINAUSM", "KXRAINNYCM", "KXRAINCHIM", "KXRAINLAXM", "KXRAINMIAM", "KXRAINSFOM", "KXRAINSEAM",
    "KXHIGHAUS", "KXHIGHNY", "KXHIGHCHI", "KXHIGHLAX", "KXHIGHMIA",
    "KXAAAGASM", "KXWTI", "KXCPI", "KXEGGS", "KXFED", "KXFEDDECISION", "KXU3", "KXPAYROLLS", "KXGDP",
)

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


def _fetch_all_series(client: httpx.Client) -> list[KalshiMarket]:
    markets: list[KalshiMarket] = []
    for series_ticker in SERIES_TICKERS:
        try:
            markets.extend(fetch_open_markets(series_ticker, client))
        except KalshiApiError:
            continue
    return markets


def load_candidate_markets(client: httpx.Client | None = None) -> list[KalshiMarket]:
    owns_client = client is None
    client = client or httpx.Client(timeout=KALSHI_REQUEST_TIMEOUT_SECONDS)
    try:
        return _fetch_all_series(client) or FALLBACK_MARKETS
    finally:
        if owns_client:
            client.close()
