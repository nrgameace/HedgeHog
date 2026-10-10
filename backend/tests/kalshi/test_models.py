from datetime import date
from decimal import Decimal

import pytest

from app.hedge.sizing import ContractWindow, Side
from app.kalshi.models import Market, OrderBook, PriceLevel, Series, event_window

# Shapes copied from live production responses on 2026-10-10.
HIGHNY_PAYLOAD = {
    "ticker": "KXHIGHNY-26OCT11-T62",
    "event_ticker": "KXHIGHNY-26OCT11",
    "title": "Will the maximum temperature be <62° on Oct 11, 2026?",
    "status": "active",
    "close_time": "2026-10-12T05:00:00Z",
    "open_time": "2026-10-10T14:00:00Z",
    "yes_ask_dollars": "0.6400",
    "yes_bid_dollars": "0.6300",
    "no_ask_dollars": "0.3700",
    "no_bid_dollars": "0.3600",
    "yes_ask_size_fp": "11.00",
    "no_ask_size_fp": "32.00",
    "volume_fp": "3602.64",
    "notional_value_dollars": "1.0000",
    "market_type": "binary",
}

SERIES_PAYLOAD = {
    "ticker": "KXHIGHNY",
    "title": "Highest temperature in NYC",
    "frequency": "daily",
    "categories": ["Climate and Weather"],
}


def series(**overrides) -> Series:
    return Series.from_api({**SERIES_PAYLOAD, **overrides})


class TestSeries:
    def test_parses_the_live_payload(self):
        parsed = series()

        assert parsed.ticker == "KXHIGHNY"
        assert parsed.title == "Highest temperature in NYC"
        assert parsed.frequency == "daily"
        assert parsed.categories == ("Climate and Weather",)

    def test_tolerates_missing_categories(self):
        assert Series.from_api({"ticker": "X", "title": "t", "frequency": "daily"}).categories == ()

    @pytest.mark.parametrize(
        ("categories", "relevant"),
        [
            (["Climate and Weather"], True),
            (["Economics"], True),
            (["Commodities"], True),
            (["Science and Technology"], True),
            (["Sports"], False),
            (["Entertainment"], False),
            (["Politics"], False),
            ([], False),
        ],
    )
    def test_only_business_relevant_categories_survive_filtering(self, categories, relevant):
        assert series(categories=categories).is_business_relevant is relevant

    @pytest.mark.parametrize(
        ("ticker", "is_test"),
        [("KXTESTB200", True), ("KXB200TEST", True), ("KXB200AVGTEST", True), ("KXB200MS", False)],
    )
    def test_test_series_are_recognised(self, ticker, is_test):
        """Test series sit beside the real ones in live responses and have no book."""
        assert series(ticker=ticker).is_test_series is is_test


class TestEventWindow:
    def test_daily_ticker_covers_the_single_event_day(self):
        window = event_window("KXHIGHNY-26OCT11-T62", "daily")

        assert window == ContractWindow(opens=date(2026, 10, 11), settles=date(2026, 10, 11))

    def test_month_only_ticker_covers_the_whole_calendar_month(self):
        """KXB200MS-27APR-12.000 carries no day, and the exposure is all of April."""
        window = event_window("KXB200MS-27APR-12.000", "monthly")

        assert window == ContractWindow(opens=date(2027, 4, 1), settles=date(2027, 4, 30))

    def test_weekly_ticker_covers_the_seven_days_ending_on_the_event_date(self):
        window = event_window("KXB200W-26SEP04-6.01", "weekly")

        assert window == ContractWindow(opens=date(2026, 8, 29), settles=date(2026, 9, 4))

    def test_monthly_ticker_with_a_day_matches_the_markets_own_open_time(self):
        """KXB200MON-26AUG31 opened 2026-08-02 live, which a 30-day window reproduces."""
        window = event_window("KXB200MON-26AUG31-7.310", "monthly")

        assert window == ContractWindow(opens=date(2026, 8, 2), settles=date(2026, 8, 31))

    def test_annual_ticker_covers_the_year_ending_on_the_event_date(self):
        window = event_window("KXB200MAX-26DEC31-13.970", "annual")

        assert window == ContractWindow(opens=date(2026, 1, 1), settles=date(2026, 12, 31))
        assert window.days == 365

    @pytest.mark.parametrize("frequency", ["custom", "one_off", "unrecognised"])
    def test_unmappable_frequencies_yield_no_window(self, frequency):
        """Without a horizon the shortfall cannot be period-matched, so refuse to guess."""
        assert event_window("KXGPURULE-26DEC31-X", frequency) is None

    @pytest.mark.parametrize("ticker", ["NODATEHERE", "KX-ZZZ99-1", "KXONLYONEPART"])
    def test_tickers_without_a_parseable_date_yield_no_window(self, ticker):
        assert event_window(ticker, "daily") is None


class TestMarket:
    def test_parses_the_live_payload(self):
        market = Market.from_api(HIGHNY_PAYLOAD)

        assert market.ticker == "KXHIGHNY-26OCT11-T62"
        assert market.yes_ask == Decimal("0.6400")
        assert market.no_ask == Decimal("0.3700")
        assert market.notional_value == Decimal("1.0000")
        assert market.is_tradeable is True

    def test_fixed_point_sizes_parse_to_whole_contracts(self):
        market = Market.from_api(HIGHNY_PAYLOAD)

        assert market.yes_ask_size == 11
        assert market.no_ask_size == 32

    def test_fractional_fixed_point_sizes_floor_rather_than_round_up(self):
        market = Market.from_api({**HIGHNY_PAYLOAD, "yes_ask_size_fp": "81.61"})

        assert market.yes_ask_size == 81

    @pytest.mark.parametrize(
        ("status", "tradeable"),
        [("active", True), ("initialized", False), ("inactive", False), ("finalized", False)],
    )
    def test_only_active_markets_are_tradeable(self, status, tradeable):
        """Live statuses are initialized/active/inactive/finalized - not the documented enum."""
        assert Market.from_api({**HIGHNY_PAYLOAD, "status": status}).is_tradeable is tradeable

    def test_missing_prices_parse_to_zero_so_validation_can_reject_them(self):
        market = Market.from_api({**HIGHNY_PAYLOAD, "yes_ask_dollars": None})

        assert market.yes_ask == Decimal("0")

    def test_converts_to_a_sizing_quote(self):
        window = ContractWindow(opens=date(2026, 10, 11), settles=date(2026, 10, 11))

        quote = Market.from_api(HIGHNY_PAYLOAD).to_quote(window)

        assert quote.ticker == "KXHIGHNY-26OCT11-T62"
        assert quote.yes_ask == Decimal("0.6400")
        assert quote.yes_ask_size == 11
        assert quote.exposure_window == window
        assert quote.notional_value == Decimal("1.0000")


class TestOrderBook:
    """Kalshi publishes two bid ladders; an ask on one side is a bid on the other at 1 - price."""

    BOOK = OrderBook(
        ticker="KXHIGHNY-26OCT11-T62",
        yes_bids=(
            PriceLevel(Decimal("0.20"), 100),
            PriceLevel(Decimal("0.25"), 200),
        ),
        no_bids=(
            PriceLevel(Decimal("0.60"), 10),
            PriceLevel(Decimal("0.65"), 20),
            PriceLevel(Decimal("0.70"), 30),
        ),
        notional_value=Decimal("1"),
    )

    def test_parses_the_live_payload_shape(self):
        book = OrderBook.from_api(
            "KXHIGHNY-26OCT11-T62",
            {
                "orderbook_fp": {
                    "no_dollars": [["0.3500", "130.00"], ["0.3600", "11.00"]],
                    "yes_dollars": [["0.6200", "32.00"], ["0.6300", "32.00"]],
                }
            },
        )

        assert book.no_bids[-1] == PriceLevel(Decimal("0.3600"), 11)
        assert book.yes_bids[-1] == PriceLevel(Decimal("0.6300"), 32)

    def test_best_ask_mirrors_the_opposing_best_bid(self):
        """Live check: a top no_dollars bid of 0.36 matched a published yes_ask of 0.64."""
        book = OrderBook.from_api(
            "T", {"orderbook_fp": {"no_dollars": [["0.3600", "11.00"]], "yes_dollars": []}}
        )

        assert book.best_ask(Side.YES) == PriceLevel(Decimal("0.6400"), 11)

    def test_best_ask_is_the_cheapest_available_offer(self):
        assert self.BOOK.best_ask(Side.YES) == PriceLevel(Decimal("0.30"), 30)
        assert self.BOOK.best_ask(Side.NO) == PriceLevel(Decimal("0.75"), 200)

    def test_missing_opposing_side_means_no_offer(self):
        empty = OrderBook.from_api("T", {"orderbook_fp": {"no_dollars": [], "yes_dollars": []}})

        assert empty.best_ask(Side.YES) is None

    def test_depth_walks_the_ladder_and_averages_the_fill_price(self):
        fill = self.BOOK.depth_up_to(Side.YES, Decimal("0.35"))

        assert fill.contracts == 50
        assert fill.cost == Decimal("16.00")
        assert fill.average_price == Decimal("0.32")
        assert fill.worst_price == Decimal("0.35")

    def test_depth_across_the_whole_ladder(self):
        fill = self.BOOK.depth_up_to(Side.YES, Decimal("1"))

        assert fill.contracts == 60
        assert fill.cost == Decimal("20.00")

    def test_depth_is_far_greater_than_top_of_book(self):
        """Top-of-book alone would cap a hedge at 30 contracts out of 60 available."""
        assert self.BOOK.best_ask(Side.YES).contracts == 30
        assert self.BOOK.depth_up_to(Side.YES, Decimal("1")).contracts == 60

    def test_a_limit_below_the_best_ask_fills_nothing(self):
        fill = self.BOOK.depth_up_to(Side.YES, Decimal("0.29"))

        assert fill.contracts == 0
        assert fill.cost == Decimal("0")
        assert fill.average_price is None

    def test_quote_uses_book_depth_rather_than_top_of_book_size(self):
        window = ContractWindow(opens=date(2026, 10, 11), settles=date(2026, 10, 11))

        quote = self.BOOK.to_quote(window, limit_price=Decimal("0.35"))

        assert quote.yes_ask == Decimal("0.32")
        assert quote.yes_ask_size == 50
        assert quote.exposure_window == window

    def test_quote_reports_no_offer_on_a_side_the_limit_cannot_reach(self):
        """The cheapest NO ask here is 0.75, so a 0.35 limit fills nothing on that side."""
        window = ContractWindow(opens=date(2026, 10, 11), settles=date(2026, 10, 11))

        quote = self.BOOK.to_quote(window, limit_price=Decimal("0.35"))

        assert quote.no_ask == Decimal("0")
        assert quote.no_ask_size == 0
