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

## Decisions log
- 2026-10-10 — Frontend: Vite + React + TS over Next.js (simpler for a
  small SPA flow).
- 2026-10-10 — Backend: Python stdlib `venv` over conda (hackathon
  simplicity; overrides the global default).
- 2026-10-10 — No login/auth, no persistence: every visit re-collects
  the questionnaire + CSV instead of storing accounts/sessions.
- 2026-10-10 — TDD required for all code, frontend and backend.
