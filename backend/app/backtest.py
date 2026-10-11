from app.financial_history import ProfitHistory

StakePlan = tuple[float, list[int]]


def simulate_monthly_net(amount_usd: int, price: float, trade_months: list[int], hit_months: list[int]) -> list[int]:
    # A contract costs `price` and returns its $1 notional, so a stake buys
    # `amount / price` of them. An unpriced side cannot be bought at all.
    payout = round(amount_usd / price) if price > 0 else 0
    return [(payout if month in hit_months else 0) - (amount_usd if month in trade_months else 0) for month in range(12)]


def monthly_stake_peak(bets: list[StakePlan]) -> float:
    return max((sum(amount for amount, months in bets if month in months) for month in range(12)), default=0)


def scale_amounts_to_budget(bets: list[StakePlan], monthly_budget: float | None) -> list[int]:
    peak = monthly_stake_peak(bets)
    factor = monthly_budget / peak if monthly_budget is not None and peak > monthly_budget else 1
    return [max(round(amount * factor), 1) for amount, _ in bets]


def worst_monthly_shortfall(history: ProfitHistory, trade_months: list[int]) -> float:
    """The deepest month the hedge is meant to cover, among the months it is placed."""
    return max((point.expected - point.actual for month, point in enumerate(history.points) if month in trade_months), default=0)


def full_cover_stake(price: float, trade_months: list[int], history: ProfitHistory) -> float:
    """The monthly stake whose payout exactly fills the deepest month it covers.

    A contract returns `stake / price`, so filling a hole of `shortfall` costs
    `shortfall * price`. That is the whole of the hedging arithmetic: the stake
    follows from the size of the hole and the price of cover, and nothing else.

    Note what is absent - the model's own guess at an amount. Sizing is
    arithmetic, and the stake it produced was simply unrelated to the hole: on
    the ice cream demo it chose $400 against a $12,523 June shortfall that
    justified $6,136 at a 49c price, and the old code could only ever shrink that
    further. Starting from full cover and reducing to fit the budget means the
    budget actually gets used.

    Cadence does not enter. A daily series needs about thirty contracts to cover
    a month, but the monthly outlay is still `shortfall * price` either way -
    thirty contracts at a thirtieth of the stake. Cadence matters only for
    describing a trade, not for pricing it.
    """
    shortfall = worst_monthly_shortfall(history, trade_months)
    return shortfall * price if shortfall > 0 and price > 0 else 0.0
