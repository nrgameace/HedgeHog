import json

import httpx
import pytest

from app.akamai_client import DEFAULT_REQUEST_TIMEOUT_SECONDS, AkamaiApiError, AkamaiConfig, AkamaiConfigError, chat_complete

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
        "temperature": 0.0,
        "seed": 0,
        "max_tokens": 4096,
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


def test_from_env_raises_when_api_key_is_empty_string(monkeypatch):
    monkeypatch.setenv("AKAMAI_API_BASE_URL", "https://fake.test/v1")
    monkeypatch.setenv("AKAMAI_API_KEY", "")
    monkeypatch.setenv("AKAMAI_CHAT_MODEL", "hackathon-chat")

    with pytest.raises(AkamaiConfigError):
        AkamaiConfig.from_env()


def test_from_env_error_names_all_missing_variables(monkeypatch):
    monkeypatch.delenv("AKAMAI_API_BASE_URL", raising=False)
    monkeypatch.delenv("AKAMAI_API_KEY", raising=False)
    monkeypatch.setenv("AKAMAI_CHAT_MODEL", "hackathon-chat")

    with pytest.raises(AkamaiConfigError) as exc_info:
        AkamaiConfig.from_env()

    assert "AKAMAI_API_BASE_URL" in str(exc_info.value)
    assert "AKAMAI_API_KEY" in str(exc_info.value)


def test_chat_complete_raises_on_non_200_includes_status_and_body():
    client = _client_with_response(401, text_body="api key authentication failure: invalid credentials")

    with pytest.raises(AkamaiApiError) as exc_info:
        chat_complete([{"role": "user", "content": "hi"}], config=FAKE_CONFIG, client=client)

    assert "401" in str(exc_info.value)
    assert "invalid credentials" in str(exc_info.value)


def test_chat_complete_wraps_network_errors():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))

    with pytest.raises(AkamaiApiError):
        chat_complete([{"role": "user", "content": "hi"}], config=FAKE_CONFIG, client=client)


def test_chat_complete_raises_when_content_is_not_a_string():
    client = _client_with_response(200, json_body={"choices": [{"message": {"content": None}}]})

    with pytest.raises(AkamaiApiError):
        chat_complete([{"role": "user", "content": "hi"}], config=FAKE_CONFIG, client=client)


def test_chat_complete_raises_on_non_json_200_response():
    client = _client_with_response(200, text_body="<html>not json</html>")

    with pytest.raises(AkamaiApiError):
        chat_complete([{"role": "user", "content": "hi"}], config=FAKE_CONFIG, client=client)


def test_chat_complete_uses_default_timeout_when_no_client_given(monkeypatch):
    captured_kwargs = {}

    class _FakeClient:
        def __init__(self, **kwargs):
            captured_kwargs.update(kwargs)

        def post(self, url, headers=None, json=None):
            return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

        def close(self):
            pass

    monkeypatch.setattr("app.akamai_client.httpx.Client", _FakeClient)

    chat_complete([{"role": "user", "content": "hi"}], config=FAKE_CONFIG)

    assert captured_kwargs.get("timeout") == DEFAULT_REQUEST_TIMEOUT_SECONDS


def _captured_body(**kwargs) -> dict:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["json"] = json.loads(request.content)
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    chat_complete([{"role": "user", "content": "hi"}], config=FAKE_CONFIG, client=httpx.Client(transport=httpx.MockTransport(handler)), **kwargs)
    return captured["json"]


def test_chat_complete_defaults_to_temperature_zero_and_fixed_seed():
    body = _captured_body()

    assert body["temperature"] == 0.0
    assert body["seed"] == 0


def test_chat_complete_sends_json_schema_response_format():
    schema = {"type": "object"}

    assert _captured_body(response_schema=schema)["response_format"] == {"type": "json_schema", "json_schema": {"name": "response", "schema": schema, "strict": True}}


def test_chat_complete_omits_response_format_without_schema():
    assert "response_format" not in _captured_body()


def test_chat_complete_asks_for_enough_output_tokens():
    assert _captured_body()["max_tokens"] == 4096


def test_chat_complete_raises_when_the_reply_was_cut_off():
    client = _client_with_response(200, json_body={"choices": [{"message": {"content": '{"a": "trunc'}, "finish_reason": "length"}]})

    with pytest.raises(AkamaiApiError, match="cut off"):
        chat_complete([{"role": "user", "content": "hi"}], config=FAKE_CONFIG, client=client)


def test_both_model_calls_fit_in_a_five_minute_serverless_function():
    assert DEFAULT_REQUEST_TIMEOUT_SECONDS == 140.0
