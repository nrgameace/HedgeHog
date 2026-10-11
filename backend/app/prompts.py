import csv
import io
from typing import TYPE_CHECKING

from app.evidence import build_evidence_digest
from app.financial_history import ProfitHistory
from app.kalshi_client import KalshiMarket
from app.questionnaire import QuestionnaireAnswers

if TYPE_CHECKING:
    from app.trend_detection import HedgeableCategory

TREND_DETECTION_SYSTEM_PROMPT = """You are a financial risk analyst for Hedgehog, a tool that helps small business owners hedge against market volatility using prediction markets (Kalshi).

You are given a business owner's answers to a short questionnaire, a digest of evidence pre-computed from their financial history (their worst months against a normal year, the owner's own notes, and the biggest swings in prices, rates and other columns), and their most recent rows of financial data.

List every factor that could plausibly move this business's revenue or costs: weather, fuel and energy prices, ingredient or input prices, interest rates on its loans or cash, inflation and consumer spending, the job market, the economy, or anything else the evidence points to. Ground each factor in what the owner said or what the evidence shows. A cost the owner already locked in at a fixed price is not a current risk; leave it out.

For each factor give:
- "category": a short snake_case slug, unique within your answer.
- "label": a short human-readable name.
- "reasoning": one or two sentences citing the owner's answers or the evidence.
- "confidence": an integer from 0 to 100 for how likely this factor really moves this business's profit. Be honest: low numbers are fine.
- "market_family": the kind of prediction market that could hedge it. Use "rain" or "heat" for local weather, "gas" for gasoline, "oil" for crude oil, "inflation" for consumer prices, "food_prices" for food and ingredient prices, "interest_rates" for loan or savings rates, "jobs" for the labor market, "economy" for GDP and consumer demand, and "none" when no such market fits (for example GPU prices or regulation).

Return up to 10 factors as JSON: {"hedgeable_categories": [{"category", "label", "reasoning", "confidence", "market_family"}]}."""

RECENT_ROWS_SENT = 24


def _format_recent_rows(financials: list[dict[str, str]]) -> str:
    if not financials:
        return ""
    rows = financials[-RECENT_ROWS_SENT:]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def build_trend_detection_messages(answers: QuestionnaireAnswers, financials: list[dict[str, str]]) -> list[dict[str, str]]:
    row_count = len(financials)
    shown = min(row_count, RECENT_ROWS_SENT)
    user_content = f"""What the business does: {answers.business_description}
Customers: {answers.customers}
Location: {answers.location}
Day-to-day operational dependencies: {answers.operational_dependencies}
Key materials or services relied on: {answers.key_materials}
Past impacts / biggest worries: {answers.past_impacts}
Important times of year: {answers.time_of_year}
Costs already locked in at a fixed price: {answers.locked_in_costs}
Risk mitigation budget: {answers.risk_budget}

Evidence from the financial history ({row_count} rows):
{build_evidence_digest(financials)}

Most recent rows (CSV, last {shown} of {row_count} rows):
{_format_recent_rows(financials)}"""
    return [
        {"role": "system", "content": TREND_DETECTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


POSITION_SIZING_SYSTEM_PROMPT = """You are a hedging strategist for Hedgehog, a tool that helps small business owners smooth out their profit by placing small paper (simulated) trades on Kalshi prediction markets.

The previous analysis step found the factors that can move this business's profit. Each factor below comes with its own list of candidate Kalshi markets and their current YES price. You also get the owner's context and monthly risk budget, and the business's monthly profit for a past year (expected in a normal year vs. what actually happened, with the owner's notes).

Each candidate is the currently open contract of a recurring series: Kalshi lists a new contract in the same series every month (or every day, or every Fed meeting). Treat a candidate as standing for its whole series, so the same kind of trade can be placed in any month of the year. Choose the months to trade by when the risk matters for this business, not by the month or date in the contract's title.

Plan every factor. For each one:
- "ticker": one of that factor's candidates, copied exactly. Use "NONE" only if none of its candidates tracks the factor.
- "side": YES or NO, whichever pays out when the business is hurt.
- "amountUsd": the stake per trade in whole dollars. The backend scales all stakes down to fit the owner's budget, so never leave out a factor to save money.
- "tradeMonths": the months of the year (0 = Jan ... 11 = Dec) when this risk matters and the trade is placed.
- "hitMonths": the months of the past year, a subset of tradeMonths, when the event most likely happened, judged from the notes and the months where actual profit fell short of expected. Use [] when there is no evidence.
- "frequency": a short label such as "Monthly, Apr–Jun" or "Quarterly".
- "riskExplanation": one short sentence on what could hurt the owner's profit.
- "rationale": one plain-English sentence on why this trade helps.

Respond as JSON: {"plans": {"<factor slug>": {"ticker", "side", "amountUsd", "frequency", "tradeMonths", "hitMonths", "riskExplanation", "rationale"}}}."""


def _format_profit_month(index: int, history: ProfitHistory, notes: dict[int, str]) -> str:
    point = history.points[index]
    line = f"{point.period}: expected {point.expected} / actual {point.actual}"
    return f"{line} — {notes[index]}" if index in notes else line


def _format_market(market: KalshiMarket) -> str:
    name = f"{market.title} — {market.subtitle}" if market.subtitle else market.title
    return f"- {market.ticker} | {name} | YES price {market.yes_price:.2f}"


def _format_factor(category: "HedgeableCategory", markets: list[KalshiMarket]) -> str:
    candidate_lines = "\n".join(_format_market(market) for market in markets)
    return f"Factor: {category.category}\n{category.label} (confidence {category.confidence}) — {category.reasoning}\nCandidates:\n{candidate_lines}"


def build_position_sizing_messages(answers: QuestionnaireAnswers, categories: list["HedgeableCategory"], history: ProfitHistory, notes: dict[int, str], candidates: dict[str, list[KalshiMarket]]) -> list[dict[str, str]]:
    factor_blocks = "\n\n".join(_format_factor(category, candidates[category.category]) for category in categories)
    profit_lines = "\n".join(_format_profit_month(index, history, notes) for index in range(len(history.points)))
    user_content = f"""What the business does: {answers.business_description}
Location: {answers.location}
Important times of year: {answers.time_of_year}
Costs already locked in at a fixed price: {answers.locked_in_costs}
Monthly risk budget: {answers.risk_budget}

Monthly profit in {history.simulated_year} (expected in a normal year / actual, with notes):
{profit_lines}

Factors to plan, each with its candidate Kalshi markets (ticker | market | YES price):

{factor_blocks}"""
    return [
        {"role": "system", "content": POSITION_SIZING_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
