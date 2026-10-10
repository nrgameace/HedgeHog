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
- `backend/` — FastAPI app with `/health` and `POST /analyze`, all TDD'd.
  `/analyze` accepts the frontend's real request shape (`answers` JSON +
  optional `financials` CSV, see TECHSTACK.md's contract) and runs
  **Model call 1 (trend detection)** for real: parses the CSV
  (`app/csv_parsing.py`), builds a prompt from the 9 questionnaire
  answers (`app/questionnaire.py`, `app/prompts.py`), calls the
  Akamai-hosted `hackathon-chat` model (`app/akamai_client.py`), and
  parses its reply into categories (`app/trend_detection.py`). Response
  is currently `{"hedgeable_categories": [{category, label, reasoning}]}`
  — **not yet** the full `HedgeReport` the frontend's contract expects,
  since that needs Model call 2 (position sizing) and a Kalshi client,
  neither of which exist yet. `backend/.env` holds the real Akamai
  credentials (gitignored); `backend/.env.example` is the template.
- `frontend/` — full home → questionnaire → results flow built via TDD,
  running on **mock data** (`MOCK_API` in `frontend/src/api/client.ts`,
  on by default). Questionnaire asks the 9 free-text questions in step 2
  (none required while the app runs on simulated data), defined as one list in `frontend/src/pages/QuestionnairePage.tsx`,
  plus an **optional** CSV upload (any shape, max 5 MB) — optional while
  the app runs on simulated data. Since the backend isn't hooked up,
  the results page **always shows simulated results for Two Scoops
  Creamery**, whatever is entered (`frontend/src/api/twoScoopsReport.ts`):
  six fixed Kalshi trades simulated against its real 2024 monthly profit
  (rain paid out in the washed-out May–June). The results table shows
  each trade's risk ("what could hurt your profit"), market, side, amount per trade, frequency, reasoning, net
  for the year and variance mitigation (share of the bad-month shortfall
  covered — `frontend/src/report/tradeImpact.ts`), with totals at the
  bottom. The graph shows the total trade impact; clicking a row shows
  that trade's graph, clicking the totals row goes back. Screens are React state in
  `App.tsx` (no router), so a refresh starts over.
- `demo-data/` — **the north-star simulated data**: two fictional
  businesses (Two Scoops Creamery, an Austin ice cream shop, 2016–2026;
  Quillstack AI, an SF AI startup, 2024–2026), each with a detailed
  monthly `financials.csv` and a `background.md` (story, ready-to-paste
  questionnaire answers, and a "what Hedgehog should find" checklist).
  Build, test and demo against these instead of inventing data. Frontend
  tests mirror the demo answers in `frontend/src/test/answers.ts`.
- Not yet built: Model call 2 (position sizing), the Kalshi client, and
  turning `hedgeable_categories` into the full `HedgeReport` shape
  (`bets`/`profitSeries`/`simulatedPeriod`) the frontend's contract
  expects — plus Akamai deployment wiring. The frontend still runs on
  mock data (`MOCK_API` default) until all of that lands; flip
  `VITE_USE_MOCK_API=false` to hit the real `/analyze` and see today's
  partial response.

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
- CSV format: what columns/shape does the financials CSV need? Will we
  define a fixed schema and validate against it, or accept loose
  formats and let the model handle variance?
- Kalshi auth: sandbox API keys or production read-only keys for market
  data?
- Akamai specifics: which Akamai product(s) — App Platform, Cloud
  Compute, the LLM hosting product — and how backend deploy + model
  hosting are wired together.
