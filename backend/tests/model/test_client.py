import httpx
import pytest

from app.model.client import ModelClient, ModelConfig, ModelError, client_from_env

CONFIG = ModelConfig(base_url="https://inference.example/v1", model="qwen-test")


def reply(content: str) -> dict:
    """An OpenAI-compatible chat completion, which is what Akamai's endpoint speaks."""
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def client(response: httpx.Response, recorder: list[httpx.Request] | None = None) -> ModelClient:
    def handler(request: httpx.Request) -> httpx.Response:
        if recorder is not None:
            recorder.append(request)
        return response

    return ModelClient(CONFIG, transport=httpx.MockTransport(handler))


def json_client(content: str, recorder: list[httpx.Request] | None = None) -> ModelClient:
    return client(httpx.Response(200, json=reply(content)), recorder)


class TestRequest:
    def test_posts_a_chat_completion_with_the_configured_model(self):
        seen: list[httpx.Request] = []

        json_client('{"ok": true}', seen).complete_json("be terse", "a question")

        assert seen[0].url.path.endswith("/chat/completions")
        assert seen[0].method == "POST"

    def test_sends_the_system_and_user_messages(self):
        import json

        seen: list[httpx.Request] = []

        json_client('{"ok": true}', seen).complete_json("be terse", "a question")
        body = json.loads(seen[0].content)

        assert body["model"] == "qwen-test"
        assert [message["role"] for message in body["messages"]] == ["system", "user"]
        assert body["messages"][1]["content"] == "a question"

    def test_omits_authorisation_when_no_key_is_configured(self):
        seen: list[httpx.Request] = []

        json_client('{"ok": true}', seen).complete_json("s", "u")

        assert "authorization" not in seen[0].headers

    def test_sends_a_bearer_token_when_a_key_is_configured(self):
        seen: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request)
            return httpx.Response(200, json=reply("{}"))

        keyed = ModelClient(
            ModelConfig(base_url=CONFIG.base_url, model="m", api_key="secret"),
            transport=httpx.MockTransport(handler),
        )
        keyed.complete_json("s", "u")

        assert seen[0].headers["authorization"] == "Bearer secret"


class TestResponseParsing:
    def test_parses_a_bare_json_object(self):
        assert json_client('{"terms": ["b200"]}').complete_json("s", "u") == {"terms": ["b200"]}

    def test_strips_a_markdown_code_fence(self):
        """Models routinely wrap JSON in fences even when told not to."""
        fenced = '```json\n{"terms": ["b200"]}\n```'

        assert json_client(fenced).complete_json("s", "u") == {"terms": ["b200"]}

    def test_strips_a_bare_code_fence(self):
        assert json_client('```\n{"a": 1}\n```').complete_json("s", "u") == {"a": 1}

    def test_tolerates_prose_around_the_object(self):
        chatty = 'Sure! Here is the mapping:\n{"terms": ["b200"]}\nHope that helps.'

        assert json_client(chatty).complete_json("s", "u") == {"terms": ["b200"]}

    def test_handles_nested_braces_in_the_object(self):
        assert json_client('{"a": {"b": 1}}').complete_json("s", "u") == {"a": {"b": 1}}


class TestErrors:
    def test_a_non_2xx_status_is_a_model_error(self):
        with pytest.raises(ModelError, match="503"):
            client(httpx.Response(503, text="overloaded")).complete_json("s", "u")

    def test_a_transport_failure_is_a_model_error(self):
        def explode(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("no route to host")

        api = ModelClient(CONFIG, transport=httpx.MockTransport(explode))

        with pytest.raises(ModelError):
            api.complete_json("s", "u")

    def test_a_response_without_choices_is_a_model_error(self):
        with pytest.raises(ModelError):
            client(httpx.Response(200, json={"choices": []})).complete_json("s", "u")

    def test_content_with_no_json_object_is_a_model_error(self):
        with pytest.raises(ModelError):
            json_client("I cannot help with that.").complete_json("s", "u")

    def test_malformed_json_in_the_content_is_a_model_error(self):
        with pytest.raises(ModelError):
            json_client('{"terms": [').complete_json("s", "u")

    def test_a_json_array_is_rejected_because_an_object_was_requested(self):
        with pytest.raises(ModelError):
            json_client('["b200"]').complete_json("s", "u")


class TestEnvironmentConfiguration:
    def test_mocked_by_default_so_nothing_calls_an_unconfigured_endpoint(self, monkeypatch):
        monkeypatch.delenv("MOCK_MODEL", raising=False)
        monkeypatch.setenv("MODEL_BASE_URL", "https://inference.example/v1")
        monkeypatch.setenv("MODEL_NAME", "qwen")

        assert client_from_env() is None

    def test_returns_none_when_the_endpoint_is_not_configured(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODEL", "false")
        monkeypatch.delenv("MODEL_BASE_URL", raising=False)
        monkeypatch.delenv("MODEL_NAME", raising=False)

        assert client_from_env() is None

    def test_builds_a_client_once_mocking_is_off_and_the_endpoint_is_set(self, monkeypatch):
        monkeypatch.setenv("MOCK_MODEL", "false")
        monkeypatch.setenv("MODEL_BASE_URL", "https://inference.example/v1")
        monkeypatch.setenv("MODEL_NAME", "qwen3-32b")
        monkeypatch.setenv("MODEL_API_KEY", "secret")

        api = client_from_env()

        assert api is not None
        assert api.config.model == "qwen3-32b"
        assert api.config.api_key == "secret"
