# Akamai Trend Detection Call Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first of Hedgehog's two Akamai model calls — given a questionnaire submission (industry, owner-stated loss factors, parsed financials CSV rows), call the Akamai-hosted `hackathon-chat` model and return a structured list of hedgeable categories (e.g. weather, fuel prices, GPU prices).

**Architecture:** Three small, independently-testable modules: a generic Akamai HTTP client (`app/akamai_client.py`, mockable via `httpx.MockTransport`), a prompts-only module (`app/prompts.py`, the system prompt and message-building logic, kept separate so it's easy to read and tune), and an orchestration module (`app/trend_detection.py`) that wires the two together and parses the model's JSON reply into typed objects.

**Tech Stack:** httpx (already a dependency), python-dotenv (new), stdlib `csv`/`json`/`dataclasses`.

**Spec:** No separate spec file — bounded task designed in chat. Confirmed live against the real API during this conversation: `POST https://ws.akamai-workshops.com/v1/chat/completions` with `Authorization: Bearer <key>`, OpenAI-compatible request/response shape, served by vLLM running `Qwen/Qwen3.8-27B-FP8` (reasoning/thinking mode off by default — no `<think>` stripping needed). See [CLAUDE.md](../../../CLAUDE.md) for overall project context.

## Global Constraints

- All function/method declarations go on one line, however long (global coding rule).
- TDD required: write the failing test before the implementation for every step below.
- Automated tests are fully mocked — no test may make a real network call to Akamai. Live verification happens manually (as already done in this conversation), not via `pytest`.
- Sampling temperature for the categorization call: **0.2**.
- Financials inlined into the prompt are capped at the **first 200 rows**; if there are more, the prompt says so explicitly (e.g. "showing first 200 of 734 rows").
- Output schema (exact): `{"hedgeable_categories": [{"category": "<short_snake_case_slug>", "label": "<Human Readable Name>", "reasoning": "<grounded explanation>"}]}`, 1–5 categories.
- `backend/.env` holds `AKAMAI_API_BASE_URL`, `AKAMAI_API_KEY`, `AKAMAI_CHAT_MODEL` (already created, gitignored). `backend/.env.example` is the committed template (already created).
- Backend tests run via `cd backend && ./venv/bin/pytest`. New modules import as `from app....` (matches `pythonpath = .` in `backend/pytest.ini`).

## Review Focus

- Missing/empty required env var (`AKAMAI_API_KEY`, `AKAMAI_API_BASE_URL`, or `AKAMAI_CHAT_MODEL`) — must raise a clear, typed error naming the missing variable(s) at config-load time, not send a request with `Authorization: Bearer None` or crash with a raw `KeyError`.
- A non-200 response from Akamai (401 invalid credentials is a real, observed case from this session) — must raise a typed error carrying the status and response body, not propagate `httpx`'s raw exception or silently return a broken value.
- The model wrapping its JSON reply in a markdown code fence (common LLM behavior even when told not to) — must still parse successfully via defensive stripping, not raise a parse error on otherwise-valid fenced JSON.
- The model returning malformed JSON, non-JSON prose, or JSON missing required fields — must raise a typed error with a clear message, not an unhandled `json.JSONDecodeError` or `KeyError`.
- A financials list longer than the 200-row cap — must truncate with an explicit "showing first N of M rows" note in the prompt, not silently drop the note (which would make the model think it's seeing the whole dataset) or silently send everything (which risks blowing the context budget on a large upload).

---

### Task 1: Akamai HTTP client

**Files:**
- Create: `backend/app/akamai_client.py`
- Test: `backend/tests/test_akamai_client.py`
- Modify: `backend/requirements.txt` (add `python-dotenv`)

**Interfaces:**
- Produces: `AkamaiConfigError(Exception)`, `AkamaiApiError(Exception)`, `AkamaiConfig` (dataclass: `base_url: str`, `api_key: str`, `chat_model: str`, classmethod `from_env() -> AkamaiConfig`), and `chat_complete(messages: list[dict[str, str]], *, temperature: float = 0.2, config: AkamaiConfig | None = None, client: httpx.Client | None = None) -> str` in `app.akamai_client`. Tasks 2 and 3 import `AkamaiConfig` and `chat_complete` from here.

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ./venv/bin/pytest tests/test_akamai_client.py -v`
Expected: FAIL / ERROR with "No module named 'app.akamai_client'"

- [ ] **Step 3: Add `python-dotenv` to `backend/requirements.txt` and install it**

Add a pinned line (e.g. `python-dotenv==1.0.1`, or the latest stable release at implementation time) to `backend/requirements.txt`, then run `cd backend && ./venv/bin/pip install -r requirements.txt`.

- [ ] **Step 4: Implement `backend/app/akamai_client.py`**

Call `load_dotenv()` (from `dotenv`) at module level so `backend/.env` is picked up when the app runs locally. Define `AkamaiConfigError` and `AkamaiApiError` as plain `Exception` subclasses. Define `AkamaiConfig` as a `@dataclass` with `base_url: str`, `api_key: str`, `chat_model: str`, and `from_env(cls) -> "AkamaiConfig"` that reads `AKAMAI_API_BASE_URL`, `AKAMAI_API_KEY`, `AKAMAI_CHAT_MODEL` via `os.environ.get`, collects the names of any that are missing or empty, and raises `AkamaiConfigError` naming all of them if any are missing — otherwise returns the populated `AkamaiConfig`. Implement `chat_complete(messages: list[dict[str, str]], *, temperature: float = 0.2, config: AkamaiConfig | None = None, client: httpx.Client | None = None) -> str:` that: resolves `config` via `AkamaiConfig.from_env()` if not passed, builds `url = f"{config.base_url}/chat/completions"`, POSTs `{"model": config.chat_model, "messages": messages, "temperature": temperature}` as JSON with header `Authorization: Bearer {config.api_key}` using `client` if provided else a freshly-created `httpx.Client()` (close it after use if created locally, e.g. via a `with` block or explicit `.close()`), raises `AkamaiApiError` with the status code and response text if the status is not 200, then parses the JSON body and raises `AkamaiApiError` if `choices[0].message.content` isn't present, otherwise returns that content string.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/pytest tests/test_akamai_client.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/akamai_client.py backend/tests/test_akamai_client.py backend/requirements.txt
git commit -m "feat: add Akamai chat completions HTTP client"
```

---

### Task 2: Trend detection prompts

**Files:**
- Create: `backend/app/prompts.py`
- Test: `backend/tests/test_prompts.py`

**Interfaces:**
- Consumes: nothing from Task 1 (this module has no HTTP dependency).
- Produces: `TREND_DETECTION_SYSTEM_PROMPT: str` and `build_trend_detection_messages(industry: str, loss_factors: str, financials: list[dict[str, str]]) -> list[dict[str, str]]` in `app.prompts`. Task 3 imports both.

- [ ] **Step 1: Write the failing tests**

```python
from app.prompts import TREND_DETECTION_SYSTEM_PROMPT, build_trend_detection_messages


def test_build_trend_detection_messages_starts_with_system_prompt():
    messages = build_trend_detection_messages("ice cream shop", "rainy days, gas prices", [])

    assert messages[0] == {"role": "system", "content": TREND_DETECTION_SYSTEM_PROMPT}


def test_build_trend_detection_messages_includes_industry_and_loss_factors():
    messages = build_trend_detection_messages("ice cream shop", "rainy days, gas prices", [])

    user_content = messages[1]["content"]
    assert "ice cream shop" in user_content
    assert "rainy days, gas prices" in user_content


def test_build_trend_detection_messages_includes_csv_rows():
    financials = [{"date": "2026-01-01", "revenue": "412.50"}]

    messages = build_trend_detection_messages("ice cream shop", "rainy days", financials)

    assert "412.50" in messages[1]["content"]


def test_build_trend_detection_messages_truncates_rows_over_200_with_a_note():
    financials = [{"date": f"2026-01-{i:03d}", "revenue": str(i)} for i in range(1, 251)]

    messages = build_trend_detection_messages("ice cream shop", "rainy days", financials)

    user_content = messages[1]["content"]
    assert "first 200 of 250 rows" in user_content
    assert financials[199]["date"] in user_content
    assert financials[200]["date"] not in user_content


def test_build_trend_detection_messages_no_truncation_note_under_cap():
    financials = [{"date": "2026-01-01", "revenue": "412.50"}]

    messages = build_trend_detection_messages("ice cream shop", "rainy days", financials)

    assert "first 200" not in messages[1]["content"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ./venv/bin/pytest tests/test_prompts.py -v`
Expected: FAIL / ERROR with "No module named 'app.prompts'"

- [ ] **Step 3: Implement `backend/app/prompts.py`**

Define `TREND_DETECTION_SYSTEM_PROMPT` as exactly this string:

```python
TREND_DETECTION_SYSTEM_PROMPT = """You are a financial risk analyst for Hedgehog, a tool that helps small business owners hedge against market volatility using prediction markets (Kalshi).

Given a business's industry, the factors the owner believes affect their revenue, and their recent financial data, identify which real-world categories of risk this business could hedge against.

A hedgeable category is a specific, publicly-tradeable real-world factor (for example: rain/weather, fuel prices, natural gas prices, livestock prices, GPU/semiconductor prices, interest rates, or a named sports team's win/loss record) that plausibly correlates with this business's revenue or costs, based on the evidence given. Only propose categories grounded in what the owner said or what the financial data shows a pattern for. Do not invent categories unrelated to the business or the data.

Respond with ONLY a single JSON object. No markdown code fences, no explanation before or after it. Match exactly this shape:

{"hedgeable_categories": [{"category": "<short_snake_case_slug>", "label": "<Human Readable Name>", "reasoning": "<one or two sentences grounded in the business's stated factors or financial data>"}]}

Return between 1 and 5 categories, ordered from most to least relevant. If the data gives no clear signal for a category, do not include it."""
```

Implement a module-private helper `_format_financials_csv(financials: list[dict[str, str]], max_rows: int = 200) -> str` that builds a CSV-formatted string (header + rows, via `csv.DictWriter` over an `io.StringIO`) from at most the first `max_rows` entries of `financials`, using the keys of the first row as the header (return an empty string if `financials` is empty). Implement `build_trend_detection_messages(industry: str, loss_factors: str, financials: list[dict[str, str]]) -> list[dict[str, str]]:` that returns `[{"role": "system", "content": TREND_DETECTION_SYSTEM_PROMPT}, {"role": "user", "content": <built>}]`, where the user content is an f-string containing the industry, loss factors, and the CSV text from `_format_financials_csv`, with a row-count line that reads `"Financial data (CSV, N rows):"` when `len(financials) <= 200`, or `"Financial data (CSV, showing first 200 of {len(financials)} rows):"` when it's over the cap.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/pytest tests/test_prompts.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/prompts.py backend/tests/test_prompts.py
git commit -m "feat: add trend detection prompts"
```

---

### Task 3: Trend detection orchestration

**Files:**
- Create: `backend/app/trend_detection.py`
- Test: `backend/tests/test_trend_detection.py`

**Interfaces:**
- Consumes: `build_trend_detection_messages(industry, loss_factors, financials) -> list[dict[str, str]]` from `app.prompts` (Task 2); `chat_complete(messages, *, temperature=0.2, config=None, client=None) -> str`, `AkamaiConfig`, `AkamaiApiError` from `app.akamai_client` (Task 1) — imported as `from app.akamai_client import chat_complete` so tests can `monkeypatch.setattr("app.trend_detection.chat_complete", fake)`.
- Produces: `HedgeableCategory` (dataclass: `category: str`, `label: str`, `reasoning: str`), `TrendDetectionError(Exception)`, and `detect_hedgeable_categories(industry: str, loss_factors: str, financials: list[dict[str, str]], *, config: "AkamaiConfig | None" = None, client: "httpx.Client | None" = None) -> list[HedgeableCategory]` in `app.trend_detection`. No later task in this plan consumes these, but they're the integration point for the future `/submissions` wiring.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from app.trend_detection import HedgeableCategory, TrendDetectionError, detect_hedgeable_categories

VALID_REPLY = '{"hedgeable_categories": [{"category": "rain", "label": "Rain", "reasoning": "Owner says rainy days hurt ice cream sales."}]}'


def test_detect_hedgeable_categories_parses_valid_response(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: VALID_REPLY)

    result = detect_hedgeable_categories("ice cream shop", "rainy days", [])

    assert result == [HedgeableCategory(category="rain", label="Rain", reasoning="Owner says rainy days hurt ice cream sales.")]


def test_detect_hedgeable_categories_strips_markdown_fences(monkeypatch):
    fenced = f"```json\n{VALID_REPLY}\n```"
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: fenced)

    result = detect_hedgeable_categories("ice cream shop", "rainy days", [])

    assert result == [HedgeableCategory(category="rain", label="Rain", reasoning="Owner says rainy days hurt ice cream sales.")]


def test_detect_hedgeable_categories_raises_on_invalid_json(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: "not json at all")

    with pytest.raises(TrendDetectionError):
        detect_hedgeable_categories("ice cream shop", "rainy days", [])


def test_detect_hedgeable_categories_raises_on_missing_top_level_key(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: '{"wrong_key": []}')

    with pytest.raises(TrendDetectionError):
        detect_hedgeable_categories("ice cream shop", "rainy days", [])


def test_detect_hedgeable_categories_raises_on_malformed_item(monkeypatch):
    monkeypatch.setattr("app.trend_detection.chat_complete", lambda *args, **kwargs: '{"hedgeable_categories": [{"category": "rain"}]}')

    with pytest.raises(TrendDetectionError):
        detect_hedgeable_categories("ice cream shop", "rainy days", [])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ./venv/bin/pytest tests/test_trend_detection.py -v`
Expected: FAIL / ERROR with "No module named 'app.trend_detection'"

- [ ] **Step 3: Implement `backend/app/trend_detection.py`**

Define `HedgeableCategory` as a `@dataclass` with `category: str`, `label: str`, `reasoning: str`. Define `TrendDetectionError(Exception)`. Implement `detect_hedgeable_categories(industry: str, loss_factors: str, financials: list[dict[str, str]], *, config: AkamaiConfig | None = None, client: httpx.Client | None = None) -> list[HedgeableCategory]:` that calls `build_trend_detection_messages(industry, loss_factors, financials)`, passes the result to `chat_complete(messages, temperature=0.2, config=config, client=client)`, strips a leading/trailing markdown code fence from the reply if present (e.g. a reply starting with ` ```json` or ` ``` ` and ending with ` ``` ` — strip the fence lines before parsing, not just backticks mid-string), parses the remainder with `json.loads` catching `json.JSONDecodeError` and re-raising as `TrendDetectionError`, checks for the `"hedgeable_categories"` key and raises `TrendDetectionError` if absent or not a list, and builds the `HedgeableCategory` list via `HedgeableCategory(**item)` for each entry, catching `TypeError` (raised when required dataclass fields are missing) and re-raising as `TrendDetectionError` naming the problem.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/pytest tests/test_trend_detection.py -v`
Expected: 5 passed

- [ ] **Step 5: Run the full backend suite**

Run: `cd backend && ./venv/bin/pytest -v`
Expected: all tests pass, including every test from the prior `questionaire-endpoint` work already on `main`.

- [ ] **Step 6: Commit**

```bash
git add backend/app/trend_detection.py backend/tests/test_trend_detection.py
git commit -m "feat: add trend detection orchestration (Akamai categorization call)"
```
