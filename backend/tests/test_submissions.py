import io

from fastapi.testclient import TestClient

from app.main import app
from app.routes.submissions import MAX_FINANCIALS_CSV_SIZE_BYTES

client = TestClient(app)


def _post_submission(csv_bytes: bytes, industry: str = "ice cream shop", loss_factors: str = "rainy days, gas prices"):
    return client.post(
        "/submissions",
        data={"industry": industry, "loss_factors": loss_factors},
        files={"financials": ("financials.csv", io.BytesIO(csv_bytes), "text/csv")},
    )


def _csv_of_exact_size(total_bytes: int) -> bytes:
    header = b"note\n"
    row = b"a" * 50 + b"\n"
    remaining = total_bytes - len(header)
    full_rows, leftover = divmod(remaining, len(row))
    content = header + row * full_rows
    if leftover:
        content += b"a" * (leftover - 1) + b"\n"
    return content


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


def test_create_submission_accepts_file_at_exact_size_limit():
    csv_at_limit = _csv_of_exact_size(MAX_FINANCIALS_CSV_SIZE_BYTES)
    assert len(csv_at_limit) == MAX_FINANCIALS_CSV_SIZE_BYTES

    response = _post_submission(csv_at_limit)

    assert response.status_code == 200


def test_create_submission_rejects_file_one_byte_over_size_limit():
    csv_over_limit = _csv_of_exact_size(MAX_FINANCIALS_CSV_SIZE_BYTES + 1)
    assert len(csv_over_limit) == MAX_FINANCIALS_CSV_SIZE_BYTES + 1

    response = _post_submission(csv_over_limit)

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
