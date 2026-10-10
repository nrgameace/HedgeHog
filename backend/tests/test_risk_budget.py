import pytest

from app.risk_budget import parse_monthly_budget


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("$500 a month", 500),
        ("$6,000 a year", 500),
        ("6000 annually", 500),
        ("$1,500 per quarter", 500),
        ("about 300", 300),
        ("$2k monthly", 2000),
        ("$12.5K/yr", 12500 / 12),
    ],
)
def test_parses_monthly_budget(text, expected):
    assert parse_monthly_budget(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["", "not sure", "   "])
def test_returns_none_without_amount(text):
    assert parse_monthly_budget(text) is None
