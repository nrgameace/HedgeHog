from dataclasses import replace

from app.backtest import scale_amounts_to_budget
from app.financial_history import build_profit_history, monthly_notes
from app.hedge_report import build_hedge_report
from app.kalshi_client import KalshiMarket
from app.market_catalog import CITY_WEATHER_FAMILIES, load_candidate_markets, match_city, series_for
from app.position_sizing import PlannedBet, UnhedgedRisk, candidates_by_category, plan_positions
from app.questionnaire import QuestionnaireAnswers
from app.risk_budget import parse_monthly_budget
from app.trend_detection import HedgeableCategory, detect_hedgeable_categories


def _fit_to_budget(bets: list[PlannedBet], risk_budget: str) -> list[PlannedBet]:
    amounts = scale_amounts_to_budget([(bet.amount_usd, bet.trade_months) for bet in bets], parse_monthly_budget(risk_budget))
    return [replace(bet, amount_usd=amount) for bet, amount in zip(bets, amounts)]


def _no_candidate_reason(category: HedgeableCategory, city: str | None) -> str:
    return "no_city_market" if category.market_family in CITY_WEATHER_FAMILIES and city is None else "no_market"


def _risks_without_candidates(categories: list[HedgeableCategory], candidates: dict[str, list[KalshiMarket]], city: str | None) -> list[UnhedgedRisk]:
    return [UnhedgedRisk(category=category.category, reason=_no_candidate_reason(category, city)) for category in categories if not candidates[category.category]]


def _in_category_order(risks: list[UnhedgedRisk], categories: list[HedgeableCategory]) -> list[UnhedgedRisk]:
    order = {category.category: index for index, category in enumerate(categories)}
    return sorted(risks, key=lambda risk: order[risk.category])


def run_analysis(answers: QuestionnaireAnswers, rows: list[dict[str, str]]) -> dict:
    history = build_profit_history(rows)
    categories = detect_hedgeable_categories(answers, rows)
    if not categories:
        return build_hedge_report(categories, [], [], [], history)
    city = match_city(answers.location)
    markets = load_candidate_markets(series_for({category.market_family for category in categories}, city))
    candidates = candidates_by_category(categories, markets)
    sizing = plan_positions(answers, categories, history, monthly_notes(rows, history.simulated_year), candidates)
    unhedged = _in_category_order(_risks_without_candidates(categories, candidates, city) + sizing.unhedged, categories)
    return build_hedge_report(categories, _fit_to_budget(sizing.bets, answers.risk_budget), unhedged, markets, history)
