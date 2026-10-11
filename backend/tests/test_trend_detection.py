import pytest

from app.trend_detection import HedgeableCategory, TrendDetectionError, detect_hedgeable_categories
from tests.sample_data import ANSWERS

VALID_REPLY = '{"hedgeable_categories": [{"category": "rain", "label": "Rain", "reasoning": "Owner says rainy days hurt ice cream sales."}]}'


def test_detect_hedgeable_categories_parses_valid_response(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: VALID_REPLY)

    result = detect_hedgeable_categories(ANSWERS, [])

    assert result == [HedgeableCategory(category="rain", label="Rain", reasoning="Owner says rainy days hurt ice cream sales.")]


def test_detect_hedgeable_categories_strips_markdown_fences(monkeypatch):
    fenced = f"```json\n{VALID_REPLY}\n```"
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: fenced)

    result = detect_hedgeable_categories(ANSWERS, [])

    assert result == [HedgeableCategory(category="rain", label="Rain", reasoning="Owner says rainy days hurt ice cream sales.")]


def test_detect_hedgeable_categories_raises_on_invalid_json(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: "not json at all")

    with pytest.raises(TrendDetectionError):
        detect_hedgeable_categories(ANSWERS, [])


def test_detect_hedgeable_categories_raises_on_missing_top_level_key(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: '{"wrong_key": []}')

    with pytest.raises(TrendDetectionError):
        detect_hedgeable_categories(ANSWERS, [])


def test_detect_hedgeable_categories_raises_on_malformed_item(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: '{"hedgeable_categories": [{"category": "rain"}]}')

    with pytest.raises(TrendDetectionError):
        detect_hedgeable_categories(ANSWERS, [])


def test_detect_hedgeable_categories_raises_on_non_dict_item(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: '{"hedgeable_categories": ["rain"]}')

    with pytest.raises(TrendDetectionError):
        detect_hedgeable_categories(ANSWERS, [])


def test_detect_hedgeable_categories_raises_on_non_list_hedgeable_categories(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: '{"hedgeable_categories": {"category": "rain"}}')

    with pytest.raises(TrendDetectionError):
        detect_hedgeable_categories(ANSWERS, [])


def test_detect_hedgeable_categories_raises_on_non_string_field(monkeypatch):
    monkeypatch.setattr(
        "app.trend_detection.chat_complete",
        lambda *args, **kwargs: '{"hedgeable_categories": [{"category": "rain", "label": "Rain", "reasoning": null}]}',
    )

    with pytest.raises(TrendDetectionError):
        detect_hedgeable_categories(ANSWERS, [])


def test_detect_hedgeable_categories_strips_fence_without_language_tag(monkeypatch):
    fenced = f"```\n{VALID_REPLY}\n```"
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: fenced)

    result = detect_hedgeable_categories(ANSWERS, [])

    assert result == [HedgeableCategory(category="rain", label="Rain", reasoning="Owner says rainy days hurt ice cream sales.")]


def test_detect_hedgeable_categories_forwards_config_and_client_with_deterministic_defaults(monkeypatch):
    captured = {}

    def fake_chat_complete(messages, **kwargs):
        captured["kwargs"] = kwargs
        config, client = kwargs.get("config"), kwargs.get("client")
        captured["config"] = config
        captured["client"] = client
        return VALID_REPLY

    monkeypatch.setattr("app.trend_detection.chat_complete", fake_chat_complete)
    sentinel_config = object()
    sentinel_client = object()

    detect_hedgeable_categories(ANSWERS, [], config=sentinel_config, client=sentinel_client)

    assert "temperature" not in captured["kwargs"]
    assert captured["config"] is sentinel_config
    assert captured["client"] is sentinel_client
