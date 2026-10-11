import json

import pytest

from app.position_sizing import PlannedBet, PositionSizingError, SizingResult, UnhedgedRisk, candidates_by_category, plan_positions, position_sizing_schema
from app.trend_detection import HedgeableCategory
from tests.sample_data import ANSWERS, CANDIDATES, CATEGORIES, HISTORY, MARKETS, NOTES

RAIN_PLAN = {
    "ticker": "KXRAINAUSM-26OCT-4",
    "side": "YES",
    "amountUsd": 300,
    "frequency": "Monthly, Apr–Jun",
    "tradeMonths": [3, 4, 5],
    "hitMonths": [4, 5],
    "riskExplanation": "Rainy days empty the patio.",
    "rationale": "Pays out in rainy months.",
}
GAS_PLAN = {**RAIN_PLAN, "ticker": "KXAAAGASM-26OCT31-3.50", "tradeMonths": [5, 6], "hitMonths": [], "riskExplanation": "Van fuel.", "rationale": "Covers fuel."}

EXPECTED_RAIN = PlannedBet(
    category="rain", ticker="KXRAINAUSM-26OCT-4", side="YES", amount_usd=300, frequency="Monthly, Apr–Jun",
    trade_months=[3, 4, 5], hit_months=[4, 5], risk_explanation="Rainy days empty the patio.", rationale="Pays out in rainy months.",
)


def _plan_with_reply(monkeypatch, reply: str, candidates=CANDIDATES) -> SizingResult:
    monkeypatch.setattr("app.position_sizing.chat_complete", lambda *args, **kwargs: reply)
    return plan_positions(ANSWERS, CATEGORIES, HISTORY, NOTES, candidates)


def _plan_with(monkeypatch, rain: object = RAIN_PLAN, gas: object = GAS_PLAN) -> SizingResult:
    plans = {slug: plan for slug, plan in (("rain", rain), ("gas_prices", gas)) if plan is not None}
    return _plan_with_reply(monkeypatch, json.dumps({"plans": plans}))


def test_candidates_by_category_matches_market_families():
    assert candidates_by_category(CATEGORIES, MARKETS) == CANDIDATES


def test_candidates_by_category_gives_none_family_no_candidates():
    gpu = HedgeableCategory(category="gpu", label="GPU prices", reasoning="Compute.", confidence=80, market_family="none")

    assert candidates_by_category([gpu], MARKETS) == {"gpu": []}


def test_schema_requires_every_category_and_limits_tickers_per_category():
    plans = position_sizing_schema(CANDIDATES)["properties"]["plans"]

    assert set(plans["required"]) == {"rain", "gas_prices"}
    assert plans["properties"]["rain"]["properties"]["ticker"]["enum"] == ["KXRAINAUSM-26OCT-4", "NONE"]
    assert plans["properties"]["gas_prices"]["properties"]["ticker"]["enum"] == ["KXAAAGASM-26OCT31-3.50", "NONE"]
    assert plans["additionalProperties"] is False


def test_schema_skips_categories_without_candidates():
    plans = position_sizing_schema({**CANDIDATES, "gpu": []})["properties"]["plans"]

    assert "gpu" not in plans["required"]


def test_parses_a_bet_for_each_category(monkeypatch):
    result = _plan_with(monkeypatch)

    assert result.bets[0] == EXPECTED_RAIN
    assert [bet.category for bet in result.bets] == ["rain", "gas_prices"]
    assert result.unhedged == []


def test_sends_the_schema_and_only_categories_with_candidates(monkeypatch):
    captured = {}

    def fake_chat_complete(messages, **kwargs):
        captured.update(messages=messages, schema=kwargs["response_schema"])
        return json.dumps({"plans": {"rain": RAIN_PLAN}})

    monkeypatch.setattr("app.position_sizing.chat_complete", fake_chat_complete)
    plan_positions(ANSWERS, CATEGORIES, HISTORY, NOTES, {"rain": CANDIDATES["rain"], "gas_prices": []})

    assert captured["schema"] == position_sizing_schema({"rain": CANDIDATES["rain"]})
    assert "gas_prices" not in captured["messages"][1]["content"]


def test_skips_the_model_when_no_category_has_candidates(monkeypatch):
    monkeypatch.setattr("app.position_sizing.chat_complete", lambda *args, **kwargs: pytest.fail("model should not be called"))

    assert plan_positions(ANSWERS, CATEGORIES, HISTORY, NOTES, {"rain": [], "gas_prices": []}) == SizingResult(bets=[], unhedged=[])


def test_none_ticker_is_unhedged_no_fit(monkeypatch):
    result = _plan_with(monkeypatch, gas={**GAS_PLAN, "ticker": "NONE"})

    assert [bet.category for bet in result.bets] == ["rain"]
    assert result.unhedged == [UnhedgedRisk(category="gas_prices", reason="no_fit")]


def test_missing_category_is_unhedged_no_fit(monkeypatch):
    assert _plan_with(monkeypatch, gas=None).unhedged == [UnhedgedRisk(category="gas_prices", reason="no_fit")]


def test_ticker_from_another_category_is_unhedged_no_fit(monkeypatch):
    assert _plan_with(monkeypatch, gas={**GAS_PLAN, "ticker": "KXRAINAUSM-26OCT-4"}).unhedged == [UnhedgedRisk(category="gas_prices", reason="no_fit")]


def test_duplicate_ticker_is_unhedged_as_covered(monkeypatch):
    candidates = {"rain": CANDIDATES["rain"], "gas_prices": CANDIDATES["rain"]}
    plans = {"rain": RAIN_PLAN, "gas_prices": RAIN_PLAN}

    result = _plan_with_reply(monkeypatch, json.dumps({"plans": plans}), candidates)

    assert result.unhedged == [UnhedgedRisk(category="gas_prices", reason="duplicate", covered_by="rain")]


@pytest.mark.parametrize(
    "bad_plan",
    [
        "rain",
        {**RAIN_PLAN, "side": "MAYBE"},
        {**RAIN_PLAN, "amountUsd": 0},
        {**RAIN_PLAN, "amountUsd": "300"},
        {**RAIN_PLAN, "tradeMonths": [13]},
        {**RAIN_PLAN, "rationale": " "},
        {**RAIN_PLAN, "ticker": {"a": 1}},
    ],
)
def test_malformed_plan_is_unhedged_no_fit(monkeypatch, bad_plan):
    assert _plan_with(monkeypatch, rain=bad_plan).unhedged == [UnhedgedRisk(category="rain", reason="no_fit")]


@pytest.mark.parametrize("amount", ["NaN", "Infinity"])
def test_non_finite_amount_is_unhedged(monkeypatch, amount):
    reply = json.dumps({"plans": {"rain": RAIN_PLAN, "gas_prices": GAS_PLAN}}).replace('"amountUsd": 300', f'"amountUsd": {amount}', 1)

    assert UnhedgedRisk(category="rain", reason="no_fit") in _plan_with_reply(monkeypatch, reply).unhedged


def test_rounds_fractional_amount(monkeypatch):
    assert _plan_with(monkeypatch, rain={**RAIN_PLAN, "amountUsd": 299.6}).bets[0].amount_usd == 300


def test_filters_out_of_range_and_duplicate_months(monkeypatch):
    assert _plan_with(monkeypatch, rain={**RAIN_PLAN, "tradeMonths": [12, 5, -1, 3, 3, "4", 4.0]}).bets[0].trade_months == [3, 5]


def test_hit_months_limited_to_trade_months(monkeypatch):
    assert _plan_with(monkeypatch, rain={**RAIN_PLAN, "hitMonths": [4, 7, 5]}).bets[0].hit_months == [4, 5]


def test_strips_fences(monkeypatch):
    assert _plan_with_reply(monkeypatch, f"```json\n{json.dumps({'plans': {'rain': RAIN_PLAN, 'gas_prices': GAS_PLAN}})}\n```").bets[0] == EXPECTED_RAIN


def test_raises_on_invalid_json(monkeypatch):
    with pytest.raises(PositionSizingError):
        _plan_with_reply(monkeypatch, "not json")


def test_raises_on_missing_plans(monkeypatch):
    with pytest.raises(PositionSizingError):
        _plan_with_reply(monkeypatch, '{"bets": []}')


def test_candidates_withhold_band_markets():
    """A 94-95 degree band is not a heat hedge: YES pays on a pleasant Austin day."""
    from app.kalshi_client import KalshiMarket
    from app.position_sizing import candidates_by_category
    from app.trend_detection import HedgeableCategory

    heat = HedgeableCategory(category="heat", label="Extreme heat", reasoning="100F empties the street.", confidence=85, market_family="heat")
    band = KalshiMarket("KXHIGHAUS-26OCT11-B94.5", "Will the maximum temperature be 94-95?", "94 to 95", 0.32, strike_type="between")
    tail = KalshiMarket("KXHIGHAUS-26OCT11-T97", "Will the maximum temperature be >97?", "98 or above", 0.01, strike_type="greater")

    offered = candidates_by_category([heat], [band, tail])["heat"]

    assert [market.ticker for market in offered] == ["KXHIGHAUS-26OCT11-T97"]
