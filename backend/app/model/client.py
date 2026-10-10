"""HTTP client for the Qwen model hosted on Akamai.

The wire format is OpenAI-compatible `POST /chat/completions`, which is what
most hosted inference endpoints speak. If Akamai's differs, this is the only
file that changes.

`complete_json` exists because every model call in this project asks for
structured JSON, and models deliver it imperfectly: wrapped in markdown fences,
prefaced with "Sure! Here you go", or truncated. Extraction tolerates all of
that and raises `ModelError` when nothing usable comes back, so callers can
degrade rather than crash - no model reply is ever trusted far enough to reach
a sizing calculation unvalidated.

Mocked by default. `MOCK_MODEL` must be explicitly set to "false" before
anything calls out, so an unconfigured endpoint can never be hit by accident.
"""

import json
import os
from dataclasses import dataclass
from types import TracebackType

import httpx

DEFAULT_TIMEOUT_SECONDS = 30.0
DEFAULT_MAX_TOKENS = 600

# Deterministic by default: these calls are classification and vocabulary
# lookup, where sampling variety is a liability rather than a feature.
DEFAULT_TEMPERATURE = 0.0


class ModelError(RuntimeError):
    """Any failure getting usable JSON out of the model: transport, status, or shape."""


@dataclass(frozen=True)
class ModelConfig:
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = DEFAULT_TIMEOUT_SECONDS


class ModelClient:
    def __init__(self, config: ModelConfig, transport: httpx.BaseTransport | None = None) -> None:
        self.config = config
        headers = {"Authorization": f"Bearer {config.api_key}"} if config.api_key else {}
        self._http = httpx.Client(
            base_url=config.base_url,
            transport=transport,
            timeout=config.timeout,
            headers=headers,
        )

    def __enter__(self) -> "ModelClient":
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    def complete_json(self, system: str, user: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> dict:
        """Ask for a JSON object and return it parsed, or raise `ModelError`."""
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": DEFAULT_TEMPERATURE,
            "max_tokens": max_tokens,
        }

        try:
            response = self._http.post("/chat/completions", json=payload)
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            raise ModelError(
                f"model returned {exc.response.status_code}: {exc.response.text[:200]}"
            ) from exc
        except httpx.HTTPError as exc:
            raise ModelError(f"could not reach the model: {exc}") from exc
        except ValueError as exc:
            raise ModelError(f"model response was not JSON: {exc}") from exc

        return _parse_object(_content(body))


def client_from_env() -> ModelClient | None:
    """A configured client, or None when mocked or unconfigured.

    None is a supported state rather than an error: callers fall back to their
    curated defaults, so the pipeline runs end to end before the Akamai endpoint
    exists.
    """
    if os.getenv("MOCK_MODEL", "true").strip().lower() != "false":
        return None

    base_url, model = os.getenv("MODEL_BASE_URL"), os.getenv("MODEL_NAME")
    if not base_url or not model:
        return None

    return ModelClient(
        ModelConfig(base_url=base_url, model=model, api_key=os.getenv("MODEL_API_KEY"))
    )


def _content(body: dict) -> str:
    choices = body.get("choices") or []
    if not choices:
        raise ModelError(f"model response carried no choices: {str(body)[:200]}")
    return (choices[0].get("message") or {}).get("content") or ""


def _parse_object(content: str) -> dict:
    """Pull a JSON object out of a model reply that may be fenced or surrounded by prose."""
    text = _strip_fence(content.strip())
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        raise ModelError(f"model reply contained no JSON object: {content[:200]}")

    try:
        parsed = json.loads(text[start : end + 1])
    except ValueError as exc:
        raise ModelError(f"model reply was not valid JSON: {content[:200]}") from exc

    if not isinstance(parsed, dict):
        raise ModelError(f"model reply was not a JSON object: {content[:200]}")
    return parsed


def _strip_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    without_open = text.split("\n", 1)[-1]
    return without_open.rsplit("```", 1)[0]
