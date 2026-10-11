from dataclasses import dataclass

import httpx

from app.akamai_client import AkamaiConfig, chat_complete
from app.model_json import parse_model_json
from app.prompts import build_trend_detection_messages
from app.questionnaire import QuestionnaireAnswers


@dataclass
class HedgeableCategory:
    category: str
    label: str
    reasoning: str


class TrendDetectionError(Exception):
    pass


def _parse_category(item: object) -> HedgeableCategory:
    if not isinstance(item, dict):
        raise TrendDetectionError(f"hedgeable_categories entry was not an object: {item!r}")
    try:
        category, label, reasoning = item["category"], item["label"], item["reasoning"]
    except KeyError as exc:
        raise TrendDetectionError(f"hedgeable_categories entry missing required field: {exc}") from exc
    if not all(isinstance(value, str) and value.strip() for value in (category, label, reasoning)):
        raise TrendDetectionError(f"hedgeable_categories entry had a non-string or empty field: {item!r}")
    return HedgeableCategory(category=category, label=label, reasoning=reasoning)


def detect_hedgeable_categories(answers: QuestionnaireAnswers, financials: list[dict[str, str]], *, config: AkamaiConfig | None = None, client: httpx.Client | None = None) -> list[HedgeableCategory]:
    messages = build_trend_detection_messages(answers, financials)
    reply = chat_complete(messages, config=config, client=client)
    try:
        parsed = parse_model_json(reply)
    except ValueError as exc:
        raise TrendDetectionError(f"model reply was not valid JSON: {reply}") from exc

    categories = parsed.get("hedgeable_categories") if isinstance(parsed, dict) else None
    if not isinstance(categories, list):
        raise TrendDetectionError(f"model reply missing 'hedgeable_categories' list: {reply}")

    return [_parse_category(item) for item in categories]
