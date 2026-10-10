import io
import json

from fastapi.testclient import TestClient

from app.akamai_client import AkamaiApiError, AkamaiConfigError
from app.main import app
from app.routes.analyze import MAX_FINANCIALS_CSV_SIZE_BYTES
from app.trend_detection import HedgeableCategory, TrendDetectionError

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


def _post_analyze(answers: str = VALID_ANSWERS, csv_bytes: bytes | None = b"date,revenue\n2026-01-01,412.50\n"):
    files = {"financials": ("financials.csv", io.BytesIO(csv_bytes), "text/csv")} if csv_bytes is not None else None
    return client.post("/analyze", data={"answers": answers}, files=files)


def test_analyze_returns_hedgeable_categories(monkeypatch):
    monkeypatch.setattr(
        "app.routes.analyze.detect_hedgeable_categories",
        lambda answers, financials: [HedgeableCategory(category="rain", label="Rain", reasoning="Rainy weekends hurt sales.")],
    )

    response = _post_analyze()

    assert response.status_code == 200
    assert response.json() == {"hedgeable_categories": [{"category": "rain", "label": "Rain", "reasoning": "Rainy weekends hurt sales."}]}


def test_analyze_accepts_missing_financials_file(monkeypatch):
    captured = {}

    def fake_detect(answers, financials):
        captured["financials"] = financials
        return []

    monkeypatch.setattr("app.routes.analyze.detect_hedgeable_categories", fake_detect)

    response = _post_analyze(csv_bytes=None)

    assert response.status_code == 200
    assert captured["financials"] == []


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
    def raise_config_error(answers, financials):
        raise AkamaiConfigError("missing required environment variable(s): AKAMAI_API_KEY")

    monkeypatch.setattr("app.routes.analyze.detect_hedgeable_categories", raise_config_error)

    response = _post_analyze()

    assert response.status_code == 500


def test_analyze_maps_akamai_api_error_to_502(monkeypatch):
    def raise_api_error(answers, financials):
        raise AkamaiApiError("Akamai API returned 401: invalid credentials")

    monkeypatch.setattr("app.routes.analyze.detect_hedgeable_categories", raise_api_error)

    response = _post_analyze()

    assert response.status_code == 502


def test_analyze_maps_trend_detection_error_to_502(monkeypatch):
    def raise_trend_error(answers, financials):
        raise TrendDetectionError("model reply was not valid JSON")

    monkeypatch.setattr("app.routes.analyze.detect_hedgeable_categories", raise_trend_error)

    response = _post_analyze()

    assert response.status_code == 502
