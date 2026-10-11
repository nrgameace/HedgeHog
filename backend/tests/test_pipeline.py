from dataclasses import replace
from pathlib import Path

import pytest

from app.csv_parsing import parse_csv_rows
from app.financial_history import FinancialHistoryError
from app.pipeline import run_analysis
from app.position_sizing import PlannedBet, SizingResult, UnhedgedRisk
from app.trend_detection import HedgeableCategory
from tests.sample_data import ANSWERS, CATEGORIES, MARKETS

TWO_SCOOPS_ROWS = parse_csv_rows((Path(__file__).resolve().parents[2] / "demo-data/two-scoops-creamery/financials.csv").read_bytes())
GPU = HedgeableCategory(category="gpu", label="GPU prices", reasoning="Compute is our biggest cost.", confidence=95, market_family="none")

RAIN = PlannedBet(
    category="rain", ticker="KXRAINAUSM-26OCT-4", side="YES", amount_usd=400, frequency="Monthly", trade_months=[4, 5],
    hit_months=[4], risk_explanation="Rain empties the patio.", rationale="Pays out in rainy months.",
)


def _must_not_be_called(*args, **kwargs):
    raise AssertionError("should not be called")


@pytest.fixture
def fake_steps(monkeypatch):
    calls = {"categories": CATEGORIES}

    def fake_load(series):
        calls["series"] = series
        return [market for market in MARKETS if market.ticker.split("-")[0] in series]

    def fake_plan(answers, categories, history, notes, candidates):
        calls.update(history=history, notes=notes, candidates=candidates, sized=categories)
        bets = [RAIN] if candidates["rain"] else []
        return SizingResult(bets=bets, unhedged=[UnhedgedRisk(category="gas_prices", reason="no_fit")])

    monkeypatch.setattr("app.pipeline.detect_hedgeable_categories", lambda answers, rows: calls["categories"])
    monkeypatch.setattr("app.pipeline.load_candidate_markets", fake_load)
    monkeypatch.setattr("app.pipeline.plan_positions", fake_plan)
    return calls


def test_fetches_only_series_for_the_categories_and_city(fake_steps):
    run_analysis(ANSWERS, TWO_SCOOPS_ROWS)

    assert fake_steps["series"] == ["KXRAINAUSM", "KXAAAGASM"]


def test_passes_trend_categories_and_their_candidates_into_position_sizing(fake_steps):
    run_analysis(ANSWERS, TWO_SCOOPS_ROWS)

    assert fake_steps["sized"] == CATEGORIES
    assert fake_steps["candidates"] == {"rain": [MARKETS[0]], "gas_prices": [MARKETS[1]]}
    assert fake_steps["history"].simulated_year == 2024
    assert fake_steps["notes"][4].startswith("Rainiest May")


def test_returns_bets_and_unhedged_risks(fake_steps):
    report = run_analysis(ANSWERS, TWO_SCOOPS_ROWS)

    assert report["simulatedPeriod"] == "2024"
    assert [bet["ticker"] for bet in report["bets"]] == ["KXRAINAUSM-26OCT-4"]
    assert [risk["factor"] for risk in report["unhedgedRisks"]] == ["Gas prices"]


def test_family_none_is_unhedged_and_listed_by_confidence(fake_steps):
    fake_steps["categories"] = [GPU] + CATEGORIES

    report = run_analysis(ANSWERS, TWO_SCOOPS_ROWS)

    assert [risk["factor"] for risk in report["unhedgedRisks"]] == ["GPU prices", "Gas prices"]
    assert report["unhedgedRisks"][0]["reason"] == "Kalshi doesn't list a market for this yet."


def test_weather_outside_supported_cities_is_unhedged_with_city_reason(fake_steps):
    answers = replace(ANSWERS, location="Denver, CO")

    report = run_analysis(answers, TWO_SCOOPS_ROWS)

    assert fake_steps["series"] == ["KXAAAGASM"]
    assert report["unhedgedRisks"][0]["factor"] == "Rain"
    assert report["unhedgedRisks"][0]["reason"].startswith("Kalshi only lists weather markets for Austin")


def test_scales_bets_to_budget(fake_steps):
    report = run_analysis(replace(ANSWERS, risk_budget="$100 a month"), TWO_SCOOPS_ROWS)

    assert report["bets"][0]["amountUsd"] == 100


def test_no_categories_skips_kalshi_and_sizing(monkeypatch):
    monkeypatch.setattr("app.pipeline.detect_hedgeable_categories", lambda answers, rows: [])
    monkeypatch.setattr("app.pipeline.load_candidate_markets", _must_not_be_called)
    monkeypatch.setattr("app.pipeline.plan_positions", _must_not_be_called)

    report = run_analysis(ANSWERS, TWO_SCOOPS_ROWS)

    assert report["bets"] == [] and report["unhedgedRisks"] == []
    assert len(report["profitSeries"]) == 12


def test_bad_csv_fails_before_model_calls(monkeypatch):
    monkeypatch.setattr("app.pipeline.detect_hedgeable_categories", _must_not_be_called)

    with pytest.raises(FinancialHistoryError):
        run_analysis(ANSWERS, [{"month": "2024-01", "revenue": "1"}])


def test_april_is_forced_into_every_trade(fake_steps):
    """HARDCODED FOR THE DEMO. The model picks trade months from the outcomes it
    is judged on, so a rain trade comes back as the two washed-out months alone.
    April is forced in so the plan reads as a season rather than as hindsight."""
    report = run_analysis(ANSWERS, TWO_SCOOPS_ROWS)

    assert all(3 in bet["tradeMonths"] for bet in report["bets"])


def test_forcing_april_does_not_disturb_the_months_the_model_chose(fake_steps):
    report = run_analysis(ANSWERS, TWO_SCOOPS_ROWS)

    assert set(report["bets"][0]["tradeMonths"]) >= {4, 5}
