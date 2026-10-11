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


def test_fetch_keeps_cheap_tails_and_drops_near_certain_ones():
    """A 1c contract is 100:1 tail insurance and must survive; a 99c one transfers
    almost no risk however much is spent on it."""
    markets = fetch_open_markets("KXRAINAUSM", _respond_with([_market("A", "0.0100"), _market("B", "0.9900"), _market("C", "0.0300"), _market("D", "0.9700")]))

    assert [market.ticker for market in markets] == ["A", "C", "D"]


def test_fetch_drops_a_zero_price_market():
    """Nothing is offered at zero, so there is nothing to buy."""
    assert fetch_open_markets("KXRAINAUSM", _respond_with([_market("A", "0.0000")])) == []


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


def test_fetch_strips_markdown_emphasis_from_titles():
    markets = fetch_open_markets("KXAAAGASM", _respond_with([_market("G", title="Will average **gas prices** be above $4.50?", yes_sub_title="Above *4.50*")]))

    assert (markets[0].title, markets[0].subtitle) == ("Will average gas prices be above $4.50?", "Above 4.50")


def test_fetch_skips_market_with_non_text_title():
    assert fetch_open_markets("KXRAINAUSM", _respond_with([_market("BAD", title=None), _market("OK")]))[0].ticker == "OK"


class TestPriceForSide:
    """`1 - yes_ask` is the NO *bid* - what a seller receives - not what a buyer
    pays. Inferring it ignored the spread: KXRAINAUSM-26OCT-4 quotes yes_ask 0.50
    against a real no_ask of 0.67, and the November contract 0.60 against 0.98."""

    @staticmethod
    def _market(yes: float, no: float) -> KalshiMarket:
        return KalshiMarket("KXRAINAUSM-26OCT-4", "Rain?", "", yes, no_price=no)

    def test_the_yes_side_costs_the_yes_ask(self):
        assert self._market(0.50, 0.67).price_for("YES") == 0.50

    def test_the_no_side_costs_the_quoted_no_ask(self):
        assert self._market(0.50, 0.67).price_for("NO") == 0.67

    def test_it_does_not_mirror_the_yes_price(self):
        market = self._market(0.60, 0.98)

        assert market.price_for("NO") != 1 - market.yes_price
        assert market.price_for("NO") == 0.98

    def test_an_unquoted_no_side_has_no_price(self):
        """So it can be refused rather than silently costed from the other side."""
        assert self._market(0.50, 0.0).price_for("NO") == 0.0


def test_fetch_reads_both_asks():
    market = _market("KXRAINAUSM-26OCT-4", "0.5000")
    market["no_ask_dollars"] = "0.6700"

    parsed = fetch_open_markets("KXRAINAUSM", _respond_with([market]))[0]

    assert (parsed.yes_price, parsed.no_price) == (0.5, 0.67)
