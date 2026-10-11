from app.financial_history import ProfitHistory

StakePlan = tuple[float, list[int]]


def simulate_monthly_net(amount_usd: int, price: float, trade_months: list[int], hit_months: list[int]) -> list[int]:
    payout = round(amount_usd / price)
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


def cap_amount_to_shortfall(amount_usd: int, price: float, trade_months: list[int], history: ProfitHistory) -> int:
    """Shrink a stake whose payout would exceed the hole it is filling.

    A contract paying out `amount / price` against a month that was only ever
    `shortfall` short is not a hedge for the excess, it is a bet - and it spends
    budget that could have covered another risk. So the stake is capped at
    `shortfall * price`, which is exactly the full-cover size.

    A month with no shortfall is left alone: there is nothing to over-cover, and
    the budget scaling still applies afterwards.
    """
    shortfall = worst_monthly_shortfall(history, trade_months)
    if shortfall <= 0 or price <= 0:
        return amount_usd
    return max(min(amount_usd, round(shortfall * price)), 1)
