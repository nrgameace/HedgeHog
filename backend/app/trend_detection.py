import json
from dataclasses import dataclass

import httpx

from app.akamai_client import AkamaiConfig, chat_complete
from app.prompts import build_trend_detection_messages


@dataclass
class HedgeableCategory:
    category: str
    label: str
    reasoning: str


class TrendDetectionError(Exception):
    pass


def _strip_markdown_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return stripped


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


def detect_hedgeable_categories(industry: str, loss_factors: str, financials: list[dict[str, str]], *, config: AkamaiConfig | None = None, client: httpx.Client | None = None) -> list[HedgeableCategory]:
    messages = build_trend_detection_messages(industry, loss_factors, financials)
    reply = chat_complete(messages, temperature=0.2, config=config, client=client)
    unfenced = _strip_markdown_fence(reply)
    try:
        parsed = json.loads(unfenced)
    except json.JSONDecodeError as exc:
        raise TrendDetectionError(f"model reply was not valid JSON: {reply}") from exc

    categories = parsed.get("hedgeable_categories") if isinstance(parsed, dict) else None
    if not isinstance(categories, list):
        raise TrendDetectionError(f"model reply missing 'hedgeable_categories' list: {reply}")

    return [_parse_category(item) for item in categories]
