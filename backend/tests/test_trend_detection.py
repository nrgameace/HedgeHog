import json

import pytest

from app.trend_detection import MIN_CATEGORY_CONFIDENCE, TREND_DETECTION_SCHEMA, HedgeableCategory, TrendDetectionError, detect_hedgeable_categories
from tests.sample_data import ANSWERS

RAIN = {"category": "rain", "label": "Rain", "reasoning": "Rainy days empty the patio.", "confidence": 90, "market_family": "rain"}
EXPECTED_RAIN = HedgeableCategory(category="rain", label="Rain", reasoning="Rainy days empty the patio.", confidence=90, market_family="rain")


def _detect_with_reply(monkeypatch, reply: str) -> list[HedgeableCategory]:
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: reply)
    return detect_hedgeable_categories(ANSWERS, [])


def _detect_with_items(monkeypatch, *items) -> list[HedgeableCategory]:
    return _detect_with_reply(monkeypatch, json.dumps({"hedgeable_categories": list(items)}))


def test_parses_valid_response(monkeypatch):
    assert _detect_with_items(monkeypatch, RAIN) == [EXPECTED_RAIN]


def test_strips_markdown_fences(monkeypatch):
    assert _detect_with_reply(monkeypatch, f"```json\n{json.dumps({'hedgeable_categories': [RAIN]})}\n```") == [EXPECTED_RAIN]


def test_keeps_categories_at_the_confidence_threshold(monkeypatch):
    low = {**RAIN, "category": "gas", "confidence": MIN_CATEGORY_CONFIDENCE - 1}
    edge = {**RAIN, "category": "heat", "confidence": MIN_CATEGORY_CONFIDENCE}

    assert [category.category for category in _detect_with_items(monkeypatch, low, edge)] == ["heat"]


def test_minimum_confidence_is_twenty():
    assert MIN_CATEGORY_CONFIDENCE == 20


def test_sorts_by_confidence_highest_first(monkeypatch):
    items = [{**RAIN, "category": "gas", "confidence": 40}, RAIN, {**RAIN, "category": "rates", "confidence": 60}]

    assert [category.category for category in _detect_with_items(monkeypatch, *items)] == ["rain", "rates", "gas"]


def test_dedupes_slugs_keeping_the_most_confident(monkeypatch):
    duplicate = {**RAIN, "label": "Weather", "confidence": 30}

    assert _detect_with_items(monkeypatch, duplicate, RAIN) == [EXPECTED_RAIN]


def test_returns_empty_when_nothing_is_confident_enough(monkeypatch):
    assert _detect_with_items(monkeypatch, {**RAIN, "confidence": 5}) == []


def test_sends_the_schema_and_forwards_config_and_client(monkeypatch):
    captured = {}

    def fake_chat_complete(messages, **kwargs):
        captured.update(kwargs)
        return json.dumps({"hedgeable_categories": [RAIN]})

    monkeypatch.setattr("app.trend_detection.chat_complete", fake_chat_complete)
    config, client = object(), object()

    detect_hedgeable_categories(ANSWERS, [], config=config, client=client)

    assert captured == {"response_schema": TREND_DETECTION_SCHEMA, "config": config, "client": client}


def test_schema_limits_families_and_confidence():
    item = TREND_DETECTION_SCHEMA["properties"]["hedgeable_categories"]["items"]

    assert item["properties"]["market_family"]["enum"] == ["rain", "heat", "gas", "oil", "inflation", "food_prices", "interest_rates", "jobs", "economy", "none"]
    assert (item["properties"]["confidence"]["minimum"], item["properties"]["confidence"]["maximum"]) == (0, 100)
    assert set(item["required"]) == {"category", "label", "reasoning", "confidence", "market_family"}


def test_raises_on_invalid_json(monkeypatch):
    with pytest.raises(TrendDetectionError):
        _detect_with_reply(monkeypatch, "not json at all")


def test_raises_on_missing_top_level_key(monkeypatch):
    with pytest.raises(TrendDetectionError):
        _detect_with_reply(monkeypatch, '{"wrong_key": []}')


@pytest.mark.parametrize(
    "item",
    [
        "rain",
        {"category": "rain"},
        {**RAIN, "reasoning": None},
        {**RAIN, "label": "  "},
        {**RAIN, "market_family": "lottery"},
        {**RAIN, "confidence": "high"},
        {**RAIN, "confidence": 101},
        {**RAIN, "confidence": True},
    ],
)
def test_raises_on_malformed_item(monkeypatch, item):
    with pytest.raises(TrendDetectionError):
        _detect_with_items(monkeypatch, item)
