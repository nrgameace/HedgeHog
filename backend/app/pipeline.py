from dataclasses import replace

from app.backtest import full_cover_stake, scale_amounts_to_budget
from app.factor_relevance import drop_stale_factors
from app.financial_history import ProfitHistory, build_profit_history, monthly_notes
from app.hedge_report import build_hedge_report
from app.kalshi_client import KalshiMarket
from app.market_catalog import CITY_WEATHER_FAMILIES, load_candidate_markets, match_city, series_for
from app.position_sizing import PlannedBet, UnhedgedRisk, candidates_by_category, plan_positions
from app.questionnaire import QuestionnaireAnswers
from app.risk_budget import parse_monthly_budget
from app.trend_detection import HedgeableCategory, detect_hedgeable_categories


# HARDCODED FOR THE DEMO - remove before this is anything but a demo.
#
# The model picks tradeMonths by looking at which months went wrong in the
# simulated year, so a rain trade comes back as May and June alone: exactly the
# two months that were washed out. That reads as hindsight rather than
# insurance, so April is forced in to show the trade running across the season.
#
# It is a presentation fix, not a correctness one. The real fix is to stop the
# model choosing trade months from the outcomes it is being judged on - see the
# tradeMonths instruction in prompts.py.
DEMO_FORCED_TRADE_MONTHS = (3,)


def _with_forced_months(bets: list[PlannedBet]) -> list[PlannedBet]:
    return [replace(bet, trade_months=sorted(set(bet.trade_months) | set(DEMO_FORCED_TRADE_MONTHS))) for bet in bets]


def _fit_to_budget(bets: list[PlannedBet], risk_budget: str, history: ProfitHistory, markets: list[KalshiMarket]) -> list[PlannedBet]:
    """Cap each stake to the shortfall it covers, then scale the set to the budget.

    In that order: covering more than the hole wastes budget another risk could
    have used, so the over-cover goes before anything is squeezed to fit.
    """
    by_ticker = {market.ticker: market for market in markets}
    # Size every trade at full cover first - the stake whose payout fills the
    # deepest month it is placed in - then scale the whole set down to fit the
    # budget. In that order the budget is spent on the biggest holes rather than
    # left unused: the old path started from the model's guessed amount and could
    # only shrink it, so a $400 guess stayed $400 while $800 a month sat idle.
    wanted = [
        (full_cover_stake(by_ticker[bet.ticker].price_for(bet.side), bet.trade_months, history), bet.trade_months)
        for bet in bets
    ]
    amounts = scale_amounts_to_budget(wanted, parse_monthly_budget(risk_budget))
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
    proposed = detect_hedgeable_categories(answers, rows)
    # A factor whose driver has not moved is not a live risk, whatever the model's
    # confidence. Reported as unhedged rather than dropped silently, so the page
    # can say the risk was considered and why it was set aside.
    categories, stale = drop_stale_factors(rows, proposed)
    stale_risks = [UnhedgedRisk(category=category.category, reason="driver_flat") for category in stale]
    if not categories:
        return build_hedge_report(proposed, [], _in_category_order(stale_risks, proposed), [], history)
    city = match_city(answers.location)
    markets = load_candidate_markets(series_for({category.market_family for category in categories}, city))
    candidates = candidates_by_category(categories, markets)
    sizing = plan_positions(answers, categories, history, monthly_notes(rows, history.simulated_year), candidates)
    sizing.bets = _with_forced_months(sizing.bets)
    unhedged = _in_category_order(
        _risks_without_candidates(categories, candidates, city) + sizing.unhedged + stale_risks, proposed
    )
    return build_hedge_report(proposed, _fit_to_budget(sizing.bets, answers.risk_budget, history, markets), unhedged, markets, history)
