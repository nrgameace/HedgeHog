import os
from dataclasses import dataclass

import httpx
from dotenv import load_dotenv

load_dotenv()

DEFAULT_REQUEST_TIMEOUT_SECONDS = 60.0
FIXED_SEED = 0


class AkamaiConfigError(Exception):
    pass


class AkamaiApiError(Exception):
    pass


@dataclass
class AkamaiConfig:
    base_url: str
    api_key: str
    chat_model: str

    @classmethod
    def from_env(cls) -> "AkamaiConfig":
        values = {
            "base_url": os.environ.get("AKAMAI_API_BASE_URL"),
            "api_key": os.environ.get("AKAMAI_API_KEY"),
            "chat_model": os.environ.get("AKAMAI_CHAT_MODEL"),
        }
        env_names = {"base_url": "AKAMAI_API_BASE_URL", "api_key": "AKAMAI_API_KEY", "chat_model": "AKAMAI_CHAT_MODEL"}
        missing = [env_names[field] for field, value in values.items() if not value]
        if missing:
            raise AkamaiConfigError(f"missing required environment variable(s): {', '.join(missing)}")
        return cls(**values)


def _request_body(model: str, messages: list[dict[str, str]], temperature: float, response_schema: dict | None) -> dict:
    body = {"model": model, "messages": messages, "temperature": temperature, "seed": FIXED_SEED}
    if response_schema is not None:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "response", "schema": response_schema, "strict": True}}
    return body


def chat_complete(messages: list[dict[str, str]], *, temperature: float = 0.0, response_schema: dict | None = None, config: AkamaiConfig | None = None, client: httpx.Client | None = None) -> str:
    config = config or AkamaiConfig.from_env()
    owns_client = client is None
    client = client or httpx.Client(timeout=DEFAULT_REQUEST_TIMEOUT_SECONDS)
    try:
        url = f"{config.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {config.api_key}"}
        body = _request_body(config.chat_model, messages, temperature, response_schema)
        try:
            response = client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise AkamaiApiError(f"request to Akamai failed: {exc}") from exc
        if response.status_code != 200:
            raise AkamaiApiError(f"Akamai API returned {response.status_code}: {response.text}")
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise AkamaiApiError(f"unexpected Akamai API response shape: {response.text}") from exc
        if not isinstance(content, str):
            raise AkamaiApiError(f"Akamai API returned non-string content: {content!r}")
        return content
    finally:
        if owns_client:
            client.close()
