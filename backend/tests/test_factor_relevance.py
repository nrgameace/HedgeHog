from pathlib import Path

import pytest

from app.csv_parsing import parse_csv_rows
from app.factor_relevance import (
    MIN_DRIVER_SPREAD,
    driver_is_flat,
    drop_stale_factors,
    proxy_column,
    relative_spread,
)
from app.trend_detection import HedgeableCategory

DEMO_DATA = Path(__file__).resolve().parents[2] / "demo-data"


def demo_rows(business: str) -> list[dict[str, str]]:
    return parse_csv_rows((DEMO_DATA / business / "financials.csv").read_bytes())


def factor(slug: str, label: str = "", family: str = "weather") -> HedgeableCategory:
    return HedgeableCategory(
        category=slug, label=label or slug.replace("_", " ").title(), reasoning="because",
        confidence=80, market_family=family,
    )


def rows_for(column: str, values: list[float]) -> list[dict[str, str]]:
    return [
        {"month": f"2024-{m + 1:02d}", "operating_income": "1000", column: str(value)}
        for m, value in enumerate(values)
    ]


class TestProxyColumn:
    @pytest.mark.parametrize(
        ("slug", "expected"),
        [
            ("dairy_prices", "dairy_cost_per_gallon"),
            ("electricity_prices", "electricity_cost"),
            ("interest_rates", "loan_interest_rate"),
        ],
    )
    def test_matches_a_factor_to_its_driver_column(self, slug, expected):
        assert proxy_column(demo_rows("two-scoops-creamery"), factor(slug)) == expected

    def test_matches_through_a_synonym(self):
        """The factor says gas, the CSV says fuel."""
        assert proxy_column(demo_rows("two-scoops-creamery"), factor("gas_prices")) == "fuel_cost_per_gallon"

    def test_matches_gpu_costs_in_the_startup_csv(self):
        assert proxy_column(demo_rows("quillstack-ai"), factor("gpu_prices")) is not None

    def test_weather_has_no_driver_column_anywhere(self):
        """Which is why a missing column must never be treated as a failed test."""
        assert proxy_column(demo_rows("two-scoops-creamery"), factor("austin_rain")) is None
        assert proxy_column(demo_rows("two-scoops-creamery"), factor("extreme_heat")) is None

    def test_never_matches_an_output_column(self):
        """Revenue moving is the business moving, not evidence of an external driver."""
        rows = [{"month": "2024-01", "operating_income": "1", "revenue_growth": "2"}]

        assert proxy_column(rows, factor("revenue_growth")) is None

    def test_returns_none_for_no_rows(self):
        assert proxy_column([], factor("gas_prices")) is None


class TestRelativeSpread:
    def test_a_flat_column_has_no_spread(self):
        assert relative_spread(rows_for("cost", [10.0] * 12), "cost") == 0.0

    def test_measures_range_against_the_level(self):
        assert relative_spread(rows_for("cost", [8.0, 12.0] * 6), "cost") == pytest.approx(0.4)

    def test_is_scale_free(self):
        """A $4 dairy price and a $4,000 power bill must be judged the same way."""
        small = relative_spread(rows_for("cost", [4.0, 5.0] * 6), "cost")
        large = relative_spread(rows_for("cost", [4000.0, 5000.0] * 6), "cost")

        assert small == pytest.approx(large)

    def test_returns_none_with_too_few_points_to_judge(self):
        assert relative_spread(rows_for("cost", [1.0, 2.0]), "cost") is None

    def test_returns_none_for_a_missing_column(self):
        assert relative_spread(rows_for("cost", [1.0] * 12), "absent") is None


class TestDriverIsFlat:
    def test_a_contracted_price_reads_as_flat(self):
        """Two Scoops' dairy is fixed at $4.25; background.md says do not hedge it."""
        assert driver_is_flat(demo_rows("two-scoops-creamery"), factor("dairy_prices")) is True

    def test_a_fixed_rent_reads_as_flat(self):
        assert driver_is_flat(demo_rows("two-scoops-creamery"), factor("rent")) is True

    @pytest.mark.parametrize("slug", ["electricity_prices", "interest_rates"])
    def test_a_moving_driver_is_not_flat(self, slug):
        """Both are listed under "should hedge" in background.md."""
        assert driver_is_flat(demo_rows("two-scoops-creamery"), factor(slug)) is False

    def test_gpu_prices_are_not_flat_for_the_startup(self):
        assert driver_is_flat(demo_rows("quillstack-ai"), factor("gpu_prices")) is False

    def test_a_factor_with_no_driver_column_is_never_vetoed(self):
        assert driver_is_flat(demo_rows("two-scoops-creamery"), factor("austin_rain")) is False

    def test_the_threshold_is_what_separates_them(self):
        barely_moving = rows_for("fuel_cost", [10.0, 10.0 * (1 + MIN_DRIVER_SPREAD / 2)] * 6)
        clearly_moving = rows_for("fuel_cost", [10.0, 10.0 * (1 + MIN_DRIVER_SPREAD * 3)] * 6)

        assert driver_is_flat(barely_moving, factor("fuel_cost")) is True
        assert driver_is_flat(clearly_moving, factor("fuel_cost")) is False


class TestDropStaleFactors:
    def test_splits_live_factors_from_stale_ones(self):
        rows = demo_rows("two-scoops-creamery")
        proposed = [factor("austin_rain"), factor("dairy_prices"), factor("electricity_prices")]

        live, stale = drop_stale_factors(rows, proposed)

        assert [c.category for c in live] == ["austin_rain", "electricity_prices"]
        assert [c.category for c in stale] == ["dairy_prices"]

    def test_keeps_the_proposed_order(self):
        rows = demo_rows("two-scoops-creamery")
        proposed = [factor("electricity_prices"), factor("interest_rates")]

        live, _ = drop_stale_factors(rows, proposed)

        assert [c.category for c in live] == ["electricity_prices", "interest_rates"]

    def test_nothing_proposed_means_nothing_dropped(self):
        assert drop_stale_factors(demo_rows("quillstack-ai"), []) == ([], [])

    def test_without_financials_nothing_can_be_vetoed(self):
        proposed = [factor("dairy_prices")]

        assert drop_stale_factors([], proposed) == (proposed, [])
