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
- **`app/akamai_client.py` is the one HTTP client for the model.**
  Anything that needs the model goes through `chat_complete`; there is
  deliberately no second client.
- Model replies are never trusted directly. `app/model/json_reply.py`
  pulls the JSON object out of a reply that may be fenced, prefaced with
  prose, or both, and raises rather than returning junk. Every caller
  validates the parsed result and degrades to a safe default rather than
  failing the request.
- Two sequential model calls per submission:
  1. **Trend detection** — **implemented** (`backend/app/trend_detection.py`,
     wired into `POST /analyze`). Given the 9 questionnaire answers +
     parsed financials CSV (capped at 200 rows in the prompt), returns
     1–5 hedgeable categories as `{category, label, reasoning}`.
     Temperature 0.2. Request timeout 60s.
  2. **Position sizing** — math, Kalshi client and market retrieval
     built (`app/hedge/`, `app/kalshi/`); the model call that picks a
     market and direction is the remaining piece.

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
  - **Retrieve through `GET /series`, not by paging `GET /markets`.**
    14,942 series exist, and `/markets` without a series filter is
    dominated by sports and 15-minute crypto markets — 6,000 pages deep
    it had still returned zero weather or compute markets. `/series`
    also carries two fields that make retrieval tractable:
    - `frequency` — `daily`, `weekly`, `monthly`, `annual`, `hourly`,
      `custom`, `one_off`. This is the horizon, straight from the API,
      so it covers most of the `ContractWindow` mapping. Only `custom`
      and `one_off` need per-series handling.
    - `categories` — business-relevant ones are Economics (860),
      Climate and Weather (422), Science and Technology (388), Companies
      (216), Commodities (132), Financials (1008), Transportation (37).
      Excluding Sports, Entertainment, Elections, Politics, Mentions and
      Crypto removes ~11,700 of the 14,942 series up front.
  - **Score relevance on series/market `title`, never on the ticker.**
    Ticker substrings produce absurd matches: `KXGPUSDW` looks like a GPU
    market but is "Will GBPUSD end the week above 1.3625?" (G-BP-USD);
    `KXNFLOPOY` matches "flop" but is NFL Offensive Player of the Year;
    `KXCHIPBURRITO` matches "chip" but is Chipotle.
  - Filter out test series — `KXTESTB200`, `KXB200TEST`,
    `KXB200AVGTEST` exist alongside the real ones and will have no book.
  - **Response gotchas** (all seen in live responses, 2026-10-10):
    - Prices are **strings in dollars**, e.g. `yes_ask_dollars: "0.3400"`.
    - `status` values are actually `initialized`, `active` and
      `inactive` — *none* of the documented enum
      (`unopened/paused/open/closed/settled`). Don't hardcode
      `== "open"`; `status=open` is accepted but does not filter as
      documented.
    - `volume` and `liquidity` come back `null`; the populated fields are
      the fixed-point variants `volume_fp`, `volume_24h_fp`,
      `open_interest_fp`.
    - Multivariate combo markets (`KXMVE*`) appear in unfiltered results
      with degenerate books (`yes_bid "0.0000"` / `no_bid "1.0000"`).
      Pass `mve_filter=exclude` — they aren't single-factor events and
      would corrupt the sizing math.

## Candidate series for the demo scenarios
Verified present in the live `GET /series` response, 2026-10-10.

**AI startup — GPU/compute pricing.** A B200 family exists, but **most of
it is dead**. Checked market-by-market:
- `KXB200MS` (monthly) — **190 active markets.** The one to build on.
  Strikes are B200 compute price per hour, e.g.
  `KXB200MS-26OCT-11.000` = "above $11.00 in October".
- `KXB200MAX` (annual) — 23 active markets.
- `KXB200W`, `KXB200WS`, `KXB200MON` — **100% finalized**, no live
  markets. The weekly horizon is not actually available.
- `KXB200Q` (quarterly), `KXFLOP` — **zero markets at all.**
- `KXPPISEMI` / `PPISEMI` — Semiconductor PPI (monthly), as a fallback.
- `KXGPURULE` — GPU export restrictions, but `custom` frequency, so no
  derivable window.
- An **H100** family also exists (`KXH100W` weekly, `KXH100MON` monthly,
  `KXH100MAX` annual) and scores well, but weekly and monthly are
  **entirely finalized**; only `KXH100MAX` has active markets (6). Don't
  spend time on H100 weekly — `KXB200MS` monthly is the only compute
  series with real depth.

**Ice cream shop — daily weather.** 122 daily weather series exist, but
they are overwhelmingly *temperature*, not rain. Daily rain is nearly
absent: `RAINSEA` (Seattle) is the only clean daily one, with
`KXRAINSNYC` (custom) and `KXRAINNAPAM` (monthly) elsewhere. Daily
temperature has broad city coverage: `KXHIGHNY`, `HIGHAUS`, `KXLOWTSFO`,
`KXLOWMIA`, `KXLOWPHIL`, `KXLOWTSATX` and more.
- No daily Kansas City weather series was found.

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
- 2026-10-10 — Contract horizons are structural, not assumed. Kalshi
  series settle daily, weekly, monthly, quarterly or on one-off event
  dates, so `Exposure` holds a daily revenue rate and `size_position()`
  scales it by each contract's own `ContractWindow`. A monthly revenue
  figure paired with a daily contract over-hedges ~30x while every
  intermediate step stays internally consistent, so the window is made
  impossible to omit rather than left to a naming convention.
- 2026-10-10 — Model/host: a Qwen model on Akamai, settling both the
  Akamai-product and model-provider questions.
- 2026-10-10 — Hedge budget is collected as a questionnaire field, not
  derived from revenue. Needs a frontend + endpoint change (see
  CLAUDE.md open questions).
- 2026-10-10 — Ice cream scenario uses daily **temperature** in a major
  city rather than rain in Kansas City. Kalshi has no KC weather series
  and daily rain is nearly absent, while daily temperature covers many
  cities. Daily US high-temp series include `KXHIGHNY` (NYC) and
  `HIGHAUS` (Austin); low-temp adds `KXLOWTSFO`, `KXLOWMIA`,
  `KXLOWPHIL`, `KXLOWTSATX`.
- 2026-10-10 — Exposure is clipped to the days of a contract window that
  are still ahead, via `ContractWindow.remaining_days(as_of)`, with
  `as_of` defaulting to today. Verified live: `KXB200MS-26OCT` on
  10 October sizes 10,560 contracts clipped versus 14,880 unclipped.
  Both report 100% volatility reduction, so the error is invisible in
  the output — it is a perfect hedge of a period that has partly gone.
- 2026-10-10 — Relevance scoring is recall-oriented, not precision-
  oriented: it exists to get plausible candidates into the prompt, and
  the model supplies precision. Term weighting is normalised IDF over
  series titles, which suppresses ubiquitous words like "price" without
  a hand-maintained domain stopword list. Two corrections came from
  running it against the live catalogue:
  - **Generic business words are down-weighted.** "cost" is lexically
    rare across 14,942 titles so IDF rates it highly, and "GPU costs"
    ranked employer health insurance cost and Social Security COLA
    above every GPU price series.
  - **Scores scale by how much of the stated factor a title covers.**
    One rare word otherwise carries a result: "cold weather" put a
    Dunkin' Cold Brew series above every temperature market on the
    strength of "cold" alone.
  A curated expansion table bridges factor wording to Kalshi's product
  names, which pure lexical matching cannot do — the series an AI
  startup needs is titled "B200 Monthly" and shares no word with "GPU
  costs".
- 2026-10-10 — **The model proposes the search vocabulary**
  (`app/model/vocabulary.py`), rather than the curated table being the
  ceiling. Naming what a market is likely called is exactly the
  knowledge a language model has and a keyword index does not, and the
  call returns search words only — never a number, size or tradeable
  ticker. The proposal is merged *over* the curated table so a thin
  reply cannot cost recall the demo scenarios already have, and
  everything returned is validated: concepts the factor never mentioned
  are dropped so the model cannot widen the search itself, terms are
  reduced to matchable tokens, and both are capped. Live comparison:
  - "TPU rental costs" — curated finds health-insurance cost and Social
    Security COLA; proposed finds the H100 price series.
  - "shipping delays" — curated finds airport flight-delay series;
    proposed finds port container-throughput series.
  - "coffee bean prices" — identical, because "coffee" already matches
    `KXCOFFEEW` directly. The model helps only where Kalshi's naming
    diverges from business wording.
  Embeddings over titles remain the cleaner long-term answer.
- 2026-10-10 — A category *boost* was tried and removed. Lifting series
  whose Kalshi category fits the factor inverted stronger lexical
  matches whenever the margin was under the boost: "chip prices" put
  "B100 Yearly Directional Price" (matching only "price") above
  "Semiconductor PPI". Category remains a hard filter only.
- Not yet decided: Kalshi fee schedule. `size_position()` takes
  `fee_per_contract` as a parameter rather than embedding a formula —
  pull the live schedule into one place before the demo.
- Not yet decided: how a `ContractWindow` is derived per Kalshi series.
  `open_time`..`close_time` is the trading window, not the event's
  coverage period, so it cannot be used directly.
