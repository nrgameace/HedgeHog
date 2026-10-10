"""Model call 2: choosing which market to hedge a factor with, and in which direction.

Relevance scoring hands over candidate markets; this decides which one to use,
how much revenue is at stake, and - critically - which side of it pays when the
business is actually hurt. Sizing turns that into contracts.

Direction is the dangerous part, so it is split in two:

1. The model answers one question per factor: is this business hurt when the
   factor goes *up* or *down*? That is a property of the business, not of any
   particular market, and it cannot be guessed from the factor's name - an AI
   startup holding treasuries is hurt by interest-rate *cuts*, not rises.
2. The side is then derived mechanically from that direction and Kalshi's
   `strike_type`. The same risk flips sides with how a market was phrased: hurt
   by cold means YES on "below 56" and NO on "above 63". Both pay in the cold
   state, and buying the wrong one turns a hedge into a doubled-down bet that
   still reports a perfect hedge in the metrics.

Only markets with no usable `strike_type` - directional ones like "B200 price up
in next week?" - fall back to a side the model states outright.

Every reply is validated: an unknown ticker is refused outright so it can never
reach a sizing calculation, and any failure returns None so the caller skips the
factor rather than hedging on a guess.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum

import httpx

from app.akamai_client import AkamaiApiError, AkamaiConfig, AkamaiConfigError, chat_complete
from app.hedge.sizing import MarketQuote, Side
from app.kalshi.models import Market
from app.model.json_reply import ModelReplyError, parse_json_object

# A factor wiping out more than this share of the exposure is not credible, and
# the shortfall scales linearly with it, so an unchecked value mis-sizes badly.
MAX_IMPACT_PCT = Decimal("0.60")

# Models commonly answer 18 for 18%. Treated as a percentage and divided down,
# because taking it literally would hedge eighteen times the exposure.
PERCENT_POINT_THRESHOLD = Decimal("1")

STRIKE_RISES_WITH_YES = {"greater", "greater_or_equal"}
STRIKE_FALLS_WITH_YES = {"less", "less_or_equal"}


class FactorDirection(Enum):
    """Which way the factor has to move for the business to be hurt."""

    UP = "up"
    DOWN = "down"


@dataclass(frozen=True)
class MarketOption:
    """One tradeable market offered to the model, with the context it needs to choose."""

    series_ticker: str
    series_title: str
    frequency: str
    market: Market
    quote: MarketQuote


@dataclass(frozen=True)
class MarketChoice:
    ticker: str
    side: Side
    direction: FactorDirection
    impact_pct: Decimal
    rationale: str
    side_was_derived: bool
    option: MarketOption


SYSTEM_PROMPT = """You choose which prediction market a small business should \
use to hedge one risk factor, from a list of markets that are already tradeable.

You are given the factor, the business context, and numbered candidate markets \
with their settlement windows and prices.

Decide three things:

1. "ticker" - the single best candidate. Prefer a market whose threshold sits \
near where the business actually starts to hurt, and whose settlement window \
covers the period at risk. Copy the ticker exactly from the list; never invent one.
2. "direction" - whether this business is hurt when the underlying factor goes \
"up" or "down". This is about the business, not the market's wording. A company \
holding cash in treasuries is hurt when interest rates go DOWN. An ice cream \
shop is hurt when temperature goes DOWN.
3. "impact_pct" - the share of the money at risk over that window that this \
factor would cost, as a decimal between 0 and 1 (0.18 means 18%).

Also give "rationale": one plain sentence the owner could judge for themselves.

Reply with JSON only, no markdown fences and no text around it:
{"ticker": "...", "direction": "up"|"down", "impact_pct": 0.0, "rationale": "..."}"""


def select_market(factor: str, options: Sequence[MarketOption], *, config: AkamaiConfig | None = None, client: httpx.Client | None = None) -> MarketChoice | None:
    """Ask the model which candidate to hedge `factor` with, or None if it cannot be trusted."""
    if not options:
        return None

    try:
        reply = chat_complete(
            [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _prompt(factor, options)},
            ],
            temperature=0.0,
            config=config,
            client=client,
        )
        return _validated(parse_json_object(reply), options)
    except (AkamaiConfigError, AkamaiApiError, ModelReplyError):
        return None


def derive_side(direction: FactorDirection, strike_type: str) -> Side | None:
    """Which side pays in the bad state, or None when the strike shape cannot say.

    A YES on a "greater" market resolves when the factor rises, so a business hurt
    by a rise buys YES. Every other combination follows from flipping one of the two.
    """
    shape = strike_type.strip().lower()
    if shape in STRIKE_RISES_WITH_YES:
        yes_pays_when_factor_rises = True
    elif shape in STRIKE_FALLS_WITH_YES:
        yes_pays_when_factor_rises = False
    else:
        return None

    hurt_by_rise = direction is FactorDirection.UP
    return Side.YES if hurt_by_rise == yes_pays_when_factor_rises else Side.NO


def _validated(reply: dict, options: Sequence[MarketOption]) -> MarketChoice | None:
    chosen = _option_for(reply.get("ticker"), options)
    direction = _direction(reply.get("direction"))
    impact = _impact(reply.get("impact_pct"))
    if chosen is None or direction is None or impact is None:
        return None

    side = derive_side(direction, chosen.market.strike_type)
    side_was_derived = side is not None
    if side is None:
        side = _stated_side(reply.get("side"))
    if side is None or not _has_depth(chosen, side):
        # Kalshi quotes many strikes on one side only, so the side this factor
        # needs may simply not be offered. Refuse rather than hand sizing a
        # quote it will reject.
        return None

    return MarketChoice(
        ticker=chosen.market.ticker,
        side=side,
        direction=direction,
        impact_pct=impact,
        rationale=str(reply.get("rationale") or "").strip(),
        side_was_derived=side_was_derived,
        option=chosen,
    )


def _option_for(ticker: object, options: Sequence[MarketOption]) -> MarketOption | None:
    """Only a ticker from the list offered is acceptable; anything else is a hallucination."""
    if not isinstance(ticker, str):
        return None
    return next((option for option in options if option.market.ticker == ticker.strip()), None)


def _direction(value: object) -> FactorDirection | None:
    if not isinstance(value, str):
        return None
    try:
        return FactorDirection(value.strip().lower())
    except ValueError:
        return None


def _impact(value: object) -> Decimal | None:
    """A positive share of the exposure, normalised off percentage points and capped."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return None
    try:
        impact = Decimal(str(value))
    except InvalidOperation:
        return None

    if impact <= 0:
        return None
    if impact > PERCENT_POINT_THRESHOLD:
        impact /= 100
    return min(impact, MAX_IMPACT_PCT)


def _stated_side(value: object) -> Side | None:
    if not isinstance(value, str):
        return None
    try:
        return Side(value.strip().lower())
    except ValueError:
        return None


def _has_depth(option: MarketOption, side: Side) -> bool:
    quote = option.quote
    return (quote.yes_ask_size if side is Side.YES else quote.no_ask_size) > 0


def _prompt(factor: str, options: Sequence[MarketOption]) -> str:
    """List the candidates, saying plainly which side of each can actually be bought.

    Many strikes are quoted on one side only, so a market is useless if the side
    this factor needs is not offered. Stating that up front lets the model avoid
    the dead end rather than being refused after the fact.
    """
    lines = [f"Risk factor: {factor}", "", "Candidate markets:"]
    for index, option in enumerate(options, start=1):
        window = option.quote.exposure_window
        quote = option.quote
        buyable = [
            name
            for name, size in (("YES", quote.yes_ask_size), ("NO", quote.no_ask_size))
            if size > 0
        ]
        lines.append(
            f"{index}. {option.market.ticker} | {option.market.title} | "
            f"{option.frequency}, {window.days}d window settling {window.settles} | "
            f"buyable: {' and '.join(buyable)} | "
            f"yes ask ${quote.yes_ask:.4f} x{quote.yes_ask_size}, "
            f"no ask ${quote.no_ask:.4f} x{quote.no_ask_size}"
        )
    lines.append("")
    lines.append(
        "Only choose a market whose buyable side matches the direction you give: "
        "a business hurt when the factor rises needs YES on an 'above' market or "
        "NO on a 'below' one."
    )
    return "\n".join(lines)
