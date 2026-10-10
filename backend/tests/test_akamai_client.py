import json

import httpx
import pytest

from app.akamai_client import AkamaiApiError, AkamaiConfig, AkamaiConfigError, chat_complete

FAKE_CONFIG = AkamaiConfig(base_url="https://fake.test/v1", api_key="test-key-123", chat_model="hackathon-chat")


def _client_with_response(status_code: int, json_body: dict | None = None, text_body: str | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if json_body is not None:
            return httpx.Response(status_code, json=json_body)
        return httpx.Response(status_code, text=text_body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_chat_complete_returns_message_content():
    client = _client_with_response(200, json_body={"choices": [{"message": {"content": "OK"}}]})

    result = chat_complete([{"role": "user", "content": "hi"}], config=FAKE_CONFIG, client=client)

    assert result == "OK"


def test_chat_complete_sends_expected_request():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))

    chat_complete([{"role": "user", "content": "hi"}], config=FAKE_CONFIG, client=client)

    assert captured["url"] == "https://fake.test/v1/chat/completions"
    assert captured["authorization"] == "Bearer test-key-123"
    assert captured["json"] == {
        "model": "hackathon-chat",
        "messages": [{"role": "user", "content": "hi"}],
        "temperature": 0.2,
    }


def test_chat_complete_raises_on_non_200():
    client = _client_with_response(401, text_body="api key authentication failure: invalid credentials")

    with pytest.raises(AkamaiApiError):
        chat_complete([{"role": "user", "content": "hi"}], config=FAKE_CONFIG, client=client)


def test_chat_complete_raises_on_response_missing_choices():
    client = _client_with_response(200, json_body={"unexpected": "shape"})

    with pytest.raises(AkamaiApiError):
        chat_complete([{"role": "user", "content": "hi"}], config=FAKE_CONFIG, client=client)


def test_from_env_raises_when_api_key_missing(monkeypatch):
    monkeypatch.setenv("AKAMAI_API_BASE_URL", "https://fake.test/v1")
    monkeypatch.delenv("AKAMAI_API_KEY", raising=False)
    monkeypatch.setenv("AKAMAI_CHAT_MODEL", "hackathon-chat")

    with pytest.raises(AkamaiConfigError):
        AkamaiConfig.from_env()


def test_from_env_builds_config_from_environment(monkeypatch):
    monkeypatch.setenv("AKAMAI_API_BASE_URL", "https://fake.test/v1")
    monkeypatch.setenv("AKAMAI_API_KEY", "test-key-123")
    monkeypatch.setenv("AKAMAI_CHAT_MODEL", "hackathon-chat")

    config = AkamaiConfig.from_env()

    assert config == FAKE_CONFIG
