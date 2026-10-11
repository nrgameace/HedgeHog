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
