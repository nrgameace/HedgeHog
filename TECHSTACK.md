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
- **Hosting**: Vercel
- **Linting**: oxlint (bundled by the Vite template)
- **Charts**: Recharts
- **Navigation**: no router — `App.tsx` holds the current screen in
  React state (fits the no-persistence flow; no Vercel rewrites needed)
- **Mock vs. real backend**: `VITE_USE_MOCK_API` (default mock) and
  `VITE_API_URL` (default `http://localhost:8000`); see
  `frontend/.env.example`

## Frontend ↔ backend contract: `POST /analyze`
- Request: `multipart/form-data` with
  - `answers` — JSON string, all free text (optional ones may be `""`):
    `{"businessDescription", "customers", "location",
    "operationalDependencies", "keyMaterials", "pastImpacts",
    "timeOfYear", "lockedInCosts", "riskBudget"}`. None are required yet (simulated
    data), so any may be `""`. Earnings/costs come from the CSV, not here.
    `lockedInCosts` lists things already protected — don't hedge them.
    `riskBudget` is free text like "$800 a month"; size total bets to it
    (the mock reads the first amount as monthly, "a year" ÷ 12).
  - `financials` — the uploaded CSV file, **optional** for now (any
    columns; frontend caps it at 5 MB). Omitted when the user skips it.
- Response: JSON matching `HedgeReport` in `frontend/src/types.ts`:
  `{"bets": [{risk: {factor, explanation}, market, ticker,
  side: "YES"|"NO", amountUsd (stake per trade), frequency (label),
  tradeMonths (0=Jan), rationale, monthlyNetUsd (12 values: payouts minus
  stakes)}], "profitSeries": [{period, expected, actual}],
  "simulatedPeriod"}`. The frontend derives totals and variance
  mitigation from these.

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
  2. **Position sizing** — not built yet. Given a hedgeable category,
     decide which Kalshi market/position to bet on and how much (uses
     `riskBudget` to size total bets).

## External APIs
- **Kalshi API**: real API calls for live market data. Trade placement
  is simulated/paper for the hackathon demo — no real money moves, no
  production trading keys needed yet.

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
  frontend should stay on `MOCK_API` until that lands.
- 2026-10-10 — `chat_complete`'s blocking `httpx` call is run via
  FastAPI's `run_in_threadpool` from the async `/analyze` route, so one
  slow model call doesn't stall the event loop for other requests.
  Upstream errors are mapped to client-facing status codes
  (`AkamaiConfigError`→500, `AkamaiApiError`/`TrendDetectionError`→502)
  without leaking the raw upstream error body to the client.
