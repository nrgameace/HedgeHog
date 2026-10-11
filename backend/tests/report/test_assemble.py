from decimal import Decimal
from pathlib import Path

import pytest

from app.csv_parsing import parse_csv_rows
from app.report.assemble import (
    MONTH_LABELS,
    BetReport,
    ProfitPoint,
    build_report,
    latest_full_year,
    month_index,
    monthly_profit,
    proxy_hit_months,
    simulate_net,
    worst_full_year,
)

DEMO_DATA = Path(__file__).resolve().parents[2].parent / "demo-data"


def demo_rows(business: str) -> list[dict[str, str]]:
    return parse_csv_rows((DEMO_DATA / business / "financials.csv").read_bytes())


def rows_for(year: int, values: list[str], column: str = "operating_income") -> list[dict[str, str]]:
    return [{"month": f"{year}-{m + 1:02d}", column: value} for m, value in enumerate(values)]


class TestMonthIndex:
    def test_parses_a_year_month_cell(self):
        assert month_index({"month": "2024-05"}) == (2024, 4)

    def test_january_is_month_zero(self):
        assert month_index({"month": "2024-01"}) == (2024, 0)

    @pytest.mark.parametrize("cell", ["", "2024", "not-a-date", "2024-13", "2024-00"])
    def test_rejects_anything_that_is_not_a_year_month(self, cell):
        assert month_index({"month": cell}) is None


class TestLatestFullYear:
    def test_finds_the_most_recent_complete_year(self):
        rows = rows_for(2023, ["1"] * 12) + rows_for(2024, ["1"] * 12) + rows_for(2025, ["1"] * 3)

        assert latest_full_year(rows) == 2024

    def test_ignores_partial_years_entirely(self):
        assert latest_full_year(rows_for(2025, ["1"] * 11)) is None

    def test_both_demo_businesses_have_a_full_year(self):
        assert latest_full_year(demo_rows("two-scoops-creamery")) is not None
        assert latest_full_year(demo_rows("quillstack-ai")) is not None


class TestMonthlyProfit:
    def test_returns_twelve_labelled_months(self):
        points = monthly_profit(rows_for(2024, ["100"] * 12), "operating_income", 2024)

        assert [p.period for p in points] == list(MONTH_LABELS)

    def test_actual_comes_straight_from_the_csv(self):
        rows = rows_for(2024, [str(100 * (m + 1)) for m in range(12)])

        points = monthly_profit(rows, "operating_income", 2024)

        assert [p.actual for p in points] == [100 * (m + 1) for m in range(12)]

    def test_expected_averages_the_same_month_in_other_years(self):
        """A seasonal business must be compared against its own seasonality."""
        rows = rows_for(2023, ["100"] * 12) + rows_for(2024, ["0"] * 12) + rows_for(2025, ["300"] * 12)

        points = monthly_profit(rows, "operating_income", 2024)

        assert {p.expected for p in points} == {200}
        assert {p.actual for p in points} == {0}

    def test_expected_falls_back_to_the_actual_when_there_is_no_other_year(self):
        points = monthly_profit(rows_for(2024, ["150"] * 12), "operating_income", 2024)

        assert [p.expected for p in points] == [150] * 12

    def test_a_missing_month_reads_as_zero_rather_than_crashing(self):
        rows = [{"month": "2024-01", "operating_income": "500"}]

        points = monthly_profit(rows, "operating_income", 2024)

        assert points[0].actual == 500
        assert points[5].actual == 0

    def test_the_washed_out_2024_summer_shows_up_as_a_shortfall(self):
        """May-June 2024 is the clearest risk in the demo data, per its background.md."""
        rows = demo_rows("two-scoops-creamery")

        points = monthly_profit(rows, "operating_income", 2024)

        assert points[4].actual < points[4].expected
        assert points[5].actual < points[5].expected


class TestProxyHitMonths:
    def test_flags_the_months_in_the_worst_tail(self):
        rows = rows_for(2024, ["1", "1", "1", "1", "1", "1", "1", "1", "1", "9", "9", "9"], "cost")

        assert proxy_hit_months(rows, "cost", 2024) == (9, 10, 11)

    def test_compares_against_the_whole_history_not_just_the_year(self):
        """A quiet year inside a volatile history should register few hits."""
        calm = rows_for(2023, ["1"] * 12, "cost")
        spiky = rows_for(2024, ["9"] * 12, "cost")

        assert proxy_hit_months(calm + spiky, "cost", 2023) == ()
        assert len(proxy_hit_months(calm + spiky, "cost", 2024)) == 12

    def test_returns_nothing_for_a_missing_column(self):
        assert proxy_hit_months(rows_for(2024, ["1"] * 12), "absent", 2024) == ()

    def test_returns_nothing_for_a_year_not_in_the_data(self):
        assert proxy_hit_months(rows_for(2024, ["1"] * 12, "cost"), "cost", 1999) == ()

    def test_finds_the_summer_electricity_peaks_in_the_demo_data(self):
        """background.md points at electricity_cost for the summer peaks."""
        rows = demo_rows("two-scoops-creamery")

        hits = proxy_hit_months(rows, "electricity_cost", 2024)

        assert hits, "expected some month to sit in the worst quartile"
        assert any(month in hits for month in (5, 6, 7, 8)), hits


class TestSimulateNet:
    def test_stakes_every_trade_month_and_pays_only_on_a_hit(self):
        net = simulate_net(Decimal("100"), Decimal("0.25"), trade_months=[0, 1], hit_months=[1])

        assert net[0] == -100
        assert net[1] == 300  # 100/0.25 = 400 back, less the 100 staked
        assert net[2] == 0

    def test_untraded_months_are_flat_even_when_the_factor_hit(self):
        """Crediting a win on a bet that was never placed would overstate the hedge."""
        net = simulate_net(Decimal("100"), Decimal("0.25"), trade_months=[0], hit_months=[5])

        assert net[5] == 0

    def test_returns_one_value_per_month(self):
        assert len(simulate_net(Decimal("10"), Decimal("0.5"), [0], [0])) == 12

    def test_a_zero_price_cannot_pay_out(self):
        net = simulate_net(Decimal("100"), Decimal("0"), trade_months=[0], hit_months=[0])

        assert net[0] == -100

    def test_a_never_hitting_trade_costs_exactly_its_stakes(self):
        net = simulate_net(Decimal("50"), Decimal("0.3"), trade_months=[0, 3, 6], hit_months=[])

        assert sum(net) == -150


class TestBuildReport:
    BET = BetReport(
        risk_factor="Extreme heat",
        risk_explanation="100F days keep evening crowds home.",
        market="Will Austin hit 98F on Oct 10?",
        ticker="KXHIGHAUS-26OCT10-T98",
        side="YES",
        amount_usd=25,
        frequency="daily",
        trade_months=(5, 6, 7),
        rationale="Pays out on the days that empty the street.",
        monthly_net_usd=(0,) * 12,
    )

    def test_matches_the_shape_the_frontend_declares(self):
        points = [ProfitPoint(label, 10, 5) for label in MONTH_LABELS]

        payload = build_report([self.BET], points, 2024)

        assert set(payload) == {"bets", "profitSeries", "simulatedPeriod", "simulated"}
        assert payload["simulatedPeriod"] == "2024"
        assert payload["simulated"] is True

    def test_a_bet_carries_every_field_the_results_table_reads(self):
        payload = build_report([self.BET], [], 2024)
        bet = payload["bets"][0]

        assert set(bet) == {
            "risk",
            "market",
            "ticker",
            "side",
            "amountUsd",
            "frequency",
            "tradeMonths",
            "rationale",
            "monthlyNetUsd",
        }
        assert bet["risk"] == {
            "factor": "Extreme heat",
            "explanation": "100F days keep evening crowds home.",
        }
        assert bet["tradeMonths"] == [5, 6, 7]
        assert len(bet["monthlyNetUsd"]) == 12

    def test_profit_points_serialise_for_the_chart(self):
        payload = build_report([], [ProfitPoint("Jan", 100, 60)], 2024)

        assert payload["profitSeries"] == [{"period": "Jan", "expected": 100, "actual": 60}]

    def test_an_empty_report_is_still_well_formed(self):
        payload = build_report([], [], 2024)

        assert payload["bets"] == []
        assert payload["profitSeries"] == []


class TestAgainstTheFrontendsMetric:
    def test_a_hedge_that_pays_in_bad_months_mitigates_variance(self):
        """Mirrors frontend/src/report/tradeImpact.ts: downside RMS before vs after."""
        rows = demo_rows("two-scoops-creamery")
        points = monthly_profit(rows, "operating_income", 2024)
        shortfall_months = [i for i, p in enumerate(points) if p.actual < p.expected]

        net = simulate_net(
            Decimal("400"), Decimal("0.15"), trade_months=shortfall_months, hit_months=shortfall_months
        )

        def downside_rms(actuals):
            squares = [max(p.expected - a, 0) ** 2 for p, a in zip(points, actuals)]
            return (sum(squares) / len(squares)) ** 0.5

        before = downside_rms([p.actual for p in points])
        after = downside_rms([p.actual + n for p, n in zip(points, net)])

        assert after < before


class TestWorstFullYear:
    def test_picks_the_year_that_fell_furthest_below_normal(self):
        rows = (
            rows_for(2023, ["100"] * 12)
            + rows_for(2024, ["10"] * 12)
            + rows_for(2025, ["100"] * 12)
        )

        assert worst_full_year(rows, "operating_income") == 2024

    def test_ignores_incomplete_years(self):
        rows = rows_for(2023, ["100"] * 12) + rows_for(2024, ["0"] * 4)

        assert worst_full_year(rows, "operating_income") == 2023

    def test_returns_none_without_a_complete_year(self):
        assert worst_full_year(rows_for(2025, ["1"] * 5), "operating_income") is None

    def test_the_latest_and_worst_year_differ_on_the_demo_data(self):
        """The newest complete year is a good one, so the choice has to be deliberate."""
        rows = demo_rows("two-scoops-creamery")

        latest = latest_full_year(rows)
        worst = worst_full_year(rows, "operating_income")

        assert latest is not None and worst is not None
        assert worst != latest

    def test_the_worst_demo_year_really_does_have_more_downside(self):
        rows = demo_rows("two-scoops-creamery")

        def downside(year):
            points = monthly_profit(rows, "operating_income", year)
            return sum(max(p.expected - p.actual, 0) for p in points)

        assert downside(worst_full_year(rows, "operating_income")) > downside(latest_full_year(rows))
