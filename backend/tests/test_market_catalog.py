import httpx

from app.market_catalog import FALLBACK_MARKETS, SERIES_TICKERS, load_candidate_markets


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _one_market_per_series(request: httpx.Request) -> httpx.Response:
    series = request.url.params["series_ticker"]
    if series == "KXRAINAUSM":
        return httpx.Response(500, text="boom")
    return httpx.Response(200, json={"markets": [{"ticker": f"{series}-X", "title": series, "yes_sub_title": "", "yes_ask_dollars": "0.5000"}]})


def test_load_candidates_skips_failing_series():
    markets = load_candidate_markets(_client(_one_market_per_series))

    assert len(markets) == len(SERIES_TICKERS) - 1
    assert "KXRAINAUSM-X" not in {market.ticker for market in markets}


def test_load_candidates_falls_back_when_all_fail():
    assert load_candidate_markets(_client(lambda request: httpx.Response(503))) == FALLBACK_MARKETS


def test_load_candidates_falls_back_when_kalshi_has_no_markets():
    assert load_candidate_markets(_client(lambda request: httpx.Response(200, json={"markets": []}))) == FALLBACK_MARKETS


def test_fallback_has_one_market_per_series():
    assert sorted(market.ticker.split("-")[0] for market in FALLBACK_MARKETS) == sorted(SERIES_TICKERS)


def test_fallback_prices_are_tradeable():
    assert all(0.03 <= market.yes_price <= 0.97 for market in FALLBACK_MARKETS)
