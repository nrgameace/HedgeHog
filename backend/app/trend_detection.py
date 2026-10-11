from dataclasses import dataclass

import httpx

from app.akamai_client import AkamaiConfig, chat_complete
from app.market_catalog import MARKET_FAMILIES
from app.model_json import parse_model_json
from app.prompts import build_trend_detection_messages
from app.questionnaire import QuestionnaireAnswers


MIN_CATEGORY_CONFIDENCE = 20
MAX_CATEGORIES = 10
TEXT_FIELDS = ("category", "label", "reasoning")

TREND_DETECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "hedgeable_categories": {
            "type": "array",
            "maxItems": MAX_CATEGORIES,
            "items": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "label": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "market_family": {"enum": list(MARKET_FAMILIES)},
                },
                "required": ["category", "label", "reasoning", "confidence", "market_family"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["hedgeable_categories"],
    "additionalProperties": False,
}


@dataclass
class HedgeableCategory:
    category: str
    label: str
    reasoning: str
    confidence: int
    market_family: str


class TrendDetectionError(Exception):
    pass


def _is_valid_confidence(value: object) -> bool:
    return type(value) is int and 0 <= value <= 100


def _parse_category(item: object) -> HedgeableCategory:
    if not isinstance(item, dict):
        raise TrendDetectionError(f"hedgeable_categories entry was not an object: {item!r}")
    if not all(isinstance(item.get(field), str) and item[field].strip() for field in TEXT_FIELDS):
        raise TrendDetectionError(f"hedgeable_categories entry had a missing or empty text field: {item!r}")
    if not _is_valid_confidence(item.get("confidence")) or item.get("market_family") not in MARKET_FAMILIES:
        raise TrendDetectionError(f"hedgeable_categories entry had a bad confidence or market_family: {item!r}")
    return HedgeableCategory(category=item["category"], label=item["label"], reasoning=item["reasoning"], confidence=item["confidence"], market_family=item["market_family"])


def _confident_unique(categories: list[HedgeableCategory]) -> list[HedgeableCategory]:
    kept: dict[str, HedgeableCategory] = {}
    for category in sorted(categories, key=lambda category: category.confidence, reverse=True):
        if category.confidence >= MIN_CATEGORY_CONFIDENCE and category.category not in kept:
            kept[category.category] = category
    return list(kept.values())


def detect_hedgeable_categories(answers: QuestionnaireAnswers, financials: list[dict[str, str]], *, config: AkamaiConfig | None = None, client: httpx.Client | None = None) -> list[HedgeableCategory]:
    messages = build_trend_detection_messages(answers, financials)
    reply = chat_complete(messages, response_schema=TREND_DETECTION_SCHEMA, config=config, client=client)
    try:
        parsed = parse_model_json(reply)
    except ValueError as exc:
        raise TrendDetectionError(f"model reply was not valid JSON: {reply}") from exc

    categories = parsed.get("hedgeable_categories") if isinstance(parsed, dict) else None
    if not isinstance(categories, list):
        raise TrendDetectionError(f"model reply missing 'hedgeable_categories' list: {reply}")

    return _confident_unique([_parse_category(item) for item in categories])
