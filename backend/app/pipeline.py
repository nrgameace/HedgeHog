from dataclasses import replace

from app.backtest import scale_amounts_to_budget
from app.financial_history import build_profit_history, monthly_notes
from app.hedge_report import build_hedge_report
from app.market_catalog import SERIES, load_candidate_markets
from app.position_sizing import PlannedBet, plan_positions
from app.questionnaire import QuestionnaireAnswers
from app.risk_budget import parse_monthly_budget
from app.trend_detection import detect_hedgeable_categories


def _fit_to_budget(bets: list[PlannedBet], risk_budget: str) -> list[PlannedBet]:
    amounts = scale_amounts_to_budget([(bet.amount_usd, bet.trade_months) for bet in bets], parse_monthly_budget(risk_budget))
    return [replace(bet, amount_usd=amount) for bet, amount in zip(bets, amounts)]


def run_analysis(answers: QuestionnaireAnswers, rows: list[dict[str, str]]) -> dict:
    history = build_profit_history(rows)
    categories = detect_hedgeable_categories(answers, rows)
    if not categories:
        return build_hedge_report(categories, [], [], history)
    markets = load_candidate_markets([series.ticker for series in SERIES])
    planned = plan_positions(answers, categories, history, monthly_notes(rows, history.simulated_year), markets)
    return build_hedge_report(categories, _fit_to_budget(planned, answers.risk_budget), markets, history)
