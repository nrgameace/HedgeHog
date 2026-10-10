import pytest

from app.trend_detection import HedgeableCategory, TrendDetectionError, detect_hedgeable_categories

VALID_REPLY = '{"hedgeable_categories": [{"category": "rain", "label": "Rain", "reasoning": "Owner says rainy days hurt ice cream sales."}]}'


def test_detect_hedgeable_categories_parses_valid_response(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: VALID_REPLY)

    result = detect_hedgeable_categories("ice cream shop", "rainy days", [])

    assert result == [HedgeableCategory(category="rain", label="Rain", reasoning="Owner says rainy days hurt ice cream sales.")]


def test_detect_hedgeable_categories_strips_markdown_fences(monkeypatch):
    fenced = f"```json\n{VALID_REPLY}\n```"
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: fenced)

    result = detect_hedgeable_categories("ice cream shop", "rainy days", [])

    assert result == [HedgeableCategory(category="rain", label="Rain", reasoning="Owner says rainy days hurt ice cream sales.")]


def test_detect_hedgeable_categories_raises_on_invalid_json(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: "not json at all")

    with pytest.raises(TrendDetectionError):
        detect_hedgeable_categories("ice cream shop", "rainy days", [])


def test_detect_hedgeable_categories_raises_on_missing_top_level_key(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: '{"wrong_key": []}')

    with pytest.raises(TrendDetectionError):
        detect_hedgeable_categories("ice cream shop", "rainy days", [])


def test_detect_hedgeable_categories_raises_on_malformed_item(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: '{"hedgeable_categories": [{"category": "rain"}]}')

    with pytest.raises(TrendDetectionError):
        detect_hedgeable_categories("ice cream shop", "rainy days", [])
