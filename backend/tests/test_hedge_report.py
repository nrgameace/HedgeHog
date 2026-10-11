from app.hedge_report import build_hedge_report
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
            "market": "Rain in Austin in Oct 2026? Above 4 inches",
            "ticker": "KXRAINAUSM-26OCT-4",
            "side": "YES",
            "amountUsd": 100,
            "frequency": "Monthly, May–Jun",
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
            "frequency": "Quarterly",
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
