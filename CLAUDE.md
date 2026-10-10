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
  — **not yet** the full `HedgeReport` the frontend's contract expects.
  `backend/.env` holds the real Akamai credentials (gitignored);
  `backend/.env.example` is the template.
- `backend/app/hedge/` — the pure math core of model call 2, TDD'd:
  - `sizing.py` — `size_position()` turns an `Exposure` (daily amount at
    risk, impact %, which side hurts) plus a `MarketQuote` into a
    contract count, capped by budget and resting book depth, and reports
    which constraint bound.
  - `metrics.py` — scenario-weighted before/after stats (mean, stdev,
    worst case, 5th percentile) and `compare_hedge()` for the dashboard.
  - Both are pure: no network, no model calls, no Kalshi types. The
    central result they encode is that contract count equals the dollar
    shortfall and is **independent of contract price** — price sets the
    hedge's cost, not its size.
- `backend/app/kalshi/` — market-data client, TDD'd:
  - `models.py` — `Series`, `Market`, `OrderBook` parsed from live
    payload shapes; `event_window()` derives a `ContractWindow` from a
    ticker's date segment plus the series frequency.
  - `client.py` — `KalshiClient` over httpx with an injectable transport
    (so tests need no network): `list_series()`, `list_markets()` with
    cursor pagination, `get_orderbook()`, `quotes_for_series()`.
  - `candidates.py` — `find_options()` walks ranked series to actual
    tradeable markets, nearest settlement first, dropping anything with
    no reachable offer. Essential: 171 of 190 active `KXB200MS` markets
    have no book, and a model shown those picks one confidently.
  - `search.py` — `rank_series()` narrows 14,942 series to the handful a
    model can reason over. Normalised IDF over titles, generic business
    words down-weighted, scores scaled by how much of the stated factor
    a title accounts for. Recall-oriented: the model supplies precision.
  - Unauthenticated by design: market data needs no credentials.
- `backend/app/model/` — model-facing helpers on top of
  `app/akamai_client.py` (the single HTTP client for the Akamai model):
  - `json_reply.py` — pulls a JSON object out of a reply that may be
    fenced, prefaced with prose, or both.
  - `selection.py` — **Model call 2**: `select_market()` picks which
    candidate market to hedge a factor with, how much is at stake, and
    which way the factor has to move to hurt. The side is then *derived*
    from that direction plus Kalshi's `strike_type`, not asked for: the
    same risk flips sides with how a market is phrased (hurt by cold
    means YES on "below 56" and NO on "above 63"), and buying the wrong
    one amplifies the risk while still reporting a perfect hedge.
    Hallucinated tickers, bad directions, implausible impacts and
    unbuyable sides are all refused.
  - `vocabulary.py` — asks the model which words Kalshi would title a
    series with, then merges the validated proposal over a curated
    table, so `search.py`'s expansions are not a ceiling on which
    businesses the app can serve.
- `frontend/` — full home → questionnaire → results flow built via TDD,
  running on **mock data** (`MOCK_API` in `frontend/src/api/client.ts`,
  on by default). Questionnaire asks the 9 free-text questions in step 2,
  plus an **optional** CSV upload (any shape, max 5 MB). The results page
  currently always shows simulated results for Two Scoops Creamery
  (`frontend/src/api/twoScoopsReport.ts`). Screens are React state in
  `App.tsx` (no router), so a refresh starts over.
- `demo-data/` — **the north-star simulated data**: two fictional
  businesses (Two Scoops Creamery, an Austin ice cream shop, 2016–2026;
  Quillstack AI, an SF AI startup, 2024–2026), each with a detailed
  monthly `financials.csv` and a `background.md`. Build, test and demo
  against these instead of inventing data.
- `backend/app/hedge/exposure.py` — converts `csv_parsing`'s untyped
  string rows and the questionnaire's free-text `riskBudget` into the
  Decimals sizing needs: fuzzy column matching, money parsing that
  survives `$1,234.50` and `(500)`, trailing-month means, and a daily
  rate so one exposure serves contract windows from a day to a year.
- Not yet built: turning `hedgeable_categories` into the full
  `HedgeReport` shape (`bets`/`profitSeries`/`simulatedPeriod`) the
  frontend expects, cross-factor portfolio allocation, the Kalshi fee
  schedule, and Akamai deployment wiring. The frontend stays on mock
  data until that lands.

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
