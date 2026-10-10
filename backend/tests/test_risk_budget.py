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
        ("$500, keep it small", 500),
        ("$300 kept aside", 300),
        ("$1.5M a year", 125000),
        ("$500 a month, more by year end", 500),
        ("500-800/month", 500),
        ("about 5% of revenue, or $400 a month", 400),
    ],
)
def test_parses_monthly_budget(text, expected):
    assert parse_monthly_budget(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["", "not sure", "   ", "$0", "5% of revenue"])
def test_returns_none_without_amount(text):
    assert parse_monthly_budget(text) is None
