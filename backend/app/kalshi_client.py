import os
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

load_dotenv()

KALSHI_API_BASE_URL = os.environ.get("KALSHI_API_BASE_URL", "https://api.elections.kalshi.com/trade-api/v2")
# Any positive price is tradeable. A floor of 0.03 looked like a junk filter and
# was quietly hostile to the whole product: hedging a rare bad event means buying
# a cheap contract, so the floor removed exactly the useful insurance. Every
# non-band Austin temperature tail is priced at 0.01, so after band markets were
# withheld the heat risk had no market left at all. At 0.01 a dollar of payout
# costs a cent - 100:1 protection, the best leverage on the board.
#
# The ceiling stays. Near 1.00 a contract pays back barely more than it cost, so
# it transfers almost no risk however much is spent on it.
MIN_TRADEABLE_PRICE = 0.01
MAX_TRADEABLE_PRICE = 0.97
MAX_MARKETS_PER_SERIES = 5


@dataclass
class KalshiMarket:
    ticker: str
    title: str
    subtitle: str
    yes_price: float
    # The NO ask, read from Kalshi rather than inferred. `1 - yes_ask` is the NO
    # *bid* - what a seller receives - not what a buyer pays, so inferring it
    # ignored the spread entirely: KXRAINAUSM-26OCT-4 quotes yes_ask 0.50 against
    # a real no_ask of 0.67, and the November contract 0.60 against 0.98. Every
    # NO trade was costed at roughly half its price.
    no_price: float = 0.0
    # "greater" / "less" where Kalshi gives it. Lets app.hedge_side work out which
    # side pays in the bad state instead of trusting the model's choice.
    strike_type: str = ""

    def price_for(self, side: str) -> float:
        """What a contract on this side actually costs to buy."""
        if side != "NO":
            return self.yes_price
        # A market with no quoted NO ask cannot be bought on that side; falling
        # back to the mirrored yes price would resurrect the bug this replaces.
        return self.no_price


class KalshiApiError(Exception):
    pass


def _plain_text(text: str) -> str:
    return text.replace("*", "").strip()


def _parse_market(item: object) -> KalshiMarket | None:
    if not isinstance(item, dict):
        return None
    try:
        title, subtitle = _plain_text(item["title"]), _plain_text(item.get("yes_sub_title") or "")
        market = KalshiMarket(
            ticker=item["ticker"], title=title, subtitle=subtitle,
            yes_price=float(item["yes_ask_dollars"]),
            no_price=float(item.get("no_ask_dollars") or 0.0),
            strike_type=item.get("strike_type") or "",
        )
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
