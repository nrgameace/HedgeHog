import os
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

load_dotenv()

KALSHI_API_BASE_URL = os.environ.get("KALSHI_API_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2")
MIN_TRADEABLE_PRICE = 0.03
MAX_TRADEABLE_PRICE = 0.97
MAX_MARKETS_PER_SERIES = 5


@dataclass
class KalshiMarket:
    ticker: str
    title: str
    subtitle: str
    yes_price: float


class KalshiApiError(Exception):
    pass


def _plain_text(text: str) -> str:
    return text.replace("*", "").strip()


def _parse_market(item: object) -> KalshiMarket | None:
    if not isinstance(item, dict):
        return None
    try:
        title, subtitle = _plain_text(item["title"]), _plain_text(item.get("yes_sub_title") or "")
        market = KalshiMarket(ticker=item["ticker"], title=title, subtitle=subtitle, yes_price=float(item["yes_ask_dollars"]))
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return market if MIN_TRADEABLE_PRICE <= market.yes_price <= MAX_TRADEABLE_PRICE else None


def _get_markets_payload(series_ticker: str, client: httpx.Client) -> list:
    params = {"series_ticker": series_ticker, "status": "open", "limit": 20}
    try:
        response = client.get(f"{KALSHI_API_BASE_URL}/markets", params=params)
    except httpx.HTTPError as exc:
        raise KalshiApiError(f"request to Kalshi failed for {series_ticker}: {exc}") from exc
    if response.status_code != 200:
        raise KalshiApiError(f"Kalshi returned {response.status_code} for {series_ticker}")
    try:
        markets = response.json().get("markets")
    except (ValueError, AttributeError) as exc:
        raise KalshiApiError(f"Kalshi returned an unexpected body for {series_ticker}") from exc
    return markets if isinstance(markets, list) else []


def fetch_open_markets(series_ticker: str, client: httpx.Client) -> list[KalshiMarket]:
    parsed = [_parse_market(item) for item in _get_markets_payload(series_ticker, client)]
    return [market for market in parsed if market is not None][:MAX_MARKETS_PER_SERIES]
