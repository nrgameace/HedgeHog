from app.backtest import monthly_stake_peak, scale_amounts_to_budget, simulate_monthly_net


def test_simulate_matches_two_scoops_rain_trade():
    assert simulate_monthly_net(400, 0.15, [3, 4, 5, 8, 9], [4, 5]) == [0, 0, 0, -400, 2267, 2267, 0, 0, -400, -400, 0, 0]


def test_simulate_with_no_hits_only_costs_stakes():
    assert simulate_monthly_net(50, 0.3, [0, 6], []) == [-50, 0, 0, 0, 0, 0, -50, 0, 0, 0, 0, 0]


def test_monthly_stake_peak_sums_overlapping_months():
    assert monthly_stake_peak([(400, [0, 1]), (200, [1]), (50, [2])]) == 600


def test_monthly_stake_peak_of_nothing_is_zero():
    assert monthly_stake_peak([]) == 0


def test_scale_leaves_amounts_under_budget():
    assert scale_amounts_to_budget([(100, [0]), (50, [1])], 300) == [100, 50]


def test_scale_shrinks_proportionally():
    assert scale_amounts_to_budget([(400, [0]), (200, [0])], 300) == [200, 100]


def test_scale_never_below_one():
    assert scale_amounts_to_budget([(1000, [0]), (1, [0])], 10) == [10, 1]


def test_scale_without_budget_only_rounds():
    assert scale_amounts_to_budget([(99.6, [0])], None) == [100]


from app.backtest import cap_amount_to_shortfall, worst_monthly_shortfall
from app.financial_history import MONTH_LABELS, ProfitHistory, ProfitPoint


def _history(shortfalls: dict[int, int]) -> ProfitHistory:
    return ProfitHistory(
        simulated_year=2024,
        points=[
            ProfitPoint(period=label, expected=1000, actual=1000 - shortfalls.get(month, 0))
            for month, label in enumerate(MONTH_LABELS)
        ],
    )


class TestWorstMonthlyShortfall:
    def test_finds_the_deepest_month_among_those_traded(self):
        assert worst_monthly_shortfall(_history({4: 600, 5: 200}), [3, 4, 5]) == 600

    def test_ignores_shortfalls_in_months_not_traded(self):
        assert worst_monthly_shortfall(_history({9: 900}), [3, 4, 5]) == 0

    def test_a_flat_year_has_no_shortfall(self):
        assert worst_monthly_shortfall(_history({}), [0, 1, 2]) == 0


class TestCapAmountToShortfall:
    def test_shrinks_a_stake_that_would_pay_more_than_the_hole(self):
        """600 short at a 0.20 price needs a 120 stake: 120/0.20 pays back exactly 600."""
        assert cap_amount_to_shortfall(300, 0.2, [3, 4, 5], _history({4: 600})) == 120

    def test_leaves_a_stake_that_under_covers_alone(self):
        assert cap_amount_to_shortfall(50, 0.2, [3, 4, 5], _history({4: 600})) == 50

    def test_leaves_the_stake_alone_when_no_traded_month_fell_short(self):
        """Nothing to over-cover, and the budget scaling still applies afterwards."""
        assert cap_amount_to_shortfall(300, 0.2, [0, 1], _history({9: 900})) == 300

    def test_never_caps_below_a_single_dollar(self):
        assert cap_amount_to_shortfall(300, 0.01, [4], _history({4: 10})) == 1

    def test_a_zero_price_cannot_be_capped(self):
        assert cap_amount_to_shortfall(300, 0.0, [4], _history({4: 600})) == 300

    def test_the_capped_payout_matches_the_shortfall(self):
        capped = cap_amount_to_shortfall(1000, 0.25, [4], _history({4: 800}))

        assert round(capped / 0.25) == 800
