"""HTTP client for Kalshi's market-data endpoints.

Market data is public: `GET /markets` returns 200 with no credentials (verified
live, 2026-10-10), so nothing here signs requests. Order placement would need
`KALSHI-ACCESS-KEY` / `-TIMESTAMP` / `-SIGNATURE`, but the demo places no
orders, so that machinery is deliberately absent rather than written unused.

Retrieval starts from `GET /series`, not by paging `GET /markets`. Unfiltered
`/markets` is almost entirely sports and 15-minute crypto - 6,000 markets deep
it had still returned zero weather or compute results - while `/series` exposes
`categories` for narrowing and `frequency` for the contract horizon.

The client is synchronous. FastAPI runs plain `def` handlers in a threadpool, so
this will not block the event loop, and a sync client keeps the retrieval code
and its tests straightforward.
"""

from types import TracebackType

import httpx

from app.kalshi.models import Market, OrderBook, Series, event_window
from app.hedge.sizing import MarketQuote

PRODUCTION_BASE_URL = "https://external-api.kalshi.com/trade-api/v2"
DEMO_BASE_URL = "https://external-api.demo.kalshi.co/trade-api/v2"

DEFAULT_TIMEOUT_SECONDS = 10.0
MARKETS_PAGE_SIZE = 1000
DEFAULT_MAX_PAGES = 20


class KalshiError(RuntimeError):
    """Any failure talking to Kalshi: transport, non-2xx status, or unparseable body."""


class KalshiClient:
    def __init__(self, base_url: str = PRODUCTION_BASE_URL, transport: httpx.BaseTransport | None = None, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> None:
        self.base_url = base_url
        self._http = httpx.Client(base_url=base_url, transport=transport, timeout=timeout)

    def __enter__(self) -> "KalshiClient":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def list_series(self, category: str | None = None, business_only: bool = False) -> list[Series]:
        """Every series, optionally narrowed to one Kalshi category or to hedgeable ones."""
        params = {"category": category} if category else {}
        payload = self._get("/series", params)
        series = [Series.from_api(entry) for entry in payload.get("series") or []]

        if business_only:
            series = [s for s in series if s.is_business_relevant and not s.is_test_series]
        return series

    def list_markets(self, series_ticker: str | None = None, tradeable_only: bool = False, max_pages: int = DEFAULT_MAX_PAGES) -> list[Market]:
        """Markets for one series, or all of them, following the pagination cursor."""
        params: dict[str, object] = {"limit": MARKETS_PAGE_SIZE, "mve_filter": "exclude"}
        if series_ticker:
            params["series_ticker"] = series_ticker

        markets: list[Market] = []
        cursor = ""
        for _ in range(max_pages):
            page = self._get("/markets", {**params, **({"cursor": cursor} if cursor else {})})
            markets.extend(Market.from_api(entry) for entry in page.get("markets") or [])
            cursor = page.get("cursor") or ""
            if not cursor:
                break

        if tradeable_only:
            markets = [market for market in markets if market.is_tradeable]
        return markets

    def get_orderbook(self, ticker: str) -> OrderBook:
        return OrderBook.from_api(ticker, self._get(f"/markets/{ticker}/orderbook", {}))

    def quotes_for_series(self, series: Series, limit_price=None) -> list[MarketQuote]:
        """Tradeable markets in a series, quoted at real book depth against their own window.

        Markets whose window cannot be derived are dropped: without a horizon the
        revenue shortfall cannot be period-matched, and guessing one would mis-size
        the hedge while leaving every intermediate step looking consistent.
        """
        quotes = []
        for market in self.list_markets(series_ticker=series.ticker, tradeable_only=True):
            window = event_window(market.ticker, series.frequency)
            if window is None:
                continue
            quotes.append(self.get_orderbook(market.ticker).to_quote(window, limit_price))
        return quotes

    def _get(self, path: str, params: dict) -> dict:
        try:
            response = self._http.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            raise KalshiError(
                f"GET {path} failed with {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise KalshiError(f"GET {path} failed: {exc}") from exc
        except ValueError as exc:
            raise KalshiError(f"GET {path} returned a body that is not JSON: {exc}") from exc
