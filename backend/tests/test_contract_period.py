import pytest

from app.contract_period import (
    DAYS_PER_MONTH,
    contracts_per_month,
    covers_whole_month,
    stake_for_month,
)
from app.market_catalog import DAILY, MONTHLY, cadence_of


class TestCadence:
    @pytest.mark.parametrize("ticker", ["KXHIGHAUS-26OCT11-T97", "KXHIGHNY-26OCT11-T62", "KXWTI-26OCT1314-T98.99"])
    def test_per_day_series_are_daily(self, ticker):
        assert cadence_of(ticker) == DAILY

    @pytest.mark.parametrize("ticker", ["KXRAINAUSM-26OCT-4", "KXCPI-26OCT-T0.3", "KXFED-26DEC-T4.50"])
    def test_series_covering_a_month_or_longer_are_monthly(self, ticker):
        assert cadence_of(ticker) == MONTHLY

    def test_a_day_precise_ticker_can_still_be_a_monthly_contract(self):
        """KXAAAGASM-26OCT31 settles a monthly average, so the ticker misleads."""
        assert cadence_of("KXAAAGASM-26OCT31-3.50") == MONTHLY

    @pytest.mark.parametrize("ticker", ["", "NODATE", "KXUNKNOWN-26OCT11-T5"])
    def test_an_unknown_series_reads_as_monthly(self, ticker):
        """Under-scaling risks too little cover; over-scaling overspends on a
        cadence that was never there."""
        assert cadence_of(ticker) == MONTHLY


class TestContractsPerMonth:
    def test_one_monthly_contract_covers_the_month(self):
        assert contracts_per_month("KXRAINAUSM-26OCT-4") == 1.0

    def test_a_daily_series_needs_a_month_of_them(self):
        assert contracts_per_month("KXHIGHAUS-26OCT11-T97") == pytest.approx(DAYS_PER_MONTH)

    def test_the_calendar_average_is_used_not_thirty(self):
        """Thirty would leave a month of daily cover short by half a week a year."""
        assert DAYS_PER_MONTH == pytest.approx(30.4166, abs=0.001)

    def test_a_daily_contract_costs_about_thirty_times_a_monthly_one_to_cover_a_month(self):
        daily = contracts_per_month("KXHIGHAUS-26OCT11-T97")
        monthly = contracts_per_month("KXRAINAUSM-26OCT-4")

        assert daily / monthly > 30


class TestStakeForMonth:
    def test_a_monthly_contract_needs_no_scaling(self):
        assert stake_for_month(300, "KXRAINAUSM-26OCT-4") == 300

    def test_a_daily_contract_is_scaled_to_a_month_of_them(self):
        """$1 a day is what covering one day costs; a month costs about thirty."""
        assert stake_for_month(1, "KXHIGHAUS-26OCT11-T97") == 30

    def test_never_scales_below_a_dollar(self):
        assert stake_for_month(0, "KXHIGHAUS-26OCT11-T97") == 1


class TestCoversWholeMonth:
    def test_true_for_a_monthly_contract(self):
        assert covers_whole_month("KXRAINAUSM-26OCT-4") is True

    def test_false_for_a_daily_contract(self):
        assert covers_whole_month("KXHIGHAUS-26OCT11-T97") is False
