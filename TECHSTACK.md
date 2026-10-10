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
- **Model**: a **Qwen** model hosted on **Akamai**, queried by the
  backend over HTTP. This settles both the "which Akamai product" and
  "which model provider" questions.
- **Wire format assumed OpenAI-compatible**: `POST {MODEL_BASE_URL}/chat/
  completions` with `{model, messages, temperature, max_tokens}`, reply
  read from `choices[0].message.content`. `backend/app/model/client.py`
  is the only file to change if Akamai differs.
- **Configuration** (all env vars, read by `client_from_env()`):
  - `MOCK_MODEL` — defaults to `true`. Must be explicitly `false` before
    anything calls out, so an unconfigured endpoint cannot be hit by
    accident. When unset or `true`, callers fall back to curated
    defaults and the pipeline still runs end to end.
  - `MODEL_BASE_URL`, `MODEL_NAME`, `MODEL_API_KEY` (optional).
- Calls run at `temperature=0`: these are classification and vocabulary
  lookups, where sampling variety is a liability.
- Model replies are never trusted directly. `complete_json()` tolerates
  markdown fences, surrounding prose and nested objects, and raises
  rather than returning junk; every caller validates the parsed result
  and degrades to a curated default on failure.
- Still to confirm: exact Qwen variant, and whether Akamai really is
  OpenAI-compatible. JSON adherence needs testing early — it is the most
  likely place a smaller model misbehaves.
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
