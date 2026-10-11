import math
from dataclasses import dataclass

import httpx

from app.akamai_client import AkamaiConfig, chat_complete
from app.financial_history import ProfitHistory
from app.hedge_side import resolved_side
from app.hit_months import credible_hit_months
from app.kalshi_client import KalshiMarket
from app.model_json import parse_model_json
from app.prompts import build_position_sizing_messages
from app.questionnaire import QuestionnaireAnswers
from app.trend_detection import HedgeableCategory

SIDES = ("YES", "NO")
TEXT_FIELDS = ("category", "ticker", "side", "frequency", "riskExplanation", "rationale")


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


class PositionSizingError(Exception):
    pass


def _valid_months(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    return sorted({month for month in value if type(month) is int and 0 <= month <= 11})


def _valid_amount(value: object) -> int | None:
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        return None
    return max(round(value), 1)


def _has_text_fields(item: dict) -> bool:
    return all(isinstance(item.get(field), str) and item[field].strip() for field in TEXT_FIELDS)


def _parse_bet(item: object, category_slugs: set[str], markets_by_ticker: dict[str, KalshiMarket], seen_tickers: set[str], history: ProfitHistory, notes: dict[int, str]) -> PlannedBet | None:
    if not isinstance(item, dict) or not _has_text_fields(item):
        return None
    ticker, amount, trade_months = item.get("ticker"), _valid_amount(item.get("amountUsd")), _valid_months(item.get("tradeMonths"))
    if item.get("category") not in category_slugs or ticker not in markets_by_ticker or ticker in seen_tickers:
        return None
    if item.get("side") not in SIDES or amount is None or not trade_months:
        return None
    claimed = [month for month in _valid_months(item.get("hitMonths")) if month in trade_months]
    return PlannedBet(
        category=item["category"], ticker=ticker,
        # Recomputed from the stated direction where the strike shape allows, so a
        # backwards side cannot quietly turn the hedge into a doubled-down bet.
        side=resolved_side(item.get("direction"), markets_by_ticker[ticker].strike_type, item["side"]),
        amount_usd=amount, frequency=item["frequency"].strip(), trade_months=trade_months,
        # Only months the business's own records corroborate, so the model cannot
        # mark its own backtest.
        hit_months=credible_hit_months(claimed, history, notes),
        risk_explanation=item["riskExplanation"].strip(), rationale=item["rationale"].strip(),
    )


def _bets_from_reply(reply: str) -> list:
    try:
        parsed = parse_model_json(reply)
    except ValueError as exc:
        raise PositionSizingError(f"model reply was not valid JSON: {reply}") from exc
    bets = parsed.get("bets") if isinstance(parsed, dict) else None
    if not isinstance(bets, list):
        raise PositionSizingError(f"model reply missing 'bets' list: {reply}")
    return bets


def plan_positions(answers: QuestionnaireAnswers, categories: list[HedgeableCategory], history: ProfitHistory, notes: dict[int, str], markets: list[KalshiMarket], *, config: AkamaiConfig | None = None, client: httpx.Client | None = None) -> list[PlannedBet]:
    messages = build_position_sizing_messages(answers, categories, history, notes, markets)
    reply = chat_complete(messages, temperature=0.2, config=config, client=client)
    category_slugs = {category.category for category in categories}
    markets_by_ticker = {market.ticker: market for market in markets}
    planned: list[PlannedBet] = []
    for item in _bets_from_reply(reply):
        bet = _parse_bet(item, category_slugs, markets_by_ticker, {bet.ticker for bet in planned}, history, notes)
        if bet is not None:
            planned.append(bet)
    return planned
