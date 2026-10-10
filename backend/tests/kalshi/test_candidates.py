from datetime import date

import httpx
import pytest

from app.kalshi.candidates import find_options
from app.hedge.sizing import Side
from app.kalshi.client import KalshiClient
from app.kalshi.models import Series

AS_OF = date(2026, 10, 10)

SERIES = [
    {
        "ticker": "KXLOWTATL",
        "title": "Low Temperature Atlanta",
        "frequency": "daily",
        "categories": ["Climate and Weather"],
    },
    {
        "ticker": "KXNHLGOAL",
        "title": "NHL temperature goals",
        "frequency": "daily",
        "categories": ["Sports"],
    },
]
CATALOGUE = tuple(Series.from_api(payload) for payload in SERIES)


def market(ticker: str, *, settles: str, status: str = "active") -> dict:
    return {
        "ticker": ticker,
        "event_ticker": ticker.rsplit("-", 1)[0],
        "title": f"Will the minimum temperature be <56 on {settles}?",
        "status": status,
        "strike_type": "less",
        "close_time": f"{settles}T05:00:00Z",
        "yes_ask_dollars": "0.2500",
        "no_ask_dollars": "0.7600",
        "yes_ask_size_fp": "5000.00",
        "no_ask_size_fp": "5000.00",
        "notional_value_dollars": "1.0000",
    }


def book(yes: list | None = None, no: list | None = None) -> dict:
    return {"orderbook_fp": {"yes_dollars": yes, "no_dollars": no}}


FULL_BOOK = book(yes=[["0.2400", "5000.00"]], no=[["0.7500", "5000.00"]])
# Each ladder holds *bids*, and an ask on one side is a bid on the other, so a
# book carrying only yes_dollars is a market offered on the NO side alone.
ONLY_NO_OFFERED = book(yes=[["0.2400", "5000.00"]], no=None)
ONLY_YES_OFFERED = book(yes=None, no=[["0.7500", "5000.00"]])
EMPTY = book(yes=None, no=None)


def api(markets: list[dict], books: dict[str, dict], recorder: list[str] | None = None) -> KalshiClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if recorder is not None:
            recorder.append(str(request.url))
        if path.endswith("/markets"):
            # Honour the series filter, as the real endpoint does, so a market
            # cannot appear under a series that was never queried.
            wanted = request.url.params.get("series_ticker")
            matching = [m for m in markets if not wanted or m["ticker"].startswith(wanted)]
            return httpx.Response(200, json={"markets": matching, "cursor": ""})
        if path.endswith("/orderbook"):
            ticker = path.split("/markets/")[1].rsplit("/", 1)[0]
            return httpx.Response(200, json=books.get(ticker, EMPTY))
        return httpx.Response(404, json={"error": path})

    return KalshiClient(transport=httpx.MockTransport(handler))


def options(markets, books, **kwargs):
    return find_options(
        api(markets, books), "cold weather", CATALOGUE, as_of=AS_OF, **kwargs
    )


def test_returns_a_tradeable_market_with_its_window_and_series_context():
    found = options([market("KXLOWTATL-26OCT11-T56", settles="2026-10-11")], {"KXLOWTATL-26OCT11-T56": FULL_BOOK})

    assert len(found) == 1
    assert found[0].market.ticker == "KXLOWTATL-26OCT11-T56"
    assert found[0].series_ticker == "KXLOWTATL"
    assert found[0].frequency == "daily"
    assert found[0].quote.exposure_window.settles == date(2026, 10, 11)
    assert found[0].quote.yes_ask_size == 5000


def test_skips_markets_with_no_reachable_offer():
    """171 of 190 live KXB200MS markets have no book; the model must not be shown them."""
    markets = [market("KXLOWTATL-26OCT11-T56", settles="2026-10-11")]

    assert options(markets, {"KXLOWTATL-26OCT11-T56": EMPTY}) == []


@pytest.mark.parametrize("one_sided", [ONLY_YES_OFFERED, ONLY_NO_OFFERED])
def test_keeps_markets_offered_on_only_one_side(one_sided):
    """Kalshi quotes out-of-the-money strikes one-sided; KXHIGHAUS-26OCT10-T91 had
    66,321 contracts on YES and nothing on NO, so requiring both loses real depth."""
    markets = [market("KXLOWTATL-26OCT11-T56", settles="2026-10-11")]

    found = options(markets, {"KXLOWTATL-26OCT11-T56": one_sided})

    assert [o.market.ticker for o in found] == ["KXLOWTATL-26OCT11-T56"]
    assert min(found[0].quote.yes_ask_size, found[0].quote.no_ask_size) == 0


def test_a_required_side_filters_out_markets_without_depth_on_it():
    """Once the factor's direction is known, only one side is actually buyable."""
    markets = [market("KXLOWTATL-26OCT11-T56", settles="2026-10-11")]
    yes_only = {"KXLOWTATL-26OCT11-T56": ONLY_YES_OFFERED}

    assert options(markets, yes_only, required_side=Side.YES) != []
    assert options(markets, yes_only, required_side=Side.NO) == []


def test_scans_past_highly_ranked_series_that_have_no_active_markets():
    """Live, the four best-scoring gasoline series had no markets while AAAGAS* did."""
    markets = [market("KXLOWTATL-26OCT11-T56", settles="2026-10-11")]
    seen: list[str] = []

    find_options(api(markets, {"KXLOWTATL-26OCT11-T56": FULL_BOOK}, seen), "cold weather", CATALOGUE, as_of=AS_OF)

    assert any("KXLOWTATL-26OCT11-T56/orderbook" in path for path in seen)


def test_skips_markets_whose_window_has_already_elapsed():
    markets = [market("KXLOWTATL-26OCT01-T56", settles="2026-10-01")]

    assert options(markets, {"KXLOWTATL-26OCT01-T56": FULL_BOOK}) == []


def test_skips_untradeable_markets_without_fetching_their_book():
    seen: list[str] = []
    markets = [market("KXLOWTATL-26OCT11-T56", settles="2026-10-11", status="finalized")]

    find_options(api(markets, {}, seen), "cold weather", CATALOGUE, as_of=AS_OF)

    assert not any("orderbook" in path for path in seen)


def test_excludes_series_the_relevance_filter_rejects():
    """The sports series mentions 'temperature' but is not a business category."""
    markets = [market("KXNHLGOAL-26OCT11-T56", settles="2026-10-11")]
    seen: list[str] = []

    find_options(api(markets, {}, seen), "cold weather", CATALOGUE, as_of=AS_OF)

    assert not any("KXNHLGOAL" in path for path in seen)


def test_prefers_the_nearest_settling_markets():
    """Live depth concentrates in near-dated markets, so those are examined first."""
    markets = [
        market("KXLOWTATL-26DEC20-T56", settles="2026-12-20"),
        market("KXLOWTATL-26OCT11-T56", settles="2026-10-11"),
        market("KXLOWTATL-26NOV15-T56", settles="2026-11-15"),
    ]
    books = {m["ticker"]: FULL_BOOK for m in markets}

    found = options(markets, books, markets_per_series=2)

    assert [o.market.ticker for o in found] == [
        "KXLOWTATL-26OCT11-T56",
        "KXLOWTATL-26NOV15-T56",
    ]


def test_caps_the_number_of_options_offered_to_the_model():
    markets = [market(f"KXLOWTATL-26OCT1{i}-T56", settles=f"2026-10-1{i}") for i in range(1, 6)]
    books = {m["ticker"]: FULL_BOOK for m in markets}

    assert len(options(markets, books, limit=2)) == 2


def test_caps_how_many_books_are_fetched_per_series():
    """One HTTP call per orderbook, so the scan is bounded rather than unbounded."""
    markets = [market(f"KXLOWTATL-26OCT1{i}-T56", settles=f"2026-10-1{i}") for i in range(1, 6)]
    seen: list[str] = []

    find_options(
        api(markets, {}, seen), "cold weather", CATALOGUE, as_of=AS_OF, markets_per_series=2
    )

    assert len([p for p in seen if "orderbook" in p]) == 2


def test_a_factor_matching_nothing_yields_no_options_and_no_market_calls():
    seen: list[str] = []

    found = find_options(api([], {}, seen), "zebra giraffe", CATALOGUE, as_of=AS_OF)

    assert found == []
    assert seen == []


def test_expansions_can_be_supplied_from_a_model_proposal():
    markets = [market("KXLOWTATL-26OCT11-T56", settles="2026-10-11")]
    books = {"KXLOWTATL-26OCT11-T56": FULL_BOOK}

    found = find_options(
        api(markets, books),
        "chilly snap",
        CATALOGUE,
        as_of=AS_OF,
        expansions={"chilly": ("temperature",)},
    )

    assert [o.market.ticker for o in found] == ["KXLOWTATL-26OCT11-T56"]
