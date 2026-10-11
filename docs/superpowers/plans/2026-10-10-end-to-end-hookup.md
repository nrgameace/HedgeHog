# End-to-End Hookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `POST /analyze` returns the full `HedgeReport` the frontend already renders, built from Model call 1 (trend detection) → live Kalshi markets → Model call 2 (position sizing) → a deterministic backtest on the uploaded CSV, and the frontend calls it by default.

**Architecture:** A new `app/pipeline.py` orchestrates focused modules: `financial_history` (profit series + notes from the CSV), `kalshi_client` + `market_catalog` (live candidate markets with a hardcoded fallback), `position_sizing` (Model call 2, fed Model call 1's categories), `backtest` (budget scaling + monthly net), and `hedge_report` (camelCase response). The route stays thin and runs the pipeline in a threadpool. The frontend flips to the real API by default, requires the CSV in real mode, and shows the backend's error `detail`.

**Tech Stack:** FastAPI, httpx (sync, in threadpool), pytest; React 19 + Vitest. Kalshi public API `https://api.elections.kalshi.com/trade-api/v2` (no auth).

**Spec:** No separate spec file. The decisions below were made with the user in chat on 2026-10-10 and are the spec.

## Design decisions (the spec)

1. **Kalshi data:** live from Kalshi's public `GET /markets?series_ticker=<S>&status=open&limit=20`, for a curated list of series. If the live fetch yields **zero** candidates in total, use a hardcoded fallback catalog so the demo never breaks.
2. **Backtest hits:** Model call 2 returns, per bet, the months of the simulated year in which the event happened (`hitMonths`), grounded in the CSV's `notes` and profit dips. The backend computes payouts deterministically: `payout = round(amountUsd / price)` in hit months, minus `amountUsd` in trade months (same formula as `frontend/src/api/twoScoopsReport.ts`'s `simulate`).
3. **Profit series:** detected automatically from the CSV. The CSV is **required** in real mode (400 if missing or unusable).
4. **Simulated year:** the **complete** calendar year (all 12 months present) with the largest shortfall below "expected", where expected for month *m* = mean profit for month *m* across all *other* years that have it (if no other year has it, expected = actual). Shortfall = RMS of `max(expected − actual, 0)` (the same measure as `frontend/src/report/tradeImpact.ts`). Ties go to the most recent year. Picks 2024 for Two Scoops and 2025 for Quillstack.
5. **Frontend default:** real API. `VITE_USE_MOCK_API=true` opts back into the Two Scoops mock, which stays for tests and offline demos.
6. **Data flow between the model calls:** Model call 1's `HedgeableCategory` list goes **into** Model call 2's prompt. Each bet returned by call 2 must name one of those `category` slugs, and the bet's `risk.factor` is that category's `label`.

## Global Constraints

- Function/method signatures on **one line** (global CLAUDE.md).
- TDD: every task writes failing tests first. Backend: `cd backend && ./venv/bin/pytest` (project uses `venv`, not conda: see TECHSTACK.md). Frontend: `cd frontend && npx vitest run`.
- No `Co-Authored-By` or any Claude trailer in commits (user memory).
- Response JSON is camelCase and matches `HedgeReport` in `frontend/src/types.ts` exactly; `frontend/src/types.ts` does not change.
- Month indexes are 0 = Jan … 11 = Dec everywhere.
- Period labels are `["Jan","Feb",…,"Dec"]`; `simulatedPeriod` is the year as a string, e.g. `"2024"`.
- Kalshi request timeout: 5 s per series; a failing series is skipped, not fatal.
- Candidate filter: keep markets with `0.03 <= yes_price <= 0.97`, max **5 per series**. Price comes from `yes_ask_dollars` (string → float).
- Price used for payout: `yes_price` for side YES, `1 - yes_price` for side NO.
- Model call 2 temperature 0.2, same `chat_complete` as call 1.
- Remove old code: `{"hedgeable_categories": …}` response shape and its tests go away.

## Review Focus

1. **Model picks a ticker not in the candidate list, an unknown category, duplicate tickers, or months outside 0–11** → drop that bet (or the bad months); never 500. Duplicate tickers would also break React's `key={bet.ticker}`. Owned by Task 5.
2. **CSV whose month column is `date` (`2026-01-01`) or whose profit column is `net_income`/`profit`, or has blank/`$1,234` profit cells** → still detected; unparsable rows skipped. Owned by Task 1.
3. **CSV with no complete calendar year (e.g. 8 months)** → 400 with a readable message, which the frontend shows. Owned by Tasks 1, 7, 8.
4. **Kalshi down / slow** → fallback catalog, demo still works. Owned by Task 3.
5. **Model call 1 returns zero categories** → skip Model call 2 and return `bets: []` with the profit series; the results page shows its existing "No clear hedges found" text. Owned by Task 6.

---

## File structure

Backend (`backend/app/`):
- `model_json.py` (new): `parse_model_json(reply: str) -> object`. Strips fences and runs `json.loads`, raising `ValueError`. Shared by both model calls (DRY: moves `_strip_markdown_fence` out of `trend_detection.py`).
- `financial_history.py` (new): the profit series and monthly notes from CSV rows.
- `kalshi_client.py` (new): the HTTP fetch and parse of one series.
- `market_catalog.py` (new): the series list, fallback markets and `load_candidate_markets`.
- `risk_budget.py` (new): turns a free-text budget into a monthly dollar amount.
- `backtest.py` (new): budget scaling and monthly net.
- `prompts.py` (modify): adds the position-sizing prompt and builder.
- `position_sizing.py` (new): Model call 2 and reply validation.
- `hedge_report.py` (new): builds the camelCase `HedgeReport` dict.
- `pipeline.py` (new): `run_analysis` orchestration.
- `routes/analyze.py`, `main.py` (modify): the route and CORS.

Frontend (`frontend/src/`): `api/client.ts`, `App.tsx`, `pages/QuestionnairePage.tsx`, `csv/validateFinancialsFile.ts`, `frontend/.env.example` (+ tests).

---

### Task 1: Financial history from the CSV

**Files:**
- Create: `backend/app/financial_history.py`
- Test: `backend/tests/test_financial_history.py`

**Interfaces:**
- Produces:
  - `@dataclass ProfitPoint: period: str; expected: int; actual: int`
  - `@dataclass ProfitHistory: simulated_year: int; points: list[ProfitPoint]` (always 12 points, Jan..Dec)
  - `class FinancialHistoryError(Exception)`
  - `build_profit_history(rows: list[dict[str, str]]) -> ProfitHistory`
  - `monthly_notes(rows: list[dict[str, str]], year: int) -> dict[int, str]` (month index → non-empty `notes` text; `{}` if there's no `notes` column)
  - `MONTH_LABELS: list[str]` (Jan..Dec, reused by `hedge_report`)

Rules: the month column is the first of `month`, `date`, `period` present (case-insensitive), parsed as `YYYY-MM` or `YYYY-MM-DD`. The profit column is the first of `operating_income`, `net_income`, `profit`, `gross_profit` present (case-insensitive). Profit cells are parsed after stripping `$`, `,` and spaces; rows with an unparsable month or profit are skipped. Expected/actual are rounded to int. The year choice follows Design decision 4.

- [ ] **Step 1: Write failing tests**, using small inline row lists plus the real demo CSVs (read `../demo-data/...` via `parse_csv_rows`):
  - `test_two_scoops_simulates_2024`: `build_profit_history(two_scoops_rows).simulated_year == 2024`, `points[4] == ProfitPoint("May", <mean of May in all other years, rounded>, 4724)` (compute the expected value in the test from the rows, don't hardcode it).
  - `test_quillstack_simulates_2025`: `simulated_year == 2025`.
  - `test_detects_date_column_and_net_income`: rows `{"date": "2023-01-01", "net_income": "$1,000"}…` → works.
  - `test_month_with_no_other_years_uses_actual_as_expected`.
  - `test_ties_pick_most_recent_year`: two identical complete years → the later one.
  - `test_skips_rows_with_blank_profit`.
  - `test_raises_without_month_column`, `test_raises_without_profit_column`, `test_raises_without_complete_year` (8 months only), `test_raises_on_empty_rows`. Each one raises `FinancialHistoryError` with a message that names the problem (e.g. `"no profit column"`).
  - `test_monthly_notes_returns_nonempty_notes_for_year`: Two Scoops 2024 → `{0: "Lease renewed at higher rent", 4: "Rainiest May…", 5: "Rain continues…", 9: …, 11: …}` (assert keys `{0, 4, 5, 9, 11}`).
  - `test_monthly_notes_without_notes_column_is_empty`.
- [ ] **Step 2:** Run `./venv/bin/pytest tests/test_financial_history.py -v`. They should fail with an ImportError.
- [ ] **Step 3:** Implement. Keep the helpers small: `_find_column(fieldnames, candidates)`, `_parse_month(text) -> tuple[int, int] | None`, `_parse_amount(text) -> float | None`, `_profit_by_year(rows) -> dict[int, dict[int, float]]`, `_expected_for(year, by_year) -> list[float]`, `_shortfall(expected, actual) -> float`.
- [ ] **Step 4:** Run the tests. They should pass.
- [ ] **Step 5:** Commit: `feat: derive simulated-year profit series and notes from financials CSV`.

---

### Task 2: Shared model-JSON parsing

**Files:**
- Create: `backend/app/model_json.py`, `backend/tests/test_model_json.py`
- Modify: `backend/app/trend_detection.py` (delete `_strip_markdown_fence`, use `parse_model_json`)

**Interfaces:**
- Produces: `parse_model_json(reply: str) -> object`. Raises `ValueError` on invalid JSON.

- [ ] **Step 1:** Tests: `test_parses_plain_json`, `test_strips_json_fence` (```` ```json\n{"a":1}\n``` ````), `test_strips_bare_fence`, `test_raises_value_error_on_garbage`.
- [ ] **Step 2:** Run them. They should fail.
- [ ] **Step 3:** Implement (move the fence-stripping logic from `trend_detection.py`). `trend_detection.detect_hedgeable_categories` catches `ValueError` and raises `TrendDetectionError`.
- [ ] **Step 4:** Run `./venv/bin/pytest`. Everything should pass, including the existing `test_trend_detection.py` (unchanged).
- [ ] **Step 5:** Commit: `refactor: share model JSON parsing between model calls`.

---

### Task 3: Kalshi client + market catalog

**Files:**
- Create: `backend/app/kalshi_client.py`, `backend/app/market_catalog.py`
- Test: `backend/tests/test_kalshi_client.py`, `backend/tests/test_market_catalog.py`

**Interfaces:**
- Produces:
  - `@dataclass KalshiMarket: ticker: str; title: str; subtitle: str; yes_price: float`
  - `KALSHI_API_BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"` (overridable by env `KALSHI_API_BASE_URL`; add it to `backend/.env.example`)
  - `class KalshiApiError(Exception)`
  - `fetch_open_markets(series_ticker: str, client: httpx.Client) -> list[KalshiMarket]`: `GET {base}/markets` with params `series_ticker`, `status=open`, `limit=20`; maps `ticker`, `title`, `yes_sub_title` → `subtitle` (default `""`), and `float(yes_ask_dollars)` → `yes_price`; skips markets missing fields; applies the candidate price filter and the 5-per-series cap. Non-200 status, transport error or bad JSON raise `KalshiApiError`.
  - `SERIES_TICKERS: tuple[str, ...]`, exactly: `KXRAINAUSM, KXRAINNYCM, KXRAINCHIM, KXRAINLAXM, KXRAINMIAM, KXRAINSFOM, KXRAINSEAM, KXHIGHAUS, KXHIGHNY, KXHIGHCHI, KXHIGHLAX, KXHIGHMIA, KXAAAGASM, KXWTI, KXCPI, KXEGGS, KXFED, KXFEDDECISION, KXU3, KXPAYROLLS, KXGDP` (all verified live on 2026-10-10).
  - `FALLBACK_MARKETS: list[KalshiMarket]`: one realistic market per series above (e.g. `KalshiMarket("KXRAINAUSM-26OCT-4", "Rain in Austin in Oct 2026?", "Above 4 inches", 0.20)`).
  - `load_candidate_markets(client: httpx.Client | None = None) -> list[KalshiMarket]`: fetches every series in `SERIES_TICKERS` with a 5 s client (owned and closed when not passed in), skips a series on `KalshiApiError`, and returns `FALLBACK_MARKETS` when the combined result is empty.

- [ ] **Step 1:** Tests with `httpx.Client(transport=httpx.MockTransport(handler))`:
  - `test_fetch_open_markets_maps_fields`: the handler asserts query params and returns 2 markets → the expected `KalshiMarket`s.
  - `test_fetch_filters_extreme_prices` (0.01 and 0.99 dropped), `test_fetch_caps_at_five_per_series`, `test_fetch_skips_market_missing_price`.
  - `test_fetch_raises_on_500`, `test_fetch_raises_on_transport_error`.
  - `test_load_candidates_skips_failing_series`: the handler returns 500 for `KXRAINAUSM` and one market for the rest → `len == len(SERIES_TICKERS) - 1`.
  - `test_load_candidates_falls_back_when_all_fail` → `== FALLBACK_MARKETS`.
  - `test_fallback_has_one_market_per_series`: the fallback tickers' series prefixes `== set(SERIES_TICKERS)`, and every price lies within the filter range.
- [ ] **Step 2:** Run them. They should fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run them. They should pass.
- [ ] **Step 5:** Commit: `feat: Kalshi public market client with fallback catalog`.

---

### Task 4: Risk budget parsing + backtest

**Files:**
- Create: `backend/app/risk_budget.py`, `backend/app/backtest.py`
- Test: `backend/tests/test_risk_budget.py`, `backend/tests/test_backtest.py`

**Interfaces:**
- Produces:
  - `parse_monthly_budget(text: str) -> float | None`: the first dollar amount in the text (`$500`, `500`, `$1,200`, `$2k` → 2000); divided by 12 if the text contains `year`/`annual`/`yr`; divided by 3 if it contains `quarter`; `None` if no number.
  - `monthly_stake_peak(bets: list[tuple[float, list[int]]]) -> float`: the max over months of the summed `amount` of bets trading that month.
  - `scale_amounts_to_budget(bets: list[tuple[float, list[int]]], monthly_budget: float | None) -> list[int]`: returns new integer amounts. Unchanged (rounded) when the budget is `None` or the peak ≤ budget; otherwise each amount × `budget / peak`, rounded, min 1.
  - `simulate_monthly_net(amount_usd: int, price: float, trade_months: list[int], hit_months: list[int]) -> list[int]`: 12 values; `round(amount_usd / price)` in hit months minus `amount_usd` in trade months.

- [ ] **Step 1:** Tests:
  - budget: `"$500 a month" → 500`, `"$6,000 a year" → 500`, `"$1,500 per quarter" → 500`, `"about 300" → 300`, `"$2k monthly" → 2000`, `"" → None`, `"not sure" → None`.
  - `simulate_monthly_net(400, 0.15, [3,4,5,8,9], [4,5])` `== [0,0,0,-400,2267,2267,0,0,-400,-400,0,0]`. This matches the Two Scoops rain trade in the mock.
  - `test_scale_leaves_amounts_under_budget`, `test_scale_shrinks_proportionally` (`[(400,[0]),(200,[0])]`, budget 300 → `[200,100]`), `test_scale_never_below_one`, `test_scale_none_budget`.
- [ ] **Step 2:** Run them. They should fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run them. They should pass.
- [ ] **Step 5:** Commit: `feat: risk budget parsing and deterministic trade backtest`.

---

### Task 5: Model call 2: position sizing

**Files:**
- Modify: `backend/app/prompts.py`, `backend/tests/test_prompts.py`
- Create: `backend/app/position_sizing.py`, `backend/tests/test_position_sizing.py`

**Interfaces:**
- Consumes: `HedgeableCategory` (trend_detection), `QuestionnaireAnswers`, `ProfitHistory` + `monthly_notes` output (Task 1), `KalshiMarket` (Task 3), `parse_model_json` (Task 2), `chat_complete`.
- Produces:
  - `build_position_sizing_messages(answers: QuestionnaireAnswers, categories: list[HedgeableCategory], history: ProfitHistory, notes: dict[int, str], markets: list[KalshiMarket]) -> list[dict[str, str]]`
  - `@dataclass PlannedBet: category: str; ticker: str; side: str; amount_usd: int; frequency: str; trade_months: list[int]; hit_months: list[int]; risk_explanation: str; rationale: str`
  - `class PositionSizingError(Exception)`
  - `plan_positions(answers: QuestionnaireAnswers, categories: list[HedgeableCategory], history: ProfitHistory, notes: dict[int, str], markets: list[KalshiMarket], *, config: AkamaiConfig | None = None, client: httpx.Client | None = None) -> list[PlannedBet]`

**Prompt content** (system prompt `POSITION_SIZING_SYSTEM_PROMPT`). It should tell the model it:
- is sizing paper hedges on Kalshi for the business,
- gets the hedgeable categories from the previous analysis step (it may only use those `category` slugs, and at most one bet per category),
- must choose `ticker`s only from the candidate list, picking the side that **pays out when the business is hurt**,
- must keep the total stake in any single month within the owner's risk budget,
- sets `tradeMonths` to the months of the year when the risk matters,
- sets `hitMonths` to the months of the simulated year (a subset of `tradeMonths`) when the event most likely happened, judged from the notes and profit shortfalls, and leaves them empty when there is no evidence,
- writes `riskExplanation` as one sentence on "what could hurt your profit" and `rationale` as one plain-English sentence.

The reply must be JSON only:
`{"bets": [{"category", "ticker", "side": "YES"|"NO", "amountUsd": int, "frequency": "<short label>", "tradeMonths": [int], "hitMonths": [int], "riskExplanation", "rationale"}]}`.

The user message lists the answers (location, time of year, locked-in costs, risk budget), the categories as `slug | label | reasoning`, the simulated year with 12 `Mon: expected / actual` lines plus their notes, and the candidates as `ticker | title — subtitle | YES price`.

**Validation in `plan_positions`.** Raise `PositionSizingError` only when the top-level shape is wrong: invalid JSON, or no `bets` list. **Drop** an individual bet (never raise) if:
- `category` is not one of the categories passed in,
- `ticker` is not one of the candidates,
- `ticker` duplicates an earlier bet,
- `side` is not `YES` or `NO`,
- `amountUsd` is not a positive number,
- the text fields are missing or empty,
- `tradeMonths` is empty after filtering.

Within a kept bet, filter months to ints in 0–11, dedupe and sort them, and then set `hit_months` to its intersection with `trade_months`.

- [ ] **Step 1:** Write tests.
  - Prompt tests in `test_prompts.py`: the messages include every category slug, every candidate ticker with its price, the simulated year, the May 2024 note, and the risk budget text.
  - In `test_position_sizing.py`, monkeypatch `app.position_sizing.chat_complete`:
    - `test_parses_valid_bet`
    - `test_drops_unknown_ticker`
    - `test_drops_unknown_category`
    - `test_drops_duplicate_ticker`
    - `test_drops_bad_side`
    - `test_drops_nonpositive_amount`
    - `test_filters_out_of_range_months`
    - `test_hit_months_limited_to_trade_months`
    - `test_raises_on_invalid_json`
    - `test_raises_on_missing_bets_key`
    - `test_strips_fences`
- [ ] **Step 2:** Run the tests. They should fail.
- [ ] **Step 3:** Implement. Use one `_parse_bet(item, category_slugs, tickers_by_name, seen) -> PlannedBet | None` helper.
- [ ] **Step 4:** Run the tests. They should pass.
- [ ] **Step 5:** Commit: `feat: position sizing model call fed by trend detection categories`.

---

### Task 6: Hedge report assembly + pipeline

**Files:**
- Create: `backend/app/hedge_report.py`, `backend/app/pipeline.py`
- Test: `backend/tests/test_hedge_report.py`, `backend/tests/test_pipeline.py`

**Interfaces:**
- Consumes: Tasks 1, 3, 4, 5 and `detect_hedgeable_categories`.
- Produces:
  - `build_hedge_report(categories: list[HedgeableCategory], bets: list[PlannedBet], markets: list[KalshiMarket], history: ProfitHistory) -> dict`. Each bet becomes `{"risk": {"factor": <category label>, "explanation": risk_explanation}, "market": f"{title} {subtitle}".strip(), "ticker", "side", "amountUsd", "frequency", "tradeMonths", "rationale", "monthlyNetUsd": simulate_monthly_net(amount, price_for_side, …)}`. Price for the side is `yes_price` for YES and `1 - yes_price` for NO. `"profitSeries"` is the history points as `{"period", "expected", "actual"}`, and `"simulatedPeriod"` is `str(history.simulated_year)`.
  - `run_analysis(answers: QuestionnaireAnswers, rows: list[dict[str, str]]) -> dict`. Steps in order:
    1. `history = build_profit_history(rows)` (fail fast, before any model call)
    2. `categories = detect_hedgeable_categories(answers, rows)`
    3. if `categories` is empty → return `build_hedge_report(categories, [], [], history)`
    4. `markets = load_candidate_markets()`
    5. `planned = plan_positions(answers, categories, history, monthly_notes(rows, history.simulated_year), markets)`
    6. scale the amounts with `scale_amounts_to_budget(..., parse_monthly_budget(answers.risk_budget))`, replacing each `PlannedBet.amount_usd` (via `dataclasses.replace`)
    7. `return build_hedge_report(categories, scaled, markets, history)`

- [ ] **Step 1:** Write tests.
  - `test_hedge_report.py`: builds the exact expected dict for one YES bet and one NO bet (the NO bet uses price `1 - yes_price`), with the profit series and period.
  - `test_pipeline.py`, monkeypatching `app.pipeline.detect_hedgeable_categories`, `load_candidate_markets` and `plan_positions`, with Two Scoops rows:
    - `test_passes_trend_categories_into_position_sizing`: asserts the fake `plan_positions` receives exactly the categories the fake detector returned.
    - `test_scales_bets_to_budget`: budget "$100 a month", one bet of 400 → `amountUsd == 100`.
    - `test_no_categories_skips_kalshi_and_sizing`: those fakes raise if called; the result has `bets == []` and 12 profit points.
    - `test_bad_csv_fails_before_model_calls`: the detector fake raises if called; expects `FinancialHistoryError`.
- [ ] **Step 2:** Run the tests. They should fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run the tests. They should pass.
- [ ] **Step 5:** Commit: `feat: analysis pipeline chaining trend detection into position sizing`.

---

### Task 7: `/analyze` returns the HedgeReport + CORS

**Files:**
- Modify: `backend/app/routes/analyze.py`, `backend/app/main.py`, `backend/tests/test_analyze.py`, `backend/tests/test_main.py`, `backend/.env.example`

**Interfaces:**
- Consumes: `run_analysis` (Task 6).
- Route: `financials` is now **required**. If missing, return 400 with detail `"Upload your financials CSV so we can simulate your trades."`. Then:
  - `run_analysis` runs via `run_in_threadpool`.
  - Error mapping: `FinancialHistoryError` → 400 with `str(exc)`; `AkamaiConfigError` → 500; `AkamaiApiError`, `TrendDetectionError` and `PositionSizingError` → 502, with the existing generic messages.
  - Returns the report dict.
- `main.py`: add `CORSMiddleware` with `allow_origins` from env `ALLOWED_ORIGINS` (comma-separated), defaulting to `http://localhost:5173`, and `allow_methods=["POST", "GET"]`. Add `ALLOWED_ORIGINS=http://localhost:5173` to `backend/.env.example`.

- [ ] **Step 1:** Rewrite `test_analyze.py` to monkeypatch `app.routes.analyze.run_analysis`, with these tests:
  - `test_analyze_returns_report`
  - `test_analyze_requires_financials` (400 plus the message)
  - `test_analyze_maps_financial_history_error_to_400` (detail passes through)
  - `test_position_sizing_error_maps_to_502`
  - the existing 413, invalid-answers and Akamai-error cases, kept
  - delete `test_analyze_accepts_missing_financials_file` and the `hedgeable_categories` assertions

  In `test_main.py`, add `test_cors_allows_frontend_origin`: an OPTIONS preflight from `http://localhost:5173` gets `access-control-allow-origin` back.
- [ ] **Step 2:** Run the tests. They should fail.
- [ ] **Step 3:** Implement.
- [ ] **Step 4:** Run `./venv/bin/pytest`. The whole suite should pass.
- [ ] **Step 5: Live smoke test.** Run uvicorn, then `curl -F answers=@<two-scoops answers json> -F financials=@../demo-data/two-scoops-creamery/financials.csv localhost:8000/analyze`. Expect 200, `simulatedPeriod == "2024"`, at least 1 bet with a real `KX…` ticker, and a rain bet with hits in May/Jun. Record the output in the task report.
- [ ] **Step 6:** Commit: `feat: /analyze returns full HedgeReport; add CORS`.

---

### Task 8: Frontend calls the real API

**Files:**
- Modify: `frontend/src/api/client.ts`, `frontend/src/api/client.test.ts`, `frontend/src/csv/validateFinancialsFile.ts` (+ test), `frontend/src/pages/QuestionnairePage.tsx` (+ test), `frontend/src/App.tsx` (+ test), `frontend/.env.example`, `.claude/launch.json`

**Interfaces:**
- `MOCK_API = import.meta.env.VITE_USE_MOCK_API === 'true'` (default **off**).
- `submitQuestionnaire`: on a non-OK response, throw `Error(detail)` when the body is JSON with a string `detail`; otherwise `Error("The analysis failed (status N).")`.
- `validateFinancialsFile(file: File | null, required: boolean): string | null`. When `required` is true and there's no file, it returns `'Upload your financials CSV so we can simulate your trades.'`.
- `QuestionnairePage` gets the prop `requireFinancials: boolean`, passes it to the validator, and the label reads "(CSV, max 5 MB)" or "(optional, CSV, max 5 MB)" accordingly. `App` passes `requireFinancials={!MOCK_API}`.
- `.env.example`: `VITE_USE_MOCK_API=false`, with a comment that `true` shows the Two Scoops mock.
- `.claude/launch.json`: add a `backend` configuration that runs `backend/venv/bin/uvicorn app.main:app --port 8000 --app-dir backend` on port 8000.

- [ ] **Step 1:** Write tests.
  - `client.test.ts`: `test throws backend detail message` (a 400 with `{"detail":"no profit column"}` rejects with `/no profit column/`); keep the 500 non-JSON case at `/500/`.
  - Validator: `required && null` → the message; `!required && null` → `null`.
  - `QuestionnairePage.test.tsx`: with `requireFinancials`, submitting without a file shows the message and doesn't call `submit`; without it, the submit goes through as today.
  - `App.test.tsx`: update for the new prop if needed.
- [ ] **Step 2:** Run `npx vitest run`. The new tests should fail.
- [ ] **Step 3:** Implement. Update the stale comments in `validateFinancialsFile.ts` and `QuestionnairePage.tsx` that say "optional while the app runs on simulated data".
- [ ] **Step 4:** Run `npx vitest run` and `npx tsc -b`. Both should pass.
- [ ] **Step 5: Browser check.** Start the `backend` and `frontend` previews, paste the Two Scoops demo answers, upload its CSV and submit. The results page should show live `KX…` tickers, "Net in 2024", and the chart. Take a screenshot.
- [ ] **Step 6:** Commit: `feat: frontend calls real /analyze by default and requires the CSV`.

---

### Task 9: Docs

**Files:** `CLAUDE.md` ("Current state": the pipeline is wired end to end; mock off by default; CSV required; the worst-year rule; the Kalshi live+fallback) and `TECHSTACK.md` (the contract: `financials` required; the Model call 2 section; Kalshi base URL/series/filters; `ALLOWED_ORIGINS`; a decisions-log entry for each Design decision 1–6; remove the "not built yet" lines). `README.md` gets the same only if it states the old status.

- [ ] **Step 1:** Edit the docs.
- [ ] **Step 2:** Run both test suites one final time. Both should be green.
- [ ] **Step 3:** Commit: `docs: record end-to-end pipeline, Kalshi integration and defaults`.
