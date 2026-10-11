from dataclasses import replace

from app.backtest import cap_amount_to_shortfall, scale_amounts_to_budget
from app.financial_history import build_profit_history, monthly_notes
from app.hedge_report import build_hedge_report
from app.financial_history import ProfitHistory
from app.market_catalog import load_candidate_markets
from app.position_sizing import PlannedBet, plan_positions
from app.questionnaire import QuestionnaireAnswers
from app.risk_budget import parse_monthly_budget
from app.trend_detection import detect_hedgeable_categories


def _price_for_side(market, side: str) -> float:
    return market.yes_price if side == "YES" else 1 - market.yes_price


def _fit_to_exposure_and_budget(bets: list[PlannedBet], risk_budget: str, history: ProfitHistory, markets: list) -> list[PlannedBet]:
    """Cap each stake to the shortfall it covers, then scale the set to the budget.

    In that order: covering more than the hole wastes budget another risk could
    have used, so the over-cover is removed before anything is squeezed to fit.
    """
    by_ticker = {market.ticker: market for market in markets}
    capped = [
        replace(bet, amount_usd=cap_amount_to_shortfall(bet.amount_usd, _price_for_side(by_ticker[bet.ticker], bet.side), bet.trade_months, history))
        for bet in bets
    ]
    amounts = scale_amounts_to_budget([(bet.amount_usd, bet.trade_months) for bet in capped], parse_monthly_budget(risk_budget))
    return [replace(bet, amount_usd=amount) for bet, amount in zip(capped, amounts)]


def run_analysis(answers: QuestionnaireAnswers, rows: list[dict[str, str]]) -> dict:
    history = build_profit_history(rows)
    categories = detect_hedgeable_categories(answers, rows)
    if not categories:
        return build_hedge_report(categories, [], [], history)
    markets = load_candidate_markets()
    planned = plan_positions(answers, categories, history, monthly_notes(rows, history.simulated_year), markets)
    return build_hedge_report(categories, _fit_to_exposure_and_budget(planned, answers.risk_budget, history, markets), markets, history)
