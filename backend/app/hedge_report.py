import re
from dataclasses import asdict

from app.backtest import simulate_monthly_net
from app.market_catalog import DAILY, cadence_of
from app.financial_history import ProfitHistory
from app.kalshi_client import KalshiMarket
from app.position_sizing import PlannedBet, UnhedgedRisk
from app.trend_detection import HedgeableCategory


REASON_TEXTS = {
    "no_market": "Kalshi doesn't list a market for this yet.",
    "no_city_market": "Kalshi only lists weather markets for Austin, New York, Chicago, Los Angeles, Miami, San Francisco and Seattle.",
    "no_fit": "None of the open Kalshi markets fit this risk closely enough.",
    "duplicate": "Already covered by the {label} trade.",
    "driver_flat": "Your own figures show this cost hasn't moved recently, so there's nothing to smooth out.",
}


# Kalshi returns whichever contract of a series is open now, so its title names
# that instance: "Rain in Austin in Oct 2026?". The plan trades the series every
# May and June, so showing the instance reads as "trade the October market in
# May" - which is what it looked like on the results page. Strip the date and the
# title describes the recurring market instead.
_DATE_PHRASE = re.compile(
    r"\s*\b(?:in|on|by|after|for)?\s*"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?"
    r"(?:\s+\d{1,2})?,?\s*\d{4}\b",
    re.IGNORECASE,
)
_CADENCE_WORDS = {DAILY: "each day", "monthly": "each month"}


def recurring_market_name(market: KalshiMarket) -> str:
    """The series a trade stands for, not the one contract that happens to be open."""
    title = _DATE_PHRASE.sub("", market.title).strip()
    title = re.sub(r"\s{2,}", " ", title).replace(" ?", "?")
    parts = [part for part in (title, market.subtitle.strip()) if part]
    return " ".join(parts)


def recurring_frequency(market: KalshiMarket, frequency: str) -> str:
    """The model's own cadence label, plus how often a new contract actually opens."""
    cadence = _CADENCE_WORDS.get(cadence_of(market.ticker))
    return f"{frequency} - a new contract {cadence}" if cadence else frequency


def _bet_entry(bet: PlannedBet, label: str, market: KalshiMarket) -> dict:
    return {
        "risk": {"factor": label, "explanation": bet.risk_explanation},
        "market": recurring_market_name(market),
        "ticker": bet.ticker,
        "side": bet.side,
        "amountUsd": bet.amount_usd,
        "frequency": recurring_frequency(market, bet.frequency),
        "tradeMonths": bet.trade_months,
        "rationale": bet.rationale,
        "monthlyNetUsd": simulate_monthly_net(bet.amount_usd, market.price_for(bet.side), bet.trade_months, bet.hit_months),
    }


def _unhedged_entry(risk: UnhedgedRisk, categories_by_slug: dict[str, HedgeableCategory]) -> dict:
    category = categories_by_slug[risk.category]
    covering_label = categories_by_slug[risk.covered_by].label if risk.covered_by else ""
    return {"factor": category.label, "explanation": category.reasoning, "reason": REASON_TEXTS[risk.reason].format(label=covering_label)}


def build_hedge_report(categories: list[HedgeableCategory], bets: list[PlannedBet], unhedged: list[UnhedgedRisk], markets: list[KalshiMarket], history: ProfitHistory) -> dict:
    categories_by_slug = {category.category: category for category in categories}
    markets_by_ticker = {market.ticker: market for market in markets}
    return {
        "bets": [_bet_entry(bet, categories_by_slug[bet.category].label, markets_by_ticker[bet.ticker]) for bet in bets],
        "unhedgedRisks": [_unhedged_entry(risk, categories_by_slug) for risk in unhedged],
        "profitSeries": [asdict(point) for point in history.points],
        "simulatedPeriod": str(history.simulated_year),
    }
