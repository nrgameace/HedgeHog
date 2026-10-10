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

## Demo scenarios
Two scenarios are being built, deliberately chosen to exercise opposite
ends of the contract-horizon range:
1. **Ice cream shop** — short-horizon daily **temperature** contracts in
   a major city. Not rain, and not Kansas City: Kalshi has no KC weather
   series, and daily rain barely exists (`RAINSEA` is the only clean
   one), while daily temperature covers many cities. A cold day also
   suppresses ice cream demand more reliably than a rainy one. The shop
   is hurt when it is *cold*, so the hedge buys the side that pays on a
   cold outcome.
2. **AI startup** — longer-horizon GPU/compute pricing contracts against
   Kalshi's B200 compute-price family. Hurt when compute prices *rise*.
   Live markets are **monthly** (`KXB200MS`, 190 active) and annual
   (`KXB200MAX`); the weekly and quarterly B200 series have no active
   markets at all, so monthly is the demo horizon.

Both are confirmed to have real Kalshi series behind them (verified
2026-10-10, see TECHSTACK.md for tickers). This is the main reason
contract windows are structural rather than assumed — the same sizing
code has to serve a one-day hedge and a quarterly one.

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
2. **Questionnaire** — the owner answers questions about their company
   (what factors they believe impact them — rain, gas prices, GPU
   prices, etc. — plus expected earnings) and attaches a CSV of their
   financials.
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
- `backend/` — FastAPI app scaffolded with a `/health` endpoint, pytest
  wired up, TDD'd (test written and confirmed red before the
  implementation went green).
- `frontend/` — Vite + React + TS scaffolded, Vitest + React Testing
  Library wired up, homepage stub ("Hedgehog" heading + "Start" link)
  built via TDD.
- `backend/app/hedge/` — the pure math core of model call 2, TDD'd:
  - `sizing.py` — `size_position()` turns an `Exposure` (daily revenue
    rate, revenue impact %, which side hurts) plus a `MarketQuote` into a
    contract count, capped by budget and resting book depth, and reports
    which constraint bound.
  - `metrics.py` — scenario-weighted before/after stats (mean, stdev,
    worst case, 5th percentile) and `compare_hedge()` for the dashboard.
  - Both are pure: no network, no model calls, no Kalshi types. The
    central result they encode is that contract count equals the dollar
    revenue shortfall and is **independent of contract price** — price
    sets the hedge's cost, not its size.

## Contract horizons
Kalshi contracts settle over whatever window their series uses — daily,
weekly, monthly, quarterly, or one-off event dates. The hedge math is
only valid when the revenue shortfall is measured over **the same window
the contract resolves on**, so:
- `Exposure` carries a **daily revenue rate**, and `size_position()`
  scales it by each contract's own `ContractWindow`. Pairing a monthly
  revenue figure with a daily contract would over-hedge ~30x while
  staying internally consistent at every step, which is why the window is
  structural rather than a caller convention.
- A `ContractWindow` is the span of business activity the event covers —
  **not** Kalshi's `open_time`..`close_time`, which is only when the
  market accepts orders and can begin weeks before the measured period.
- **A contract bought mid-window only hedges the remainder.**
  `KXB200MS-26OCT` covers 1–31 October, but bought on 10 October nine of
  those days are already spent, and sizing against all 31 over-hedges by
  ~41%. `size_position()` and `two_state_scenarios()` both clip to
  `ContractWindow.remaining_days(as_of)`, which defaults to today.
  This failure mode is invisible in the metrics — an unclipped hedge
  still reports 100% volatility reduction, because it is a perfect hedge
  of the wrong period.
- Every position reports `window`, `as_of`, `days_hedged` and
  `revenue_at_risk` so the results page can state each leg's horizon
  rather than implying one uniform period.
- Portfolio construction (not yet built) has to mix horizons: a monthly
  risk is often better hedged by a ladder of daily contracts, which pays
  in proportion to how many bad days actually occur, than by one
  all-or-nothing monthly contract. The tradeoff is transaction cost —
  30 daily legs cross the spread 30 times — and the aggregate payoff of
  many independent daily legs is binomial, so it needs no 2^k scenario
  enumeration.
- `backend/app/kalshi/` — market-data client, TDD'd:
  - `models.py` — `Series`, `Market`, `OrderBook` parsed from live
    payload shapes; `event_window()` derives a `ContractWindow` from a
    ticker's date segment plus the series frequency.
  - `client.py` — `KalshiClient` over httpx with an injectable transport
    (so tests need no network). `list_series()`, `list_markets()` with
    cursor pagination, `get_orderbook()`, and `quotes_for_series()`
    which pairs each tradeable market with its own window and quotes it
    at real book depth.
  - `search.py` — `rank_series()` narrows the catalogue to the
    candidates a model can reason over. Normalised IDF over titles,
    curated factor-to-product expansions, generic business words
    down-weighted, and scores scaled by how much of the stated factor a
    title accounts for. Recall-oriented by design: the model supplies
    precision, and its chosen tickers are validated against the
    candidates it was shown.
  - Unauthenticated by design: market data needs no credentials, so no
    request signing exists rather than sitting unused.
- Not yet built: model call 1 (trend detection), model call 2's LLM
  selection stage, cross-factor portfolio allocation, fee schedule, the
  CSV-to-daily-revenue converter, the `revenueSeries` generator,
  orchestration endpoint, Akamai deployment wiring. Frontend flow exists
  on a branch but is unmerged and on mocks.

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
- ~~Kalshi auth: sandbox API keys or production read-only keys for market
  data?~~ **Resolved 2026-10-10**: market data needs no auth at all.
  `GET /markets` against production returns 200 with no credentials, so
  the demo needs no Kalshi keys. See TECHSTACK.md for the signing scheme
  if real order placement is ever added.
- ~~Hedge budget: does the questionnaire collect it, or is it derived as
  a % of revenue?~~ **Resolved 2026-10-10**: the questionnaire collects
  it as a new field. **This needs a frontend + endpoint change owned by
  whoever holds the questionnaire** — add it to `QuestionnaireAnswers`,
  the form, and whatever submit endpoint the two sides settle on.
  `size_position()` already takes `budget` and reports
  `Constraint.BUDGET` plus `hedge_ratio` when it binds.
- Hedge horizon: over what period is the owner trying to smooth revenue?
  This bounds which contract windows are eligible, but individual legs
  keep their own settlement windows regardless (see Contract horizons).
- Per-series exposure windows: Kalshi does not cleanly expose the period
  an event covers, so the client needs a per-series mapping from ticker
  conventions to a `ContractWindow`.
- Akamai specifics: which Akamai product(s) — App Platform, Cloud
  Compute, the LLM hosting product — and how backend deploy + model
  hosting are wired together.
