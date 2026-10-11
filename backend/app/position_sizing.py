import math
from dataclasses import dataclass

import httpx

from app.akamai_client import AkamaiConfig, chat_complete
from app.financial_history import ProfitHistory
from app.hedge_side import DIRECTIONS, resolved_side
from app.hit_months import credible_hit_months
from app.kalshi_client import KalshiMarket
from app.market_catalog import family_of
from app.model_json import parse_model_json
from app.prompts import build_position_sizing_messages
from app.questionnaire import QuestionnaireAnswers
from app.trend_detection import HedgeableCategory

NO_MARKET_TICKER = "NONE"
SIDES = ("YES", "NO")
TEXT_FIELDS = ("ticker", "side", "frequency", "riskExplanation", "rationale")
MONTHS_SCHEMA = {"type": "array", "items": {"type": "integer", "minimum": 0, "maximum": 11}}


@dataclass
class PlannedBet:
    category: str
    ticker: str
    side: str
    amount_usd: int
    frequency: str
    trade_months: list[int]
    hit_months: list[int]
    risk_explanation: str
    rationale: str


@dataclass
class UnhedgedRisk:
    category: str
    reason: str
    covered_by: str | None = None


@dataclass
class SizingResult:
    bets: list[PlannedBet]
    unhedged: list[UnhedgedRisk]


class PositionSizingError(Exception):
    pass


def candidates_by_category(categories: list[HedgeableCategory], markets: list[KalshiMarket]) -> dict[str, list[KalshiMarket]]:
    return {category.category: [market for market in markets if family_of(market.ticker) == category.market_family] for category in categories}


def _plan_schema(markets: list[KalshiMarket]) -> dict:
    return {
        "type": "object",
        "properties": {
            "ticker": {"enum": [market.ticker for market in markets] + [NO_MARKET_TICKER]},
            "direction": {"enum": sorted(DIRECTIONS)},
            "side": {"enum": list(SIDES)},
            "amountUsd": {"type": "integer", "minimum": 1},
            "frequency": {"type": "string"},
            "tradeMonths": MONTHS_SCHEMA,
            "hitMonths": MONTHS_SCHEMA,
            "riskExplanation": {"type": "string"},
            "rationale": {"type": "string"},
        },
        "required": ["ticker", "direction", "side", "amountUsd", "frequency", "tradeMonths", "hitMonths", "riskExplanation", "rationale"],
        "additionalProperties": False,
    }


def position_sizing_schema(candidates: dict[str, list[KalshiMarket]]) -> dict:
    sized = {slug: markets for slug, markets in candidates.items() if markets}
    plans = {"type": "object", "properties": {slug: _plan_schema(markets) for slug, markets in sized.items()}, "required": list(sized), "additionalProperties": False}
    return {"type": "object", "properties": {"plans": plans}, "required": ["plans"], "additionalProperties": False}


def _valid_months(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    return sorted({month for month in value if type(month) is int and 0 <= month <= 11})


def _valid_amount(value: object) -> int | None:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        return None
    return max(round(value), 1)


def _parse_bet(item: object, category: str, markets: dict[str, KalshiMarket], history: ProfitHistory, notes: dict[int, str]) -> PlannedBet | None:
    if not isinstance(item, dict) or not all(isinstance(item.get(field), str) and item[field].strip() for field in TEXT_FIELDS):
        return None
    amount, trade_months = _valid_amount(item.get("amountUsd")), _valid_months(item.get("tradeMonths"))
    if item["ticker"] not in markets or item["side"] not in SIDES or amount is None or not trade_months:
        return None
    claimed = [month for month in _valid_months(item.get("hitMonths")) if month in trade_months]
    return PlannedBet(
        category=category, ticker=item["ticker"],
        # Recomputed from the stated direction where the strike shape allows it, so a
        # backwards side cannot quietly turn the hedge into a doubled-down bet.
        side=resolved_side(item.get("direction"), markets[item["ticker"]].strike_type, item["side"]),
        amount_usd=amount, frequency=item["frequency"].strip(), trade_months=trade_months,
        # Only months the business's own records corroborate, so the model cannot
        # mark its own backtest.
        hit_months=credible_hit_months(claimed, history, notes),
        risk_explanation=item["riskExplanation"].strip(), rationale=item["rationale"].strip(),
    )


def _plans_from_reply(reply: str) -> dict:
    try:
        parsed = parse_model_json(reply)
    except ValueError as exc:
        raise PositionSizingError(f"model reply was not valid JSON: {reply}") from exc
    plans = parsed.get("plans") if isinstance(parsed, dict) else None
    if not isinstance(plans, dict):
        raise PositionSizingError(f"model reply missing 'plans' object: {reply}")
    return plans


def _collect(plans: dict, sized: list[HedgeableCategory], candidates: dict[str, list[KalshiMarket]], history: ProfitHistory, notes: dict[int, str]) -> SizingResult:
    result, owner_of_ticker = SizingResult(bets=[], unhedged=[]), {}
    for category in sized:
        by_ticker = {market.ticker: market for market in candidates[category.category]}
        bet = _parse_bet(plans.get(category.category), category.category, by_ticker, history, notes)
        if bet is None:
            result.unhedged.append(UnhedgedRisk(category=category.category, reason="no_fit"))
        elif bet.ticker in owner_of_ticker:
            result.unhedged.append(UnhedgedRisk(category=category.category, reason="duplicate", covered_by=owner_of_ticker[bet.ticker]))
        else:
            owner_of_ticker[bet.ticker] = category.category
            result.bets.append(bet)
    return result


def plan_positions(answers: QuestionnaireAnswers, categories: list[HedgeableCategory], history: ProfitHistory, notes: dict[int, str], candidates: dict[str, list[KalshiMarket]], *, config: AkamaiConfig | None = None, client: httpx.Client | None = None) -> SizingResult:
    sized = [category for category in categories if candidates.get(category.category)]
    if not sized:
        return SizingResult(bets=[], unhedged=[])
    sized_candidates = {category.category: candidates[category.category] for category in sized}
    messages = build_position_sizing_messages(answers, sized, history, notes, sized_candidates)
    reply = chat_complete(messages, response_schema=position_sizing_schema(sized_candidates), config=config, client=client)
    return _collect(_plans_from_reply(reply), sized, sized_candidates, history, notes)
