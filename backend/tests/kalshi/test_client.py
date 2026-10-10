import httpx
import pytest

from app.kalshi.client import DEMO_BASE_URL, PRODUCTION_BASE_URL, KalshiClient, KalshiError
from app.kalshi.models import Series


def stub(routes: dict[str, dict], recorder: list[httpx.Request] | None = None) -> httpx.MockTransport:
    """Serve canned JSON per path, recording requests so query params can be asserted."""

    def handler(request: httpx.Request) -> httpx.Response:
        if recorder is not None:
            recorder.append(request)
        body = routes.get(request.url.path)
        if body is None:
            return httpx.Response(404, json={"error": f"no stub for {request.url.path}"})
        return httpx.Response(200, json=body)

    return httpx.MockTransport(handler)


def client(routes: dict[str, dict], recorder: list[httpx.Request] | None = None) -> KalshiClient:
    return KalshiClient(transport=stub(routes, recorder))


SERIES_BODY = {
    "series": [
        {
            "ticker": "KXHIGHNY",
            "title": "Highest temperature in NYC",
            "frequency": "daily",
            "categories": ["Climate and Weather"],
        },
        {
            "ticker": "KXNHLGOAL",
            "title": "NHL goals",
            "frequency": "daily",
            "categories": ["Sports"],
        },
        {
            "ticker": "KXTESTB200",
            "title": "Weekly B200 Compute Price",
            "frequency": "weekly",
            "categories": ["Science and Technology"],
        },
    ]
}

MARKET = {
    "ticker": "KXHIGHNY-26OCT11-T62",
    "event_ticker": "KXHIGHNY-26OCT11",
    "title": "Will the maximum temperature be <62° on Oct 11, 2026?",
    "status": "active",
    "close_time": "2026-10-12T05:00:00Z",
    "yes_ask_dollars": "0.6400",
    "no_ask_dollars": "0.3700",
    "yes_ask_size_fp": "11.00",
    "no_ask_size_fp": "32.00",
    "notional_value_dollars": "1.0000",
}


def test_defaults_to_the_production_base_url():
    assert KalshiClient().base_url == PRODUCTION_BASE_URL
    assert KalshiClient(base_url=DEMO_BASE_URL).base_url == DEMO_BASE_URL


def test_sends_no_credentials_because_market_data_is_public():
    """Verified live: GET /markets returns 200 unauthenticated, so the demo needs no keys."""
    seen: list[httpx.Request] = []
    client({"/trade-api/v2/series": SERIES_BODY}, seen).list_series()

    assert not any(h.lower().startswith("kalshi-access") for h in seen[0].headers)


def test_list_series_parses_every_entry():
    assert len(client({"/trade-api/v2/series": SERIES_BODY}).list_series()) == 3


def test_list_series_can_drop_sports_and_test_series():
    relevant = client({"/trade-api/v2/series": SERIES_BODY}).list_series(business_only=True)

    assert [s.ticker for s in relevant] == ["KXHIGHNY"]


def test_list_series_passes_a_category_filter_through():
    seen: list[httpx.Request] = []
    client({"/trade-api/v2/series": SERIES_BODY}, seen).list_series(category="Economics")

    assert seen[0].url.params["category"] == "Economics"


def test_list_markets_filters_to_one_series():
    seen: list[httpx.Request] = []
    routes = {"/trade-api/v2/markets": {"markets": [MARKET], "cursor": ""}}

    markets = client(routes, seen).list_markets(series_ticker="KXHIGHNY")

    assert [m.ticker for m in markets] == ["KXHIGHNY-26OCT11-T62"]
    assert seen[0].url.params["series_ticker"] == "KXHIGHNY"


def test_list_markets_excludes_multivariate_combo_markets():
    """KXMVE* combos have degenerate books and are not single-factor events."""
    seen: list[httpx.Request] = []
    routes = {"/trade-api/v2/markets": {"markets": [], "cursor": ""}}

    client(routes, seen).list_markets(series_ticker="KXHIGHNY")

    assert seen[0].url.params["mve_filter"] == "exclude"


def test_list_markets_can_keep_only_tradeable_markets():
    routes = {
        "/trade-api/v2/markets": {
            "markets": [MARKET, {**MARKET, "ticker": "DEAD", "status": "finalized"}],
            "cursor": "",
        }
    }

    markets = client(routes).list_markets(series_ticker="KXHIGHNY", tradeable_only=True)

    assert [m.ticker for m in markets] == ["KXHIGHNY-26OCT11-T62"]


def test_list_markets_follows_the_pagination_cursor():
    pages = [
        {"markets": [MARKET], "cursor": "page2"},
        {"markets": [{**MARKET, "ticker": "SECOND"}], "cursor": ""},
    ]
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=pages[len(seen) - 1])

    markets = KalshiClient(transport=httpx.MockTransport(handler)).list_markets()

    assert [m.ticker for m in markets] == ["KXHIGHNY-26OCT11-T62", "SECOND"]
    assert "cursor" not in seen[0].url.params
    assert seen[1].url.params["cursor"] == "page2"


def test_pagination_stops_at_the_page_limit_rather_than_looping_forever():
    """A cursor that never empties would otherwise page until the process dies."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"markets": [MARKET], "cursor": "always-more"})

    markets = KalshiClient(transport=httpx.MockTransport(handler)).list_markets(max_pages=3)

    assert len(seen) == 3
    assert len(markets) == 3


def test_get_orderbook_parses_both_ladders():
    routes = {
        "/trade-api/v2/markets/KXHIGHNY-26OCT11-T62/orderbook": {
            "orderbook_fp": {
                "no_dollars": [["0.3500", "130.00"], ["0.3600", "11.00"]],
                "yes_dollars": [["0.6300", "32.00"]],
            }
        }
    }

    book = client(routes).get_orderbook("KXHIGHNY-26OCT11-T62")

    assert book.ticker == "KXHIGHNY-26OCT11-T62"
    assert len(book.no_bids) == 2
    assert len(book.yes_bids) == 1


def test_an_empty_orderbook_parses_rather_than_crashing():
    """Live illiquid markets return null ladders."""
    routes = {
        "/trade-api/v2/markets/T/orderbook": {
            "orderbook_fp": {"no_dollars": None, "yes_dollars": None}
        }
    }

    book = client(routes).get_orderbook("T")

    assert book.no_bids == ()
    assert book.yes_bids == ()


def test_http_errors_surface_as_kalshi_errors():
    transport = httpx.MockTransport(lambda request: httpx.Response(500, text="upstream exploded"))

    with pytest.raises(KalshiError, match="500"):
        KalshiClient(transport=transport).list_series()


def test_malformed_json_surfaces_as_a_kalshi_error():
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b"<html>not json</html>")
    )

    with pytest.raises(KalshiError):
        KalshiClient(transport=transport).list_series()


def test_works_as_a_context_manager():
    with KalshiClient(transport=stub({"/trade-api/v2/series": SERIES_BODY})) as api:
        assert api.list_series()


def test_quotes_for_a_series_pair_each_market_with_its_window():
    """The series frequency supplies the horizon the sizing math needs."""
    routes = {
        "/trade-api/v2/markets": {"markets": [MARKET], "cursor": ""},
        "/trade-api/v2/markets/KXHIGHNY-26OCT11-T62/orderbook": {
            "orderbook_fp": {"no_dollars": [["0.3600", "11.00"]], "yes_dollars": []}
        },
    }
    series = Series.from_api(SERIES_BODY["series"][0])

    quotes = client(routes).quotes_for_series(series)

    assert len(quotes) == 1
    assert quotes[0].exposure_window.days == 1
    assert quotes[0].yes_ask_size == 11


def test_quotes_for_a_series_skip_markets_with_no_derivable_window():
    """A custom-frequency series has no horizon, so its markets cannot be period-matched."""
    routes = {"/trade-api/v2/markets": {"markets": [MARKET], "cursor": ""}}
    series = Series.from_api({**SERIES_BODY["series"][0], "frequency": "custom"})

    assert client(routes).quotes_for_series(series) == []
