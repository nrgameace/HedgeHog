"""Getting a JSON object out of what a model actually returns.

Every model call in this project asks for structured JSON, and models deliver it
imperfectly: wrapped in a markdown fence despite being told not to, prefaced
with "Sure! Here you go", or both. Extraction tolerates all of that and raises
rather than handing back something half-parsed, so a caller can degrade to a
safe default instead of feeding junk into a sizing calculation.

The transport lives in `app/akamai_client.py`; this module only parses.
"""

import json

MAX_ERROR_EXCERPT = 200


class ModelReplyError(RuntimeError):
    """The model's reply did not contain a usable JSON object."""


def parse_json_object(content: str) -> dict:
    """Pull a JSON object out of a reply that may be fenced or surrounded by prose."""
    text = _strip_fence(content.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ModelReplyError(f"reply contained no JSON object: {_excerpt(content)}")

    # Slicing between the outermost braces means the result parses to a dict or
    # raises, so no further type check is reachable here.
    try:
        return json.loads(text[start : end + 1])
    except ValueError as exc:
        raise ModelReplyError(f"reply was not valid JSON: {_excerpt(content)}") from exc


def _strip_fence(text: str) -> str:
    """Drop a leading ```/```json line and anything after the closing fence."""
    if not text.startswith("```"):
        return text
    without_open = text.split("\n", 1)[-1]
    return without_open.rsplit("```", 1)[0]


def _excerpt(content: str) -> str:
    return content[:MAX_ERROR_EXCERPT]
