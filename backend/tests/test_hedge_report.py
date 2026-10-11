from app.hedge_report import build_hedge_report, recurring_frequency, recurring_market_name
from app.kalshi_client import KalshiMarket
from app.position_sizing import PlannedBet, UnhedgedRisk
from app.trend_detection import HedgeableCategory
from tests.sample_data import CATEGORIES, HISTORY, MARKETS

RAIN = PlannedBet(
    category="rain", ticker="KXRAINAUSM-26OCT-4", side="YES", amount_usd=100, frequency="Monthly, May–Jun",
    trade_months=[4, 5], hit_months=[4], risk_explanation="Rain empties the patio.", rationale="Pays out in rainy months.",
)
GAS = PlannedBet(
    category="gas_prices", ticker="KXAAAGASM-26OCT31-3.50", side="NO", amount_usd=70, frequency="Quarterly",
    trade_months=[0], hit_months=[0], risk_explanation="Gas costs for the van.", rationale="Covers fuel spikes.",
)


def test_builds_bets_in_frontend_shape():
    report = build_hedge_report(CATEGORIES, [RAIN, GAS], [], MARKETS, HISTORY)

    assert report["bets"] == [
        {
            "risk": {"factor": "Rain", "explanation": "Rain empties the patio."},
            "market": "Rain in Austin? Above 4 inches",
            "ticker": "KXRAINAUSM-26OCT-4",
            "side": "YES",
            "amountUsd": 100,
            "frequency": "Monthly, May–Jun - a new contract each month",
            "tradeMonths": [4, 5],
            "rationale": "Pays out in rainy months.",
            "monthlyNetUsd": [0, 0, 0, 0, 400, -100, 0, 0, 0, 0, 0, 0],
        },
        {
            "risk": {"factor": "Gas prices", "explanation": "Gas costs for the van."},
            "market": "Will average gas prices be above $3.50? Above $3.50",
            "ticker": "KXAAAGASM-26OCT31-3.50",
            "side": "NO",
            "amountUsd": 70,
            "frequency": "Quarterly - a new contract each month",
            "tradeMonths": [0],
            "rationale": "Covers fuel spikes.",
            "monthlyNetUsd": [30, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        },
    ]


def test_includes_profit_series_and_period():
    report = build_hedge_report(CATEGORIES, [], [], MARKETS, HISTORY)

    assert report["bets"] == []
    assert report["unhedgedRisks"] == []
    assert report["simulatedPeriod"] == "2024"
    assert report["profitSeries"][0] == {"period": "Jan", "expected": 1000, "actual": 1000}
    assert len(report["profitSeries"]) == 12


GPU = HedgeableCategory(category="gpu", label="GPU prices", reasoning="Compute is our biggest cost.", confidence=80, market_family="none")


def _unhedged_entry(risk: UnhedgedRisk) -> dict:
    return build_hedge_report(CATEGORIES + [GPU], [], [risk], MARKETS, HISTORY)["unhedgedRisks"][0]


def test_unhedged_risk_without_any_market():
    assert _unhedged_entry(UnhedgedRisk(category="gpu", reason="no_market")) == {
        "factor": "GPU prices",
        "explanation": "Compute is our biggest cost.",
        "reason": "Kalshi doesn't list a market for this yet.",
    }


def test_unhedged_weather_outside_supported_cities():
    assert _unhedged_entry(UnhedgedRisk(category="rain", reason="no_city_market"))["reason"] == (
        "Kalshi only lists weather markets for Austin, New York, Chicago, Los Angeles, Miami, San Francisco and Seattle."
    )


def test_unhedged_when_no_market_fits():
    assert _unhedged_entry(UnhedgedRisk(category="rain", reason="no_fit"))["reason"] == "None of the open Kalshi markets fit this risk closely enough."


def test_unhedged_when_already_covered_names_the_covering_trade():
    assert _unhedged_entry(UnhedgedRisk(category="gas_prices", reason="duplicate", covered_by="rain"))["reason"] == "Already covered by the Rain trade."


class TestRecurringNaming:
    """Kalshi returns whichever contract is open now, so its title names that one
    instance. A plan that trades the series every May and June must not read as
    "trade the October market in May"."""

    @staticmethod
    def _market(title: str, subtitle: str, ticker: str) -> KalshiMarket:
        return KalshiMarket(ticker, title, subtitle, 0.3)

    def test_strips_a_month_and_year_from_the_title(self):
        market = self._market("Rain in Austin in Oct 2026?", "Above 4 inches", "KXRAINAUSM-26OCT-4")

        assert recurring_market_name(market) == "Rain in Austin? Above 4 inches"

    def test_strips_a_full_date_from_the_title(self):
        market = self._market("Will the maximum temperature be >97° on Oct 11, 2026?", "98° or above", "KXHIGHAUS-26OCT11-T97")

        assert recurring_market_name(market) == "Will the maximum temperature be >97°? 98° or above"

    def test_leaves_a_title_without_a_date_alone(self):
        market = self._market("Will average gas prices be above $4.50?", "Above $4.50", "KXAAAGASM-26OCT31-4.50")

        assert recurring_market_name(market) == "Will average gas prices be above $4.50? Above $4.50"

    def test_handles_a_missing_subtitle(self):
        market = self._market("Rain in Austin in Oct 2026?", "", "KXRAINAUSM-26OCT-4")

        assert recurring_market_name(market) == "Rain in Austin?"

    def test_frequency_says_how_often_a_new_contract_opens(self):
        monthly = self._market("Rain in Austin?", "", "KXRAINAUSM-26OCT-4")
        daily = self._market("Max temperature?", "", "KXHIGHAUS-26OCT11-T97")

        assert recurring_frequency(monthly, "Monthly, May-Jun").endswith("a new contract each month")
        assert recurring_frequency(daily, "Monthly, Jun-Aug").endswith("a new contract each day")

    def test_an_unknown_series_keeps_the_models_label_unchanged(self):
        market = self._market("Something?", "", "KXUNKNOWN-26OCT-1")

        assert recurring_frequency(market, "Quarterly") == "Quarterly - a new contract each month"
