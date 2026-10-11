# Tech Stack

Living record of concrete tech stack decisions for Hedgehog — tools,
versions, and why they were picked. Update this whenever a stack
decision is made or changed, so every teammate's Claude Code session
sees the same ground truth. Project context/flow lives in
[CLAUDE.md](CLAUDE.md); this file is stack specifics only.

## Frontend
- **Language/framework**: TypeScript + React 19
- **Scaffolding tool**: Vite (`react-ts` template) — chosen over Next.js
  because the app is a small 3-screen flow (home → questionnaire →
  results) that doesn't need file-based routing or SSR.
- **Testing**: Vitest + React Testing Library + jsdom
  - Setup file: `frontend/src/test/setup.ts` imports
    `@testing-library/jest-dom/vitest` (use this subpath, not the bare
    `@testing-library/jest-dom` import — it's the one that gives
    TypeScript the matcher types under Vitest 5.x)
  - Run: `cd frontend && npm run test` (or `npx vitest run`)
- **Hosting**: Vercel, configured by `vercel.json` at the repo root
  (`cd frontend && npm ci`, `cd frontend && npm run build`, output
  `frontend/dist`). Env vars on Vercel: `VITE_API_URL` (deployed backend)
  and `VITE_USE_MOCK_API=true` until the backend is live.
- **Linting**: oxlint (bundled by the Vite template)
- **Charts**: Recharts
- **Navigation**: no router — `App.tsx` holds the current screen in
  React state (fits the no-persistence flow; no Vercel rewrites needed)
- **Mock vs. real backend**: `VITE_USE_MOCK_API` (default **real
  backend**; `true` shows the simulated Two Scoops report) and
  `VITE_API_URL` (default `http://localhost:8000`); see
  `frontend/.env.example`

## Frontend ↔ backend contract: `POST /analyze`
- Request: `multipart/form-data` with
  - `answers` — JSON string, all free text (optional ones may be `""`):
    `{"businessDescription", "customers", "location",
    "operationalDependencies", "keyMaterials", "pastImpacts",
    "timeOfYear", "lockedInCosts", "riskBudget"}`. None are required, so
    any may be `""`. Earnings/costs come from the CSV, not here.
    `lockedInCosts` lists things already protected — don't hedge them.
    `riskBudget` is free text like "$800 a month"; the backend reads the
    first amount as monthly ("a year" ÷ 12, "a quarter" ÷ 3) and scales
    stakes so no month's total exceeds it.
  - `financials` — the uploaded CSV, **required** (400 if missing). Needs
    a month column (`month`/`date`/`period`; `YYYY-MM[-DD]`, `YYYY/MM` or `M/D/YYYY`) and a profit
    column (`operating_income`, `net_income`, `profit` or
    `gross_profit`), plus at least one complete calendar year; an
    optional `notes` column feeds Model call 2. Max 5 MB.
- Response: JSON matching `HedgeReport` in `frontend/src/types.ts`:
  `{"bets": [{risk: {factor, explanation}, market, ticker,
  side: "YES"|"NO", amountUsd (stake per trade), frequency (label),
  tradeMonths (0=Jan), rationale, monthlyNetUsd (12 values: payouts minus
  stakes)}], "profitSeries": [{period, expected, actual}],
  "simulatedPeriod"}`. The frontend derives totals and variance
  mitigation from these.
- Errors: 400 (bad answers, missing/unusable CSV — `detail` is shown to
  the user), 413 (CSV too big), 500 (Akamai misconfigured), 502 (model
  unavailable or replied in an unexpected shape; upstream details are
  never leaked).

## Backend
- **Language/framework**: Python + FastAPI
- **Virtual env**: Python's built-in `venv` module
  (`python3 -m venv backend/venv`) — **not** conda, despite the global
  CLAUDE.md default of a conda env named after the repo. Deliberate
  deviation for this project: simpler for a hackathon, no conda
  dependency required on teammates' machines.
- **Dependencies**: pinned in `backend/requirements.txt`
- **Testing**: pytest + httpx (via FastAPI's `TestClient`)
  - Config: `backend/pytest.ini` (sets `pythonpath = .` so `app` imports
    resolve from the repo root of `backend/`)
  - Run: `cd backend && ./venv/bin/pytest`
- **Hosting**: Akamai
- **CORS**: `ALLOWED_ORIGINS` env (comma-separated), default
  `http://localhost:5173`. Add the Vercel URL when deploying.
- **Run locally**: `.claude/launch.json` `backend` config (uvicorn on
  8000 with `--env-file backend/.env`), or `cd backend &&
  ./venv/bin/uvicorn app.main:app --reload`.

## Model / LLM
- Hosted on Akamai; the backend queries it over HTTP at
  `https://ws.akamai-workshops.com/v1` — OpenAI Chat Completions-
  compatible (`POST /chat/completions`, `Authorization: Bearer <key>`),
  served by vLLM running `Qwen/Qwen3.8-27B-FP8` (confirmed live;
  reasoning/thinking mode off by default, so no `<think>` stripping
  needed). Model names: `hackathon-chat` (text), `hackathon-image`
  (unused so far), `hackathon-embedding` (unused so far).
- Two sequential model calls per submission:
  1. **Trend detection** — **implemented** (`backend/app/trend_detection.py`,
     wired into `POST /analyze`). Given the 9 questionnaire answers +
     parsed financials CSV (capped at 200 rows in the prompt), returns
     1–5 hedgeable categories as `{category, label, reasoning}`.
     Temperature 0.2. Request timeout 60s.
  2. **Position sizing** — **implemented** (`backend/app/position_sizing.py`).
     Input: Model call 1's categories, the open Kalshi candidates
     (`ticker | title — subtitle | YES price`), the simulated year's 12
     months of expected/actual profit with CSV notes, and the answers
     (location, time of year, locked-in costs, budget). Output JSON:
     `{"bets": [{category, ticker, side, amountUsd, frequency,
     tradeMonths, hitMonths, riskExplanation, rationale}]}`. The prompt
     says each candidate stands for its recurring series, so trade months
     follow the business's risk season, not the contract's listed month.
     Temperature 0.2. Invalid bets are dropped, not fatal.
  - Shared: `app/model_json.py` strips code fences and parses replies for
    both calls.

## External APIs
- **Kalshi API**: public market data, no auth —
  `GET https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=<S>&status=open&limit=20`
  (base URL overridable with `KALSHI_API_BASE_URL`). Price = 
  `yes_ask_dollars`. Series offered (`app/market_catalog.py`): Austin,
  NYC, Chicago, LA, Miami, SF and Seattle monthly rain (`KXRAIN…M`); Austin,
  NYC, Chicago, LA and Miami daily highs (`KXHIGH…`); gas (`KXAAAGASM`),
  oil (`KXWTI`), CPI, eggs, Fed rate/decision, unemployment, payrolls and
  GDP. Up to 5 markets per series with YES price 0.03–0.97; series are
  fetched in parallel (5 s per request, 6 s overall deadline); a failing
  or late series is skipped; if all fail, a hardcoded
  fallback list is used. Trade placement is simulated/paper — no real
  money moves, no trading keys.

## Decisions log
- 2026-10-10 — Frontend: Vite + React + TS over Next.js (simpler for a
  small SPA flow).
- 2026-10-10 — Backend: Python stdlib `venv` over conda (hackathon
  simplicity; overrides the global default).
- 2026-10-10 — No login/auth, no persistence: every visit re-collects
  the questionnaire + CSV instead of storing accounts/sessions.
- 2026-10-10 — TDD required for all code, frontend and backend.
- 2026-10-10 — Frontend: screens in React state instead of a router;
  Recharts for the revenue chart; mock API on by default until
  `/analyze` exists.
- 2026-10-10 — Financials CSV: any shape accepted, only limit is 5 MB;
  optional until the backend exists (simulated data only for now).
- 2026-10-10 — Questionnaire has no suggested factors: owners type in
  whatever factors they believe impact them.
- 2026-10-10 — Added a 9th question, the monthly risk-mitigation budget,
  which caps total recommended bets; locked-in question reworded to give
  examples (fixed-price contracts, fixed-rate loans, long leases).
- 2026-10-10 — Questionnaire reworked to 8 free-text questions that find
  dependencies (business, customers, location, day-to-day reliance,
  key materials, past impacts, time of year, locked-in costs); expected
  earnings dropped because the CSV covers it.
- 2026-10-10 — North-star demo data in `demo-data/`: two fixed
  fictional businesses (ice cream shop, AI startup) with hand-built
  monthly CSVs and background stories. No generator, no randomness.
- 2026-10-10 — Backend `POST /analyze` built and wired to the real
  Akamai trend-detection call. Response is `{"hedgeable_categories":
  [...]}` only, not the full `HedgeReport` the frontend's contract
  documents above — position sizing and Kalshi aren't built yet, so the
  frontend should stay on `MOCK_API` until that lands (superseded by the end-to-end hookup below).
- 2026-10-10 — `chat_complete`'s blocking `httpx` call is run via
  FastAPI's `run_in_threadpool` from the async `/analyze` route, so one
  slow model call doesn't stall the event loop for other requests.
  Upstream errors are mapped to client-facing status codes
  (`AkamaiConfigError`→500, `AkamaiApiError`/`TrendDetectionError`→502)
  without leaking the raw upstream error body to the client.
- 2026-10-10 — End-to-end hookup: `/analyze` returns the full
  `HedgeReport`; frontend calls the real backend by default
  (`VITE_USE_MOCK_API=true` for the offline mock).
- 2026-10-10 — Kalshi candidates come live from the public API for a
  curated list of series, with a hardcoded fallback so the demo never
  breaks.
- 2026-10-10 — Model call 2 picks which months each trade paid out
  (grounded in CSV notes and profit dips); the backend computes payouts
  deterministically from stake and price.
- 2026-10-10 — The financials CSV is now required; the profit series is
  auto-detected from it.
- 2026-10-10 — Simulated year = the worst of the 3 most recent complete
  calendar years (worst of all years picked COVID 2020 for Two Scoops,
  which isn't hedgeable and lost the 2024 rain story).
- 2026-10-10 — Model call 1's categories are passed into Model call 2,
  and every bet must name one of them.
- 2026-10-10 — Model reliability: both calls JSON-schema enforced,
  temperature 0 + seed 0, `max_tokens` 4096 (the server truncated at
  512), 180 s timeout. Model 1 lists every factor with confidence (keep
  ≥ 20) and a market family; Model 2 must answer every factor from its
  own candidates or say NONE; unhedged risks are shown with a reason.
  Weather markets only for the owner's city. Model 1 gets an evidence
  digest + last 24 rows instead of 200 raw rows.
