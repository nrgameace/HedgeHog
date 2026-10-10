from dataclasses import dataclass

import httpx

from app.akamai_client import AkamaiConfig, chat_complete
from app.financial_history import ProfitHistory
from app.kalshi_client import KalshiMarket
from app.model_json import parse_model_json
from app.prompts import build_position_sizing_messages
from app.questionnaire import QuestionnaireAnswers
from app.trend_detection import HedgeableCategory

SIDES = ("YES", "NO")
TEXT_FIELDS = ("frequency", "riskExplanation", "rationale")


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
    if type(value) not in (int, float) or value <= 0:
        return None
    return max(round(value), 1)


def _has_text_fields(item: dict) -> bool:
    return all(isinstance(item.get(field), str) and item[field].strip() for field in TEXT_FIELDS)


def _parse_bet(item: object, category_slugs: set[str], tickers: set[str], seen_tickers: set[str]) -> PlannedBet | None:
    if not isinstance(item, dict) or not _has_text_fields(item):
        return None
    ticker, amount, trade_months = item.get("ticker"), _valid_amount(item.get("amountUsd")), _valid_months(item.get("tradeMonths"))
    if item.get("category") not in category_slugs or ticker not in tickers or ticker in seen_tickers:
        return None
    if item.get("side") not in SIDES or amount is None or not trade_months:
        return None
    hit_months = [month for month in _valid_months(item.get("hitMonths")) if month in trade_months]
    return PlannedBet(
        category=item["category"], ticker=ticker, side=item["side"], amount_usd=amount, frequency=item["frequency"].strip(),
        trade_months=trade_months, hit_months=hit_months, risk_explanation=item["riskExplanation"].strip(), rationale=item["rationale"].strip(),
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
    category_slugs, tickers = {category.category for category in categories}, {market.ticker for market in markets}
    planned: list[PlannedBet] = []
    for item in _bets_from_reply(reply):
        bet = _parse_bet(item, category_slugs, tickers, {bet.ticker for bet in planned})
        if bet is not None:
            planned.append(bet)
    return planned
