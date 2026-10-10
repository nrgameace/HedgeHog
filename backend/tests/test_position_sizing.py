import json

import pytest

from app.position_sizing import PlannedBet, PositionSizingError, plan_positions
from tests.sample_data import ANSWERS, CATEGORIES, HISTORY, MARKETS, NOTES

RAIN_BET = {
    "category": "rain",
    "ticker": "KXRAINAUSM-26OCT-4",
    "side": "YES",
    "amountUsd": 300,
    "frequency": "Monthly, Apr–Jun",
    "tradeMonths": [3, 4, 5],
    "hitMonths": [4, 5],
    "riskExplanation": "Rainy days empty the patio.",
    "rationale": "Pays out in rainy months.",
}

EXPECTED_RAIN = PlannedBet(
    category="rain", ticker="KXRAINAUSM-26OCT-4", side="YES", amount_usd=300, frequency="Monthly, Apr–Jun",
    trade_months=[3, 4, 5], hit_months=[4, 5], risk_explanation="Rainy days empty the patio.", rationale="Pays out in rainy months.",
)


def _plan_with_reply(monkeypatch, reply: str) -> list[PlannedBet]:
    monkeypatch.setattr("app.position_sizing.chat_complete", lambda *args, **kwargs: reply)
    return plan_positions(ANSWERS, CATEGORIES, HISTORY, NOTES, MARKETS)


def _plan_with_bets(monkeypatch, *bets: dict) -> list[PlannedBet]:
    return _plan_with_reply(monkeypatch, json.dumps({"bets": list(bets)}))


def test_parses_valid_bet(monkeypatch):
    assert _plan_with_bets(monkeypatch, RAIN_BET) == [EXPECTED_RAIN]


def test_sends_categories_and_markets_to_the_model(monkeypatch):
    captured = {}

    def fake_chat_complete(messages, **kwargs):
        captured["messages"] = messages
        return json.dumps({"bets": []})

    monkeypatch.setattr("app.position_sizing.chat_complete", fake_chat_complete)
    plan_positions(ANSWERS, CATEGORIES, HISTORY, NOTES, MARKETS)

    assert "gas_prices | Gas prices" in captured["messages"][1]["content"]
    assert "KXRAINAUSM-26OCT-4" in captured["messages"][1]["content"]


def test_strips_fences(monkeypatch):
    assert _plan_with_reply(monkeypatch, f"```json\n{json.dumps({'bets': [RAIN_BET]})}\n```") == [EXPECTED_RAIN]


def test_drops_unknown_ticker(monkeypatch):
    assert _plan_with_bets(monkeypatch, {**RAIN_BET, "ticker": "KXMADEUP-1"}) == []


def test_drops_unknown_category(monkeypatch):
    assert _plan_with_bets(monkeypatch, {**RAIN_BET, "category": "dairy"}) == []


def test_drops_duplicate_ticker(monkeypatch):
    assert _plan_with_bets(monkeypatch, RAIN_BET, {**RAIN_BET, "category": "gas_prices"}) == [EXPECTED_RAIN]


def test_drops_bad_side(monkeypatch):
    assert _plan_with_bets(monkeypatch, {**RAIN_BET, "side": "MAYBE"}) == []


@pytest.mark.parametrize("amount", [0, -5, "300", None])
def test_drops_nonpositive_or_non_numeric_amount(monkeypatch, amount):
    assert _plan_with_bets(monkeypatch, {**RAIN_BET, "amountUsd": amount}) == []


def test_rounds_fractional_amount(monkeypatch):
    assert _plan_with_bets(monkeypatch, {**RAIN_BET, "amountUsd": 299.6})[0].amount_usd == 300


@pytest.mark.parametrize("field", ["frequency", "riskExplanation", "rationale"])
def test_drops_bet_missing_text(monkeypatch, field):
    assert _plan_with_bets(monkeypatch, {**RAIN_BET, field: " "}) == []


def test_filters_out_of_range_months(monkeypatch):
    bets = _plan_with_bets(monkeypatch, {**RAIN_BET, "tradeMonths": [12, 5, -1, 3, 3, "4", 4.0]})

    assert bets[0].trade_months == [3, 5]


def test_drops_bet_without_valid_trade_months(monkeypatch):
    assert _plan_with_bets(monkeypatch, {**RAIN_BET, "tradeMonths": [13]}) == []


def test_hit_months_limited_to_trade_months(monkeypatch):
    assert _plan_with_bets(monkeypatch, {**RAIN_BET, "hitMonths": [4, 7, 5]})[0].hit_months == [4, 5]


def test_missing_hit_months_means_no_hits(monkeypatch):
    bet = {key: value for key, value in RAIN_BET.items() if key != "hitMonths"}

    assert _plan_with_bets(monkeypatch, bet)[0].hit_months == []


def test_drops_non_object_bet(monkeypatch):
    assert _plan_with_bets(monkeypatch, "rain", RAIN_BET) == [EXPECTED_RAIN]


def test_raises_on_invalid_json(monkeypatch):
    with pytest.raises(PositionSizingError):
        _plan_with_reply(monkeypatch, "not json")


def test_raises_on_missing_bets_key(monkeypatch):
    with pytest.raises(PositionSizingError):
        _plan_with_reply(monkeypatch, '{"trades": []}')
