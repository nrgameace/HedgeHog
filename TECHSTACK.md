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
- Hosted on Akamai; the backend queries it over HTTP.
- Two sequential model calls per submission:
  1. **Trend detection** — given uploaded financials + stated risk
     factors, identify which trends are currently hedgeable.
  2. **Position sizing** — given a hedgeable trend, decide which Kalshi
     market/position to bet on and how much.
- Not yet decided: exact model(s)/provider behind these two calls.

## External APIs
- **Kalshi API**: real API calls for live market data. Trade placement
  is simulated/paper for the hackathon demo — no real money moves, no
  production trading keys needed yet.
  - **Market data is unauthenticated.** `GET /markets` returns 200 with
    no credentials (verified 2026-10-10), so the demo needs no API keys.
  - Base URLs: production `https://external-api.kalshi.com/trade-api/v2`,
    demo `https://external-api.demo.kalshi.co/trade-api/v2`. Credentials
    do not cross environments.
  - Auth, if order placement is ever added: headers `KALSHI-ACCESS-KEY`,
    `KALSHI-ACCESS-TIMESTAMP` (ms), `KALSHI-ACCESS-SIGNATURE` — base64 of
    a signature over `timestamp + METHOD + path` (query string excluded),
    RSA-PSS/SHA-256 or Ed25519.
  - **Response gotchas** (all seen in live responses, 2026-10-10):
    - Prices are **strings in dollars**, e.g. `yes_ask_dollars: "0.3400"`.
    - `status` can be `"active"`, which is not in the documented
      enum (`unopened/paused/open/closed/settled`) — don't hardcode
      `== "open"`.
    - `volume` and `liquidity` come back `null`; the populated fields are
      the fixed-point variants `volume_fp`, `volume_24h_fp`,
      `open_interest_fp`.
    - Multivariate combo markets (`KXMVE*`) appear in unfiltered results
      with degenerate books (`yes_bid "0.0000"` / `no_bid "1.0000"`).
      Pass `mve_filter=exclude` — they aren't single-factor events and
      would corrupt the sizing math.

## Decisions log
- 2026-10-10 — Frontend: Vite + React + TS over Next.js (simpler for a
  small SPA flow).
- 2026-10-10 — Backend: Python stdlib `venv` over conda (hackathon
  simplicity; overrides the global default).
- 2026-10-10 — No login/auth, no persistence: every visit re-collects
  the questionnaire + CSV instead of storing accounts/sessions.
- 2026-10-10 — TDD required for all code, frontend and backend.
- 2026-10-10 — All money and prices use `Decimal`, never `float`.
  Kalshi returns prices as strings; float arithmetic on contract counts
  in the thousands produces penny drift in the sizing math.
- 2026-10-10 — The LLM does not do arithmetic. Model calls return
  judgment in structured JSON (which market, which side, revenue impact
  as a *percentage*); every number shown to a user is computed by a pure,
  tested function in `backend/app/hedge/`. Keeps the math testable under
  the TDD rule and makes the model provider swappable.
- 2026-10-10 — Model-selected tickers are validated against the
  retrieved candidate set and dropped if unknown, so a hallucinated
  ticker can never reach a sizing calculation.
- 2026-10-10 — Sizing uses the **ask** price, not the mid, and caps
  contracts at resting book depth. On thin Kalshi markets the spread is a
  large fraction of a $1 contract, and sizing past the book makes the
  recommendation unfillable.
- Not yet decided: Kalshi fee schedule. `size_position()` takes
  `fee_per_contract` as a parameter rather than embedding a formula —
  pull the live schedule into one place before the demo.
