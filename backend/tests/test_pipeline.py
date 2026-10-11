from pathlib import Path

import pytest

from app.csv_parsing import parse_csv_rows
from app.financial_history import FinancialHistoryError
from app.pipeline import run_analysis
from app.position_sizing import PlannedBet
from tests.sample_data import ANSWERS, CATEGORIES, MARKETS

TWO_SCOOPS_ROWS = parse_csv_rows((Path(__file__).resolve().parents[2] / "demo-data/two-scoops-creamery/financials.csv").read_bytes())

RAIN = PlannedBet(
    category="rain", ticker="KXRAINAUSM-26OCT-4", side="YES", amount_usd=400, frequency="Monthly", trade_months=[4, 5],
    hit_months=[4], risk_explanation="Rain empties the patio.", rationale="Pays out in rainy months.",
)


def _must_not_be_called(*args, **kwargs):
    raise AssertionError("should not be called")


@pytest.fixture
def fake_steps(monkeypatch):
    calls = {}

    def fake_plan(answers, categories, history, notes, markets):
        calls.update(categories=categories, history=history, notes=notes, markets=markets)
        return [RAIN]

    monkeypatch.setattr("app.pipeline.detect_hedgeable_categories", lambda answers, rows: CATEGORIES)
    monkeypatch.setattr("app.pipeline.load_candidate_markets", lambda series: MARKETS)
    monkeypatch.setattr("app.pipeline.plan_positions", fake_plan)
    return calls


def test_passes_trend_categories_into_position_sizing(fake_steps):
    run_analysis(ANSWERS, TWO_SCOOPS_ROWS)

    assert fake_steps["categories"] == CATEGORIES
    assert fake_steps["markets"] == MARKETS
    assert fake_steps["history"].simulated_year == 2024
    assert fake_steps["notes"][4].startswith("Rainiest May")


def test_returns_report_for_simulated_year(fake_steps):
    report = run_analysis(ANSWERS, TWO_SCOOPS_ROWS)

    assert report["simulatedPeriod"] == "2024"
    assert [bet["ticker"] for bet in report["bets"]] == ["KXRAINAUSM-26OCT-4"]


def test_scales_bets_to_budget(fake_steps):
    answers = ANSWERS.__class__(**{**ANSWERS.__dict__, "risk_budget": "$100 a month"})

    report = run_analysis(answers, TWO_SCOOPS_ROWS)

    assert report["bets"][0]["amountUsd"] == 100


def test_no_categories_skips_kalshi_and_sizing(monkeypatch):
    monkeypatch.setattr("app.pipeline.detect_hedgeable_categories", lambda answers, rows: [])
    monkeypatch.setattr("app.pipeline.load_candidate_markets", _must_not_be_called)
    monkeypatch.setattr("app.pipeline.plan_positions", _must_not_be_called)

    report = run_analysis(ANSWERS, TWO_SCOOPS_ROWS)

    assert report["bets"] == []
    assert len(report["profitSeries"]) == 12


def test_bad_csv_fails_before_model_calls(monkeypatch):
    monkeypatch.setattr("app.pipeline.detect_hedgeable_categories", _must_not_be_called)

    with pytest.raises(FinancialHistoryError):
        run_analysis(ANSWERS, [{"month": "2024-01", "revenue": "1"}])
