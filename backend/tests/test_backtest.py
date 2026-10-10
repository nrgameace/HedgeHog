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
