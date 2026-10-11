from dataclasses import asdict

from app.backtest import simulate_monthly_net
from app.financial_history import ProfitHistory
from app.kalshi_client import KalshiMarket
from app.position_sizing import PlannedBet, UnhedgedRisk
from app.trend_detection import HedgeableCategory


REASON_TEXTS = {
    "no_market": "Kalshi doesn't list a market for this yet.",
    "no_city_market": "Kalshi only lists weather markets for Austin, New York, Chicago, Los Angeles, Miami, San Francisco and Seattle.",
    "no_fit": "None of the open Kalshi markets fit this risk closely enough.",
    "duplicate": "Already covered by the {label} trade.",
}


def _price_for_side(market: KalshiMarket, side: str) -> float:
    return market.yes_price if side == "YES" else 1 - market.yes_price


def _bet_entry(bet: PlannedBet, label: str, market: KalshiMarket) -> dict:
    return {
        "risk": {"factor": label, "explanation": bet.risk_explanation},
        "market": f"{market.title} {market.subtitle}".strip(),
        "ticker": bet.ticker,
        "side": bet.side,
        "amountUsd": bet.amount_usd,
        "frequency": bet.frequency,
        "tradeMonths": bet.trade_months,
        "rationale": bet.rationale,
        "monthlyNetUsd": simulate_monthly_net(bet.amount_usd, _price_for_side(market, bet.side), bet.trade_months, bet.hit_months),
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
