import json
from datetime import date
from decimal import Decimal

import httpx
import pytest

from app.akamai_client import AkamaiConfig
from app.hedge.sizing import ContractWindow, MarketQuote, Side
from app.kalshi.models import Market
from app.model.selection import (
    MAX_IMPACT_PCT,
    FactorDirection,
    MarketOption,
    derive_side,
    select_market,
)

CONFIG = AkamaiConfig(
    base_url="https://inference.example/v1", api_key="test-key", chat_model="qwen-test"
)
WINDOW = ContractWindow(opens=date(2026, 10, 11), settles=date(2026, 10, 11))


def market(ticker: str, title: str, strike_type: str) -> Market:
    return Market.from_api(
        {
            "ticker": ticker,
            "event_ticker": ticker.rsplit("-", 1)[0],
            "title": title,
            "status": "active",
            "strike_type": strike_type,
            "close_time": "2026-10-12T05:00:00Z",
            "yes_ask_dollars": "0.2500",
            "no_ask_dollars": "0.7600",
            "yes_ask_size_fp": "5000.00",
            "no_ask_size_fp": "5000.00",
            "notional_value_dollars": "1.0000",
        }
    )


def option(ticker: str, title: str, strike_type: str = "less") -> MarketOption:
    return MarketOption(
        series_ticker=ticker.split("-")[0],
        series_title="Low Temperature Atlanta",
        frequency="daily",
        market=market(ticker, title, strike_type),
        quote=MarketQuote(
            ticker=ticker,
            yes_ask=Decimal("0.25"),
            no_ask=Decimal("0.76"),
            yes_ask_size=5000,
            no_ask_size=5000,
            exposure_window=WINDOW,
        ),
    )


COLD = option("KXLOWTATL-26OCT11-T56", "Will the minimum temperature be <56 on Oct 11?", "less")
WARM = option("KXLOWTATL-26OCT11-T63", "Will the minimum temperature be >63 on Oct 11?", "greater")


def reply(**fields) -> str:
    return json.dumps(fields)


def model_returning(content: str, recorder: list[httpx.Request] | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if recorder is not None:
            recorder.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def choose(content: str, options=(COLD, WARM), factor="cold weather"):
    return select_market(factor, options, config=CONFIG, client=model_returning(content))


class TestDeriveSide:
    """The direction trap: the same risk flips sides with how Kalshi phrased the market."""

    @pytest.mark.parametrize(
        ("direction", "strike_type", "expected"),
        [
            (FactorDirection.DOWN, "less", Side.YES),
            (FactorDirection.DOWN, "greater", Side.NO),
            (FactorDirection.UP, "greater", Side.YES),
            (FactorDirection.UP, "less", Side.NO),
        ],
    )
    def test_side_follows_the_factor_direction_and_the_strike_shape(self, direction, strike_type, expected):
        assert derive_side(direction, strike_type) is expected

    def test_an_ice_cream_shop_buys_the_contract_that_pays_when_it_is_cold(self):
        """Hurt by cold: YES on 'below 56', NO on 'above 63'. Both pay in the cold state."""
        assert derive_side(FactorDirection.DOWN, "less") is Side.YES
        assert derive_side(FactorDirection.DOWN, "greater") is Side.NO

    @pytest.mark.parametrize("strike_type", ["", "between", "custom", "unrecognised"])
    def test_an_unusable_strike_type_cannot_be_derived(self, strike_type):
        assert derive_side(FactorDirection.UP, strike_type) is None


class TestSelection:
    def test_returns_the_chosen_market_with_a_derived_side(self):
        choice = choose(
            reply(
                ticker="KXLOWTATL-26OCT11-T56",
                direction="down",
                impact_pct=0.18,
                rationale="A cold day cuts walk-in traffic.",
            )
        )

        assert choice.ticker == "KXLOWTATL-26OCT11-T56"
        assert choice.direction is FactorDirection.DOWN
        assert choice.side is Side.YES
        assert choice.side_was_derived is True
        assert choice.impact_pct == Decimal("0.18")
        assert choice.rationale == "A cold day cuts walk-in traffic."

    def test_the_same_direction_flips_the_side_on_an_oppositely_phrased_market(self):
        choice = choose(reply(ticker="KXLOWTATL-26OCT11-T63", direction="down", impact_pct=0.18))

        assert choice.side is Side.NO

    def test_a_rising_factor_buys_yes_on_an_above_market(self):
        choice = choose(reply(ticker="KXLOWTATL-26OCT11-T63", direction="up", impact_pct=0.1))

        assert choice.side is Side.YES

    def test_the_prompt_lists_the_candidate_markets(self):
        seen: list[httpx.Request] = []
        select_market(
            "cold weather",
            (COLD, WARM),
            config=CONFIG,
            client=model_returning(
                reply(ticker=COLD.market.ticker, direction="down", impact_pct=0.1), seen
            ),
        )
        prompt = json.loads(seen[0].content)["messages"][1]["content"]

        assert COLD.market.ticker in prompt
        assert WARM.market.ticker in prompt
        assert "cold weather" in prompt

    def test_no_options_means_no_model_call_and_no_choice(self):
        """Nothing to choose between, so the call is skipped rather than wasted."""
        seen: list[httpx.Request] = []

        assert select_market("x", (), config=CONFIG, client=model_returning("{}", seen)) is None
        assert seen == []


class TestGuardrails:
    def test_a_hallucinated_ticker_is_rejected(self):
        """A ticker outside the candidate list must never reach a sizing calculation."""
        assert choose(reply(ticker="KXINVENTED-99", direction="down", impact_pct=0.1)) is None

    def test_an_unparseable_reply_is_rejected(self):
        assert choose("I am not able to choose a market.") is None

    def test_a_missing_direction_is_rejected(self):
        assert choose(reply(ticker=COLD.market.ticker, impact_pct=0.1)) is None

    def test_an_unrecognised_direction_is_rejected(self):
        assert choose(reply(ticker=COLD.market.ticker, direction="sideways", impact_pct=0.1)) is None

    @pytest.mark.parametrize("stated", [0.95, 95, 150])
    def test_an_implausibly_large_impact_is_clamped(self, stated):
        """The shortfall scales linearly with this, so an unchecked value mis-sizes badly."""
        choice = choose(reply(ticker=COLD.market.ticker, direction="down", impact_pct=stated))

        assert choice.impact_pct == MAX_IMPACT_PCT

    def test_a_small_whole_number_reads_as_percentage_points(self):
        """5 means 5%, not 500%: a value above 1 is always percentage points."""
        choice = choose(reply(ticker=COLD.market.ticker, direction="down", impact_pct=5))

        assert choice.impact_pct == Decimal("0.05")

    def test_a_negative_impact_is_rejected(self):
        """A negative impact means the factor helps, so the market or direction is wrong."""
        assert choose(reply(ticker=COLD.market.ticker, direction="down", impact_pct=-0.2)) is None

    def test_a_zero_impact_is_rejected_because_there_is_nothing_to_hedge(self):
        assert choose(reply(ticker=COLD.market.ticker, direction="down", impact_pct=0)) is None

    def test_a_non_numeric_impact_is_rejected(self):
        assert choose(reply(ticker=COLD.market.ticker, direction="down", impact_pct="lots")) is None

    def test_a_percentage_given_as_whole_points_is_normalised(self):
        """Models often answer 18 for 18%, which unchecked would hedge 18x the exposure."""
        choice = choose(reply(ticker=COLD.market.ticker, direction="down", impact_pct=18))

        assert choice.impact_pct == Decimal("0.18")

    def test_an_unreachable_model_yields_no_choice(self):
        failing = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))

        assert select_market("x", (COLD,), config=CONFIG, client=failing) is None

    def test_missing_credentials_yield_no_choice(self, monkeypatch):
        for name in ("AKAMAI_API_BASE_URL", "AKAMAI_API_KEY", "AKAMAI_CHAT_MODEL"):
            monkeypatch.delenv(name, raising=False)

        assert select_market("x", (COLD,)) is None


class TestModelStatedSideFallback:
    def test_an_underivable_strike_uses_the_models_stated_side(self):
        directional = option("KXB200W-26SEP04-6.01", "B200 price up in next week?", "")

        choice = choose(
            reply(ticker=directional.market.ticker, direction="up", impact_pct=0.1, side="yes"),
            options=(directional,),
        )

        assert choice.side is Side.YES
        assert choice.side_was_derived is False

    def test_an_underivable_strike_with_no_stated_side_is_rejected(self):
        directional = option("KXB200W-26SEP04-6.01", "B200 price up in next week?", "")

        assert choose(
            reply(ticker=directional.market.ticker, direction="up", impact_pct=0.1),
            options=(directional,),
        ) is None

    def test_a_derivable_strike_ignores_a_contradicting_stated_side(self):
        """strike_type is mechanical, so it wins over the model's own guess."""
        choice = choose(
            reply(ticker=COLD.market.ticker, direction="down", impact_pct=0.1, side="no")
        )

        assert choice.side is Side.YES
        assert choice.side_was_derived is True


class TestUnbuyableSide:
    """Kalshi quotes many strikes one-sided, so the needed side may not be offered."""

    @staticmethod
    def _yes_only(ticker: str, title: str, strike_type: str) -> MarketOption:
        base = option(ticker, title, strike_type)
        return MarketOption(
            series_ticker=base.series_ticker,
            series_title=base.series_title,
            frequency=base.frequency,
            market=base.market,
            quote=MarketQuote(
                ticker=ticker,
                yes_ask=Decimal("0.25"),
                no_ask=Decimal("0"),
                yes_ask_size=5000,
                no_ask_size=0,
                exposure_window=WINDOW,
            ),
        )

    def test_a_choice_needing_the_unoffered_side_is_refused(self):
        """Hurt by a rise on a 'below' market needs NO, which has no depth here."""
        yes_only = self._yes_only("KXLOWTAUS-26OCT11-T60", "min temp below 60?", "less")

        assert choose(
            reply(ticker=yes_only.market.ticker, direction="up", impact_pct=0.1),
            options=(yes_only,),
        ) is None

    def test_a_choice_needing_the_offered_side_is_accepted(self):
        yes_only = self._yes_only("KXLOWTAUS-26OCT11-T60", "min temp below 60?", "less")

        choice = choose(
            reply(ticker=yes_only.market.ticker, direction="down", impact_pct=0.1),
            options=(yes_only,),
        )

        assert choice.side is Side.YES

    def test_the_prompt_says_which_side_is_buyable(self):
        seen: list[httpx.Request] = []
        yes_only = self._yes_only("KXLOWTAUS-26OCT11-T60", "min temp below 60?", "less")
        select_market(
            "cold",
            (yes_only,),
            config=CONFIG,
            client=model_returning(
                reply(ticker=yes_only.market.ticker, direction="down", impact_pct=0.1), seen
            ),
        )
        prompt = json.loads(seen[0].content)["messages"][1]["content"]

        assert "buyable: YES" in prompt
