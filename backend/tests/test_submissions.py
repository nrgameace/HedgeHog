import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _post_submission(csv_bytes: bytes, industry: str = "ice cream shop", loss_factors: str = "rainy days, gas prices"):
    return client.post(
        "/submissions",
        data={"industry": industry, "loss_factors": loss_factors},
        files={"financials": ("financials.csv", io.BytesIO(csv_bytes), "text/csv")},
    )


def test_create_submission_returns_parsed_data():
    csv_bytes = b"date,revenue\n2026-01-01,412.50\n"

    response = _post_submission(csv_bytes)

    assert response.status_code == 200
    assert response.json() == {
        "industry": "ice cream shop",
        "loss_factors": "rainy days, gas prices",
        "financials": [{"date": "2026-01-01", "revenue": "412.50"}],
    }


def test_create_submission_rejects_file_over_size_limit():
    oversized_csv = b"date,revenue\n" + b"2026-01-01,412.50\n" * 400_000

    response = _post_submission(oversized_csv)

    assert response.status_code == 413


def test_create_submission_rejects_malformed_csv():
    ragged_csv = b"date,revenue\n2026-01-01,412.50,extra\n"

    response = _post_submission(ragged_csv)

    assert response.status_code == 400
    assert "detail" in response.json()


def test_create_submission_requires_industry_field():
    response = client.post(
        "/submissions",
        data={"loss_factors": "rainy days"},
        files={"financials": ("financials.csv", io.BytesIO(b"date,revenue\n"), "text/csv")},
    )

    assert response.status_code == 422
