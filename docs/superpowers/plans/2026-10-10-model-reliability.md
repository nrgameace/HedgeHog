# Model Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every real risk the business faces reaches the results page, either as a trade or as "no Kalshi market for this yet". The same inputs give the same plan, and the model can't skip a risk, invent a ticker, pick the wrong city or reply with broken JSON.

**Architecture:**
- **Model 1:** gets a pre-computed evidence digest instead of 200 raw CSV rows. It returns every plausible factor with a 0–100 `confidence` and a `market_family` from a fixed list, enforced by a JSON schema. The backend keeps factors with confidence ≥ 20.
- **Candidate markets:** the backend fetches only the Kalshi series matching those families. Weather series are limited to the business's city, and dropped if no market exists for that city.
- **Model 2:** must answer every factor, also enforced by a JSON schema. Each factor gets a ticker chosen from that factor's own candidates, or `"NONE"`.
- **Unhedged risks:** factors with no market, or answered `NONE`, become `unhedgedRisks`, each with a reason, and the results page lists them.
- **Both calls:** temperature 0 and seed 0.

**Tech Stack:** FastAPI/pytest; React 19/Vitest. The vLLM endpoint supports `response_format: {"type": "json_schema", …}` (verified live 2026-10-10).

**Spec:** Design approved by the user in chat on 2026-10-10:
- confidence > 20%;
- leave weather out when the city has no market;
- explain risks with no Kalshi market on the results page;
- implement the schema, filtering, determinism and evidence-digest ideas;
- add `vercel.json`.

## Global Constraints
- One-line function signatures; TDD for all code; no Claude trailers in commits.
- Backend tests: `cd backend && ./venv/bin/pytest -q`. Frontend tests: `cd frontend && npx vitest run && npx tsc -b`.
- `MIN_CATEGORY_CONFIDENCE = 20`. A factor is kept when its confidence is ≥ 20.
- `MAX_CATEGORIES = 10`.
- Market families, in exactly this order: `rain, heat, gas, oil, inflation, food_prices, interest_rates, jobs, economy, none`.
- Cities: `austin, nyc, chicago, los_angeles, miami, san_francisco, seattle`, matched from the location text with word boundaries.

| Reason code | Text shown on the results page |
|---|---|
| `no_market` | "Kalshi doesn't list a market for this yet." |
| `no_city_market` | "Kalshi only lists weather markets for Austin, New York, Chicago, Los Angeles, Miami, San Francisco and Seattle." |
| `no_fit` | "None of the open Kalshi markets fit this risk closely enough." |
| `duplicate` | "Already covered by the {label} trade." |

## Review Focus
1. Model 1 returns duplicate slugs → dedupe them (keep the first), because Model 2's schema keys on the slug.
2. Every factor has family `none`, or the city has no market → Model 2 is not called, and every factor appears in `unhedgedRisks`.
3. Kalshi is down → the fallback list is filtered to the same series, so the candidate set is consistent.
4. Model 2 gives a malformed entry despite the schema → that factor becomes unhedged (`no_fit`). Never a 500.
5. A location that mentions two cities, or "LA" inside a word like "Atlanta" → word-boundary matching, first city found.

---

### Task 1: Deterministic, schema-enforced model calls
**Files:** `backend/app/akamai_client.py`, `backend/tests/test_akamai_client.py`

**Interface:** `chat_complete(messages, *, temperature: float = 0.0, response_schema: dict | None = None, config=None, client=None) -> str`
- The body always includes `"seed": 0`.
- When a schema is given, the body adds `"response_format": {"type": "json_schema", "json_schema": {"name": "response", "schema": <schema>, "strict": True}}`.

- [ ] Tests:
  - `test_chat_complete_defaults_to_temperature_zero_and_fixed_seed`
  - `test_chat_complete_sends_json_schema_response_format`
  - `test_chat_complete_omits_response_format_without_schema`

  Each captures the request body via `httpx.MockTransport`. Watch them fail, implement, watch them pass, then commit.

### Task 2: Market families, cities and filtered candidates
**Files:** `backend/app/market_catalog.py`, `backend/tests/test_market_catalog.py`

**Interfaces:**
- `MARKET_FAMILIES: tuple[str, ...]`
- `@dataclass SeriesInfo(ticker: str, family: str, city: str | None)`
- `SERIES: tuple[SeriesInfo, ...]`. These are the same 21 series as before:
  - rain series → family `rain` with their city;
  - `KXHIGH*` → family `heat` with their city;
  - `KXAAAGASM` → `gas`; `KXWTI` → `oil`; `KXCPI` → `inflation`; `KXEGGS` → `food_prices`;
  - `KXFED` and `KXFEDDECISION` → `interest_rates`;
  - `KXU3` and `KXPAYROLLS` → `jobs`; `KXGDP` → `economy`.
- `CITY_WEATHER_FAMILIES = {"rain", "heat"}`
- `match_city(location: str) -> str | None`. Alias lists:
  - austin: "austin"
  - nyc: "new york", "nyc", "manhattan", "brooklyn"
  - chicago: "chicago"
  - los_angeles: "los angeles", "la"
  - miami: "miami"
  - san_francisco: "san francisco", "sf", "bay area"
  - seattle: "seattle"

  Match is case-insensitive with `\b` boundaries; the earliest match in the text wins.
- `series_for(families: set[str], city: str | None) -> list[str]`. Series whose family is in `families`; for weather families, only when `series.city == city`.
- `family_of(ticker: str) -> str | None`, via the ticker's series prefix.
- `load_candidate_markets(series_tickers: list[str], client=None, deadline_seconds=…) -> list[KalshiMarket]`. Fetches only those series. The fallback is `FALLBACK_MARKETS` filtered to those series. An empty `series_tickers` gives `[]`.
- `SERIES_TICKERS` is removed (old code).

- [ ] Tests:
  - `match_city`: "Austin, TX" → austin; "Brooklyn, NY" → nyc; "Atlanta, GA" → None; "LA" → los_angeles; "Denver" → None
  - `series_for({"rain","gas"}, "austin") == ["KXRAINAUSM", "KXAAAGASM"]`
  - `series_for({"rain"}, None) == []`
  - `family_of("KXRAINAUSM-26OCT-4") == "rain"`; `family_of("BOGUS") is None`
  - Update the existing load tests to pass series lists.
  - The fallback is filtered to the requested series.
  - `[]` series → `[]` with no HTTP calls.

  RED, GREEN, commit.

### Task 3: Evidence digest
**Files:** create `backend/app/evidence.py`, `backend/tests/test_evidence.py`; modify `backend/app/financial_history.py` (expose helpers)

**Interfaces:**
- `financial_history`: rename `_find_column`, `_parse_month` and `_parse_amount` to public `find_column`, `parse_month` and `parse_amount`. Export `MONTH_COLUMNS` and `PROFIT_COLUMNS`.
- `worst_months(rows, limit: int = 6) -> list[str]`. Every month that has a "normal" (the same-month mean of the other years) is ranked by its shortfall. Each line reads `"2024-05: profit 4,724 vs normal 13,097 (−64%) — Rainiest May…"`, with the note only if present.
- `notes_timeline(rows) -> list[str]`. Each line reads `"YYYY-MM: note"`, oldest first.
- `column_swings(rows, limit: int = 12) -> list[str]`, over the numeric columns other than the month and notes columns.
  - Each line reads `"fuel_cost_per_gallon: low 1.95 (2016-01), high 4.85 (2022-06), latest 3.10 (2026-09)"`.
  - Lines are ranked by `(max − min) / max(|mean|, 1)`, largest first.
  - A column with fewer than 2 numeric values is skipped.
- `build_evidence_digest(rows) -> str`. Three titled sections: "Worst months vs. a normal year", "Owner's notes", "Biggest swings by column". A section with nothing in it reads "(none)".

- [ ] Tests:
  - On the Two Scoops CSV, `worst_months` contains a `2024-05` line with "Rainiest May".
  - `notes_timeline` starts with the `2016-01` note.
  - `column_swings` includes `fuel_cost_per_gallon` with `high 4.85`. Read the real max in the test.
  - Each section reads `(none)` for rows without notes.
  - Numeric parsing reuses `parse_amount`.

  RED, GREEN, commit.

### Task 4: Model 1 — every factor, confidence, family, schema
**Files:** `backend/app/trend_detection.py`, `backend/app/prompts.py`, the tests, and `tests/sample_data.py`

**Interfaces:**
- `HedgeableCategory(category, label, reasoning, confidence: int, market_family: str)`
- `TREND_DETECTION_SCHEMA: dict`. Its items require `category`, `label`, `reasoning`, `confidence` (integer, 0–100) and `market_family` (enum `MARKET_FAMILIES`), with `maxItems` set to `MAX_CATEGORIES`.
- `detect_hedgeable_categories` calls `chat_complete(messages, response_schema=TREND_DETECTION_SCHEMA)`. It parses the reply, drops confidence < 20, dedupes slugs (keeping the first), and sorts by confidence, highest first.
- The prompt asks for **every** factor that could plausibly affect revenue or costs (up to 10), each with an honest confidence and the closest market family (`none` if no family fits). It still excludes locked-in costs. The user message sends `build_evidence_digest(rows)` plus the **last 24 rows** of the CSV, instead of the first 200.

- [ ] Tests:
  - `test_drops_low_confidence_categories` (19 dropped, 20 kept)
  - `test_sorts_by_confidence`
  - `test_dedupes_slugs`
  - `test_sends_schema` (the fake `chat_complete` captures `response_schema`)
  - `test_rejects_unknown_family`
  - Prompt tests: the digest headings appear; only the last 24 rows are sent.
  - Update the existing fixtures with confidence and family.

  RED, GREEN, commit.

### Task 5: Model 2 — must answer every factor
**Files:** `backend/app/position_sizing.py`, `backend/app/prompts.py`, the tests

**Interfaces:**
- `@dataclass UnhedgedRisk(category: str, reason: str)`. `reason` is one of the codes in the table above.
- `@dataclass SizingResult(bets: list[PlannedBet], unhedged: list[UnhedgedRisk])`
- `candidates_by_category(categories, markets) -> dict[str, list[KalshiMarket]]` (by `family_of`)
- `position_sizing_schema(candidates: dict[str, list[KalshiMarket]]) -> dict`. Its `{"plans": {slug: {...}}}` requires every slug. For each slug, `ticker` is an enum of that slug's tickers plus `"NONE"`. The other fields: `side` is an enum YES/NO; `amountUsd` is an integer ≥ 1; `tradeMonths` and `hitMonths` are arrays of integers 0–11; `frequency`, `riskExplanation` and `rationale` are strings.
- `plan_positions(answers, categories, history, notes, candidates: dict[str, list[KalshiMarket]], *, config=None, client=None) -> SizingResult`. Only categories with at least 1 candidate are sent. Per slug:
  - `NONE` or an invalid entry → `UnhedgedRisk(slug, "no_fit")`
  - a ticker already used → `UnhedgedRisk(slug, "duplicate:<label of first>")`
  - otherwise a `PlannedBet`, with the existing month and amount rules
- The prompt:
  - groups candidates under each factor;
  - says "answer every factor; use NONE only if no candidate tracks it";
  - says "the backend scales stakes to the budget, so never drop a factor to save money";
  - keeps the recurring-series guidance.

- [ ] Tests:
  - `NONE` → unhedged `no_fit`
  - a missing slug → `no_fit`
  - a duplicate ticker → `duplicate`
  - `test_schema_requires_every_category_and_limits_tickers_per_category`
  - the existing validation tests adapted

  RED, GREEN, commit.

### Task 6: Pipeline + report `unhedgedRisks`
**Files:** `backend/app/pipeline.py`, `backend/app/hedge_report.py`, the tests

The pipeline:
1. Build the history.
2. Get the categories.
3. Compute `city = match_city(answers.location)`.
4. Load `markets = load_candidate_markets(series_for({c.market_family for c in categories}, city))`.
5. Build `candidates = candidates_by_category(...)`.
6. Mark the no-candidate categories unhedged:
   - `no_city_market` if the family is rain or heat and `city` is None;
   - otherwise `no_market`.
7. Call `plan_positions` only if any category has candidates.
8. Scale to the budget.
9. Build the report.

**The report** adds `"unhedgedRisks": [{"factor": label, "explanation": reasoning, "reason": <text from the table, with {label} filled in>}]`, in category (confidence) order.

- [ ] Tests:
  - `test_weather_outside_supported_cities_is_unhedged_with_city_reason`
  - `test_family_none_is_unhedged_without_calling_sizing`
  - `test_passes_only_matching_candidates_to_sizing`
  - the report tests for the reason texts

  RED, GREEN, commit.

### Task 7: Frontend shows risks without a market
**Files:** `frontend/src/types.ts`, `frontend/src/pages/ResultsPage.tsx` (+ test), `frontend/src/api/twoScoopsReport.ts` (+ test), `frontend/src/App.css`

**Interfaces:**
- `export type UnhedgedRisk = { factor: string; explanation: string; reason: string }`
- `HedgeReport.unhedgedRisks: UnhedgedRisk[]`
- The mock returns `unhedgedRisks: []`.

`ResultsPage` renders, after the trades and chart (or after the empty-plan text), a section `<h2>Risks without a Kalshi market</h2>` when the list is non-empty. Each item shows the **factor** in bold, its explanation, and the reason in muted text. The empty-plan text changes when there are unhedged risks: "We found risks, but none have a matching Kalshi market yet."

- [ ] Tests:
  - the section renders its items
  - the section is hidden when empty
  - the empty-plan text with unhedged risks

  RED, GREEN, `tsc -b`, commit.

### Task 8: `vercel.json`, docs, live verification
- `vercel.json` at the repo root:
  - `installCommand: "cd frontend && npm ci"`
  - `buildCommand: "cd frontend && npm run build"`
  - `outputDirectory: "frontend/dist"`
  - `framework: "vite"`
- Docs: CLAUDE.md and TECHSTACK.md get the pipeline changes, deploy notes (`VITE_API_URL`, `ALLOWED_ORIGINS`, `VITE_USE_MOCK_API=true` until the backend is deployed) and decisions-log entries.
- [ ] Live: restart the backend. Run Two Scoops 3× and Quillstack once.
  - **Expected (Two Scoops):** identical bets across runs, an Austin rain bet trading in May–Jun, and no non-Austin weather tickers.
  - **Expected (Quillstack):** non-empty `unhedgedRisks` (e.g. GPU prices).
- [ ] Commit.
