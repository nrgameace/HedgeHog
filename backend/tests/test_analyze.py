import io
import json

import pytest

from fastapi.testclient import TestClient

from app.akamai_client import AkamaiApiError, AkamaiConfigError
from app.main import app
from app.routes.analyze import MAX_FINANCIALS_CSV_SIZE_BYTES
from app.financial_history import FinancialHistoryError
from app.position_sizing import PositionSizingError
from app.trend_detection import TrendDetectionError

client = TestClient(app)

VALID_ANSWERS = json.dumps(
    {
        "businessDescription": "Ice cream shop with outdoor seating",
        "customers": "Mostly tourists and families in summer",
        "location": "Austin, TX",
        "operationalDependencies": "Refrigeration, a delivery van, foot traffic",
        "keyMaterials": "Dairy, sugar, electricity, gas for the van",
        "pastImpacts": "Rainy weekends, heat waves, gas price spikes",
        "timeOfYear": "June-August is tourist season; winter is slow",
        "lockedInCosts": "Milk is on a fixed-price contract through 2027",
        "riskBudget": "$500 a month",
    }
)


def _post_analyze(answers: str = VALID_ANSWERS, csv_bytes: bytes | None = b"month,operating_income\n2024-01,412.50\n"):
    files = {"financials": ("financials.csv", io.BytesIO(csv_bytes), "text/csv")} if csv_bytes is not None else None
    return client.post("/analyze", data={"answers": answers}, files=files)


REPORT = {"bets": [], "profitSeries": [{"period": "Jan", "expected": 1, "actual": 1}], "simulatedPeriod": "2024"}


def _raise(error: Exception):
    def raiser(answers, financials):
        raise error

    return raiser


def test_analyze_returns_report_from_pipeline(monkeypatch):
    captured = {}

    def fake_run_analysis(answers, financials):
        captured.update(answers=answers, financials=financials)
        return REPORT

    monkeypatch.setattr("app.routes.analyze.run_analysis", fake_run_analysis)

    response = _post_analyze()

    assert response.status_code == 200
    assert response.json() == REPORT
    assert captured["answers"].location == "Austin, TX"
    assert captured["financials"] == [{"month": "2024-01", "operating_income": "412.50"}]


def test_analyze_requires_financials(monkeypatch):
    monkeypatch.setattr("app.routes.analyze.run_analysis", _raise(AssertionError("should not run")))

    response = _post_analyze(csv_bytes=None)

    assert response.status_code == 400
    assert response.json() == {"detail": "Upload your financials CSV so we can simulate your trades."}


def test_analyze_maps_financial_history_error_to_400_with_its_message(monkeypatch):
    monkeypatch.setattr("app.routes.analyze.run_analysis", _raise(FinancialHistoryError("The financials CSV needs a profit column.")))

    response = _post_analyze()

    assert response.status_code == 400
    assert response.json() == {"detail": "The financials CSV needs a profit column."}


def test_analyze_rejects_file_over_size_limit():
    oversized_csv = b"date,revenue\n" + b"2026-01-01,412.50\n" * 400_000

    response = _post_analyze(csv_bytes=oversized_csv)

    assert response.status_code == 413


def test_analyze_rejects_malformed_csv():
    response = _post_analyze(csv_bytes=b"date,revenue\n2026-01-01,412.50,extra\n")

    assert response.status_code == 400


def test_analyze_rejects_invalid_answers_json():
    response = _post_analyze(answers="not json")

    assert response.status_code == 400


def test_analyze_requires_answers_field():
    response = client.post("/analyze", data={}, files={"financials": ("financials.csv", io.BytesIO(b"date,revenue\n"), "text/csv")})

    assert response.status_code == 422


def test_analyze_maps_akamai_config_error_to_500(monkeypatch):
    monkeypatch.setattr("app.routes.analyze.run_analysis", _raise(AkamaiConfigError("missing AKAMAI_API_KEY")))

    response = _post_analyze()

    assert response.status_code == 500
    assert "AKAMAI_API_KEY" not in response.text


@pytest.mark.parametrize("error", [AkamaiApiError("401: invalid credentials"), TrendDetectionError("bad JSON"), PositionSizingError("missing bets")])
def test_analyze_maps_upstream_errors_to_502_without_leaking_details(monkeypatch, error):
    monkeypatch.setattr("app.routes.analyze.run_analysis", _raise(error))

    response = _post_analyze()

    assert response.status_code == 502
    assert str(error) not in response.text
