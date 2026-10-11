from app.hedge_report import build_hedge_report
from app.position_sizing import PlannedBet
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
    report = build_hedge_report(CATEGORIES, [RAIN, GAS], MARKETS, HISTORY)

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
    report = build_hedge_report(CATEGORIES, [], MARKETS, HISTORY)

    assert report["bets"] == []
    assert report["simulatedPeriod"] == "2024"
    assert report["profitSeries"][0] == {"period": "Jan", "expected": 1000, "actual": 1000}
    assert len(report["profitSeries"]) == 12
