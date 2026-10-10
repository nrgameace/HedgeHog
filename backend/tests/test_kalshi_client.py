import httpx
import pytest

from app.kalshi_client import KalshiApiError, KalshiMarket, fetch_open_markets


def _market(ticker: str, price: str = "0.2000", **overrides) -> dict:
    market = {"ticker": ticker, "title": "Rain in Austin in Oct 2026?", "yes_sub_title": "Above 4 inches", "yes_ask_dollars": price}
    market.update(overrides)
    return market


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _respond_with(markets: list[dict]):
    return _client(lambda request: httpx.Response(200, json={"markets": markets}))


def test_fetch_open_markets_maps_fields():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"], seen["params"] = request.url.path, dict(request.url.params)
        return httpx.Response(200, json={"markets": [_market("KXRAINAUSM-26OCT-4"), _market("KXRAINAUSM-26OCT-6", "0.0600", yes_sub_title="Above 6 inches")]})

    markets = fetch_open_markets("KXRAINAUSM", _client(handler))

    assert seen["path"].endswith("/markets")
    assert seen["params"] == {"series_ticker": "KXRAINAUSM", "status": "open", "limit": "20"}
    assert markets == [
        KalshiMarket(ticker="KXRAINAUSM-26OCT-4", title="Rain in Austin in Oct 2026?", subtitle="Above 4 inches", yes_price=0.2),
        KalshiMarket(ticker="KXRAINAUSM-26OCT-6", title="Rain in Austin in Oct 2026?", subtitle="Above 6 inches", yes_price=0.06),
    ]


def test_fetch_defaults_missing_subtitle_to_empty():
    market = _market("KXCPI-26OCT-T0.3")
    del market["yes_sub_title"]

    assert fetch_open_markets("KXCPI", _respond_with([market]))[0].subtitle == ""


def test_fetch_filters_extreme_prices():
    markets = fetch_open_markets("KXRAINAUSM", _respond_with([_market("A", "0.0100"), _market("B", "0.9900"), _market("C", "0.0300"), _market("D", "0.9700")]))

    assert [market.ticker for market in markets] == ["C", "D"]


def test_fetch_caps_at_five_per_series():
    markets = fetch_open_markets("KXRAINAUSM", _respond_with([_market(f"M{index}") for index in range(8)]))

    assert len(markets) == 5


def test_fetch_skips_market_missing_price():
    market = _market("NOPRICE")
    del market["yes_ask_dollars"]

    assert fetch_open_markets("KXRAINAUSM", _respond_with([market, _market("OK")])) == [KalshiMarket("OK", "Rain in Austin in Oct 2026?", "Above 4 inches", 0.2)]


def test_fetch_raises_on_500():
    with pytest.raises(KalshiApiError):
        fetch_open_markets("KXRAINAUSM", _client(lambda request: httpx.Response(500, text="boom")))


def test_fetch_raises_on_non_json_body():
    with pytest.raises(KalshiApiError):
        fetch_open_markets("KXRAINAUSM", _client(lambda request: httpx.Response(200, text="<html>")))


def test_fetch_raises_on_transport_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timed out")

    with pytest.raises(KalshiApiError):
        fetch_open_markets("KXRAINAUSM", _client(handler))
