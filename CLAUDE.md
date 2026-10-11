# Hedgehog

This file is a living record of project context and keeps getting updated
as the project evolves. For concrete tech stack choices (languages,
frameworks, tools, versions, and why they were picked), see
[TECHSTACK.md](TECHSTACK.md) — that's the file to check/update when a
stack decision changes.

## What this is
Hedgehog lets small business owners hedge against market volatility that
affects their business, using Kalshi prediction markets. Example: an
ice cream shop owner bets that it will rain today. If it rains, the bet
pays out; if it doesn't, ice cream sales make up the difference. Either
way, revenue is more consistent.

Built for a weekend hackathon. Priority is a convincing end-to-end demo,
not production robustness. Mock data/services where real integration
would eat the weekend; prefer real calls (even against sandbox/paper
endpoints) wherever feasible without costing significant time.

## Architecture
- **Frontend**: TypeScript + React (`frontend/`), deployed on Vercel.
- **Deployment**: one Vercel project with two services (root `vercel.json`):
  `frontend` (Vite) public at `/`, `backend` (FastAPI) public at `/api/*`.
- **Backend**: FastAPI (Python) (`backend/`), deployed on Akamai.
- **LLM/model inference**: hosted on Akamai, called by the backend.
- **Kalshi API**: backend calls Kalshi's real API for live market data.
  Trade placement is simulated/paper for the demo — no real money moves.

See [TECHSTACK.md](TECHSTACK.md) for exact tools/versions.

## Core flow (no login, no persistence)
Every visit is stateless — there is no account system. Each session
starts fresh: the user answers the questionnaire and uploads financials
again; nothing is saved between visits.

1. **Homepage** — links straight into the questionnaire. No login screen.
2. **Questionnaire** — the owner answers free-text questions about how
   their company works: what it does, its customers, location, what it
   relies on day to day, the materials/services it uses most, what
   outside events have hurt it, which times of year matter, which costs
   are locked in at a set price, and how much budget they have for risk
   mitigation (sizes the bets). Nothing the financials CSV already reports
   (earnings, costs) is asked. They can attach a CSV of their financials.
3. **Submit** — triggers the backend pipeline:
   a. **Model call 1 — trend detection**: given the uploaded financials
      and stated risk factors, identify which trends are currently
      "hedgeable" (e.g. gas prices have been rising).
   b. **Model call 2 — position sizing**: given a hedgeable trend,
      decide which Kalshi market to bet on, which position, and how
      much.
4. **Results page (dashboard)** — shown immediately after submit, in
   the same session: personalized view of the submitted company's
   concerns, the recommended/placed Kalshi bets, and proof-of-concept
   graphs showing hedged vs. unhedged revenue volatility.

## Current state
Wired end to end: the frontend calls the real backend by default, and
`POST /api/analyze` returns the full `HedgeReport` the results page renders.
- `backend/` — FastAPI, all TDD'd. Every route is under `/api`
  (`/api/analyze`, `/api/health`). `/api/analyze` takes `answers` JSON + a
  **required** `financials` CSV (400 with a readable `detail` if it's
  missing or unusable). `app/pipeline.py` runs, in order:
  1. `financial_history.py` — finds the month column (`month`/`date`/
     `period`) and profit column (`operating_income` → `net_income` →
     `profit` → `gross_profit`); reads `YYYY-MM[-DD]`, `YYYY/MM` and
     `M/D/YYYY` dates, `$1,234` and `(1,234)` amounts and Excel's BOM;
     then picks the year to simulate: the
     **worst of the 3 most recent complete calendar years** (largest RMS
     shortfall below "expected" = the same month's mean in every other
     year). Two Scoops → 2024, Quillstack → 2025. Fails before any model
     call.
  2. **Model call 1 — trend detection** (`trend_detection.py`) gets the
     answers, an **evidence digest** (`evidence.py`: worst months vs. normal
     with notes, the owner's notes timeline, price/rate column swings first)
     and the last 24 CSV rows. It lists every plausible factor (up to 10)
     with a 0–100 `confidence` and a `market_family`; factors under 20 are
     dropped. If none remain, return the report with no bets.
  3. `market_catalog.py` + `kalshi_client.py` — open markets only from the
     Kalshi series matching those families; weather (rain/heat) only for
     the owner's city (`match_city`: Austin, NYC, Chicago, LA, Miami, SF,
     Seattle), left out entirely for other cities. Via the public no-auth API, fetched in parallel with a 6 s
     overall deadline (up to 5
     markets each, YES price 0.03–0.97). If Kalshi returns nothing at all,
     `FALLBACK_MARKETS` (clearly labelled mock) keeps the demo working.
  4. **Model call 2 — position sizing** (`position_sizing.py`) must plan
     **every** factor that has candidates: each gets a ticker from its own
     candidates or `NONE`, plus side, stake, trade months and months it
     paid out. Factors with no candidates, `NONE`, invalid plans or a
     ticker another factor already uses become `unhedgedRisks` with a
     reason, shown on the results page under "Risks without a Kalshi market".
  Both model calls are JSON-schema enforced (`response_format`), run at
  temperature 0 with seed 0, request 4096 output tokens (the server's
  default cap of 512 truncated replies) and allow 140 s per call, so both
  fit in Vercel's 300 s function limit.
  5. `risk_budget.py` + `backtest.py` — stakes are scaled so no month
     exceeds the budget; monthly net = `round(stake / price)` in hit
     months minus the stake in trade months (NO price = 1 − YES price).
  6. `hedge_report.py` — camelCase `HedgeReport`.
  A full run takes ~35–115 s depending on the shared model server's load.
  `backend/.env` holds the real Akamai credentials (gitignored);
  `backend/.env.example` is the template. CORS allows `ALLOWED_ORIGINS`
  (default `http://localhost:5173`).
- `frontend/` — home → questionnaire → results, TDD'd. Calls the real
  `/api/analyze` on the same site by default (the Vite dev server proxies
  `/api` to `localhost:8000`); `VITE_USE_MOCK_API=true` switches to the
  simulated Two Scoops Creamery report (`frontend/src/api/twoScoopsReport.ts`),
  kept for offline demos and tests. The questionnaire asks the 9 free-text
  questions (none required); the CSV upload is required unless mock mode
  is on. Backend error `detail`s are shown on the form. The results table
  shows each trade's risk, market, side, amount per trade, frequency,
  reasoning, net for the year and variance mitigation
  (`frontend/src/report/tradeImpact.ts`), with totals; clicking a row shows
  that trade's graph. Screens are React state in `App.tsx` (no router).
- `.claude/launch.json` has `frontend` (5173) and `backend` (8000) configs.
- `demo-data/` — **the north-star simulated data**: two fictional
  businesses (Two Scoops Creamery, an Austin ice cream shop, 2016–2026;
  Quillstack AI, an SF AI startup, 2024–2026), each with a detailed
  monthly `financials.csv` and a `background.md` (story, ready-to-paste
  questionnaire answers, and a "what Hedgehog should find" checklist).
  Build, test and demo against these instead of inventing data. Backend
  tests read these CSVs directly; frontend tests mirror the demo answers
  in `frontend/src/test/answers.ts`.
- `vercel.json` (repo root) deploys both apps as Vercel **services**:
  `frontend` (root `frontend/`, Vite) serves `/`; `backend` (root
  `backend/`, FastAPI, entrypoint `app/main.py`, `maxDuration` 300 s)
  serves `/api/*`. No bindings: the browser calls `/api` directly, and the
  backend only calls Akamai and Kalshi. The Vercel project's Root
  Directory must be the repo root. Set `AKAMAI_API_BASE_URL`,
  `AKAMAI_API_KEY` and `AKAMAI_CHAT_MODEL` in Vercel's env vars. The
  site and API share one domain, so CORS only matters for local dev.
  Uploads are capped at 4 MB (Vercel rejects request bodies over 4.5 MB).
- Both model calls
  run at temperature 0 with a fixed seed, but the shared vLLM server can
  still vary slightly between runs.

## Parts of the project
- Questionnaire + CSV upload UI (frontend)
- Kalshi API client (backend)
- Model service: two sequential model calls (trend detection → position
  sizing), both hosted/queried via Akamai
- CSV financials parser (backend ingests the uploaded data directly —
  no stored "standard business metrics" pipeline needed for MVP)
- Results/dashboard UI: concerns summary, recommended bets,
  proof-of-concept graphs

## Development approach
- **Test-driven development is required for all code** (frontend and
  backend): write a failing test first, then the minimum code to pass
  it, then refactor. This applies to model-call logic, the CSV parser,
  the Kalshi client, and UI components alike.
- Follow the global coding rules (simple, modular, DRY, informative
  names, one-line function signatures, remove old code rather than
  leaving it for "compatibility").
- Keep real-vs-mocked boundaries explicit in code (e.g. a clearly named
  `MOCK_` flag or a swappable data-source interface), so swapping mocked
  pieces for real integrations post-hackathon doesn't require a rewrite.

## Open questions (fill in before/while building)
- Akamai specifics: which Akamai product(s) — App Platform, Cloud
  Compute, the LLM hosting product — and how backend deploy + model
  hosting are wired together.
