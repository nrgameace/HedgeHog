from dataclasses import asdict

from app.backtest import simulate_monthly_net
from app.financial_history import ProfitHistory
from app.kalshi_client import KalshiMarket
from app.position_sizing import PlannedBet
from app.trend_detection import HedgeableCategory


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


def build_hedge_report(categories: list[HedgeableCategory], bets: list[PlannedBet], markets: list[KalshiMarket], history: ProfitHistory) -> dict:
    labels = {category.category: category.label for category in categories}
    markets_by_ticker = {market.ticker: market for market in markets}
    return {
        "bets": [_bet_entry(bet, labels[bet.category], markets_by_ticker[bet.ticker]) for bet in bets],
        "profitSeries": [asdict(point) for point in history.points],
        "simulatedPeriod": str(history.simulated_year),
    }
