import time

import httpx
import pytest

from app.market_catalog import FALLBACK_MARKETS, MARKET_FAMILIES, SERIES, family_of, load_candidate_markets, match_city, series_for

ALL_SERIES = [series.ticker for series in SERIES]


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def _one_market_per_series(request: httpx.Request) -> httpx.Response:
    series = request.url.params["series_ticker"]
    return httpx.Response(200, json={"markets": [{"ticker": f"{series}-X", "title": series, "yes_sub_title": "", "yes_ask_dollars": "0.5000"}]})


def test_market_families_end_with_none():
    assert MARKET_FAMILIES == ("rain", "heat", "gas", "oil", "inflation", "food_prices", "interest_rates", "jobs", "economy", "none")


def test_every_series_has_a_known_family():
    assert all(series.family in MARKET_FAMILIES and series.family != "none" for series in SERIES)


def test_only_weather_series_are_tied_to_a_city():
    assert all((series.city is not None) == (series.family in ("rain", "heat")) for series in SERIES)


@pytest.mark.parametrize(
    ("location", "city"),
    [
        ("Austin, TX", "austin"),
        ("Brooklyn, NY", "nyc"),
        ("New York City", "nyc"),
        ("LA", "los_angeles"),
        ("Downtown Los Angeles", "los_angeles"),
        ("SF Bay Area", "san_francisco"),
        ("Atlanta, GA", None),
        ("Denver, CO", None),
        ("", None),
        ("Miami, but we ship to Seattle", "miami"),
        ("Shreveport, LA", None),
        ("New Orleans, LA", None),
        ("La Jolla, CA", None),
        ("Calle de la Paz, Austin TX", "austin"),
        ("Downtown LA", "los_angeles"),
    ],
)
def test_match_city(location, city):
    assert match_city(location) == city


def test_series_for_limits_weather_to_the_city():
    assert series_for({"rain", "gas"}, "austin") == ["KXRAINAUSM", "KXAAAGASM"]


def test_series_for_drops_weather_without_a_city():
    assert series_for({"rain", "heat"}, None) == []


def test_series_for_includes_every_series_of_a_national_family():
    assert series_for({"interest_rates"}, None) == ["KXFED", "KXFEDDECISION"]


def test_series_for_none_family_is_empty():
    assert series_for({"none"}, "austin") == []


def test_family_of_ticker():
    assert family_of("KXRAINAUSM-26OCT-4") == "rain"
    assert family_of("KXFEDDECISION-28JAN-H25") == "interest_rates"
    assert family_of("BOGUS-1") is None


def test_load_candidates_fetches_only_requested_series():
    requested = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.params["series_ticker"])
        return _one_market_per_series(request)

    markets = load_candidate_markets(["KXRAINAUSM", "KXCPI"], _client(handler))

    assert sorted(requested) == ["KXCPI", "KXRAINAUSM"]
    assert [market.ticker for market in markets] == ["KXRAINAUSM-X", "KXCPI-X"]


def test_load_candidates_without_series_makes_no_calls():
    assert load_candidate_markets([], _client(lambda request: pytest.fail("no request expected"))) == []


def test_load_candidates_skips_failing_series():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["series_ticker"] == "KXRAINAUSM":
            return httpx.Response(500, text="boom")
        return _one_market_per_series(request)

    markets = load_candidate_markets(ALL_SERIES, _client(handler))

    assert len(markets) == len(ALL_SERIES) - 1
    assert "KXRAINAUSM-X" not in {market.ticker for market in markets}


def test_load_candidates_falls_back_to_requested_series_when_all_fail():
    markets = load_candidate_markets(["KXRAINAUSM", "KXCPI"], _client(lambda request: httpx.Response(503)))

    assert sorted(market.ticker.split("-")[0] for market in markets) == ["KXCPI", "KXRAINAUSM"]


def test_load_candidates_falls_back_when_kalshi_has_no_markets():
    assert load_candidate_markets(ALL_SERIES, _client(lambda request: httpx.Response(200, json={"markets": []}))) == FALLBACK_MARKETS


def test_load_candidates_returns_by_deadline_when_a_series_hangs():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["series_ticker"] == "KXRAINAUSM":
            time.sleep(2)
        return _one_market_per_series(request)

    started = time.monotonic()
    markets = load_candidate_markets(ALL_SERIES, _client(handler), deadline_seconds=0.5)

    assert time.monotonic() - started < 1.5
    assert len(markets) == len(ALL_SERIES) - 1


def test_fallback_has_one_market_per_series():
    assert sorted(market.ticker.split("-")[0] for market in FALLBACK_MARKETS) == sorted(ALL_SERIES)


def test_fallback_prices_are_tradeable():
    assert all(0.03 <= market.yes_price <= 0.97 for market in FALLBACK_MARKETS)
