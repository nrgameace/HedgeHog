from decimal import Decimal
from pathlib import Path

import pytest

from app.csv_parsing import parse_csv_rows
from app.hedge.exposure import (
    DAYS_PER_MONTH,
    daily_rate,
    find_column,
    parse_money,
    parse_risk_budget,
    recent_monthly_mean,
)

DEMO_DATA = Path(__file__).resolve().parents[2].parent / "demo-data"


def demo_rows(business: str) -> list[dict[str, str]]:
    return parse_csv_rows((DEMO_DATA / business / "financials.csv").read_bytes())


class TestParseMoney:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1234", "1234"),
            ("1234.50", "1234.50"),
            ("$1,234.50", "1234.50"),
            ("  $800  ", "800"),
            ("-500", "-500"),
            ("(500)", "-500"),
            ("$1,000,000", "1000000"),
            ("0", "0"),
        ],
    )
    def test_parses_the_shapes_spreadsheets_actually_export(self, text, expected):
        assert parse_money(text) == Decimal(expected)

    @pytest.mark.parametrize("text", ["", "   ", "n/a", "a few hundred", "-", "TBD"])
    def test_returns_none_for_anything_unparseable(self, text):
        assert parse_money(text) is None


class TestParseRiskBudget:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("$800 a month", "800"),
            ("800", "800"),
            ("$800/mo", "800"),
            ("about $1,500 per month", "1500"),
        ],
    )
    def test_reads_a_monthly_amount(self, text, expected):
        assert parse_risk_budget(text) == Decimal(expected)

    @pytest.mark.parametrize("text", ["$9,600 a year", "$9600 annually", "$9,600 per year"])
    def test_divides_an_annual_amount_into_a_monthly_one(self, text):
        assert parse_risk_budget(text) == Decimal("800")

    def test_scales_a_weekly_amount_up_to_a_month(self):
        assert parse_risk_budget("$100 a week") == Decimal("100") * 52 / 12

    def test_takes_the_first_amount_when_a_range_is_given(self):
        """Matches the frontend's convention so both ends read the same answer."""
        assert parse_risk_budget("$500 to $800 a month") == Decimal("500")

    @pytest.mark.parametrize("text", ["", "not much", "whatever it takes"])
    def test_returns_none_when_no_amount_is_stated(self, text):
        assert parse_risk_budget(text) is None

    def test_a_negative_budget_is_refused(self):
        assert parse_risk_budget("-$500 a month") is None


class TestFindColumn:
    def test_finds_a_revenue_column_in_the_ice_cream_csv(self):
        rows = demo_rows("two-scoops-creamery")

        assert find_column(rows, "total_revenue", "revenue") == "total_revenue"

    def test_finds_a_cost_column_in_the_ai_startup_csv(self):
        rows = demo_rows("quillstack-ai")

        assert find_column(rows, "gpu_compute_cost") == "gpu_compute_cost"

    def test_prefers_an_exact_name_over_a_partial_match(self):
        rows = [{"revenue_growth": "1", "revenue": "2"}]

        assert find_column(rows, "revenue") == "revenue"

    def test_falls_back_to_a_partial_match(self):
        rows = [{"monthly_total_revenue_usd": "1"}]

        assert find_column(rows, "total_revenue") == "monthly_total_revenue_usd"

    def test_returns_none_when_nothing_matches(self):
        assert find_column([{"month": "2024-01"}], "revenue") is None

    def test_returns_none_for_no_rows(self):
        assert find_column([], "revenue") is None


class TestRecentMonthlyMean:
    def test_averages_the_most_recent_months_of_the_ice_cream_csv(self):
        rows = demo_rows("two-scoops-creamery")

        mean = recent_monthly_mean(rows, "total_revenue", months=12)

        # Two Scoops is an established shop; a plausible monthly revenue, not a
        # stray single row or a cumulative total.
        assert Decimal("20000") < mean < Decimal("300000")

    def test_uses_only_the_requested_number_of_trailing_months(self):
        rows = [{"total_revenue": "100"}, {"total_revenue": "200"}, {"total_revenue": "900"}]

        assert recent_monthly_mean(rows, "total_revenue", months=2) == Decimal("550")

    def test_skips_unparseable_and_blank_values(self):
        rows = [{"r": "100"}, {"r": ""}, {"r": "n/a"}, {"r": "300"}]

        assert recent_monthly_mean(rows, "r", months=12) == Decimal("200")

    def test_returns_none_when_no_value_parses(self):
        assert recent_monthly_mean([{"r": "n/a"}], "r") is None

    def test_returns_none_for_a_missing_column(self):
        assert recent_monthly_mean([{"r": "100"}], "absent") is None

    def test_returns_none_for_no_rows(self):
        assert recent_monthly_mean([], "r") is None


class TestDailyRate:
    def test_spreads_a_monthly_amount_across_an_average_month(self):
        assert daily_rate(Decimal("30000")) == Decimal("30000") / DAYS_PER_MONTH

    def test_uses_the_calendar_average_rather_than_thirty_days(self):
        """365/12, so a year of daily rate adds back to a year of the monthly figure."""
        assert daily_rate(Decimal("1200")) * DAYS_PER_MONTH * 12 == Decimal("14400")

    def test_an_ice_cream_shops_daily_revenue_is_plausible(self):
        rows = demo_rows("two-scoops-creamery")

        rate = daily_rate(recent_monthly_mean(rows, "total_revenue", months=12))

        assert Decimal("500") < rate < Decimal("10000")
