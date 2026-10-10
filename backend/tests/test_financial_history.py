from pathlib import Path

import pytest

from app.csv_parsing import parse_csv_rows
from app.financial_history import MONTH_LABELS, FinancialHistoryError, ProfitPoint, build_profit_history, monthly_notes

DEMO_DATA = Path(__file__).resolve().parents[2] / "demo-data"


def _demo_rows(business: str) -> list[dict[str, str]]:
    return parse_csv_rows((DEMO_DATA / business / "financials.csv").read_bytes())


def _year_rows(year: int, profits: list[float], column: str = "operating_income") -> list[dict[str, str]]:
    return [{"month": f"{year}-{month + 1:02d}", column: str(profit)} for month, profit in enumerate(profits)]


def test_month_labels_run_jan_to_dec():
    assert MONTH_LABELS == ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def test_two_scoops_simulates_rainy_2024():
    rows = _demo_rows("two-scoops-creamery")
    other_mays = [float(row["operating_income"]) for row in rows if row["month"].endswith("-05") and not row["month"].startswith("2024")]

    history = build_profit_history(rows)

    assert history.simulated_year == 2024
    assert len(history.points) == 12
    assert history.points[4] == ProfitPoint(period="May", expected=round(sum(other_mays) / len(other_mays)), actual=4724)


def test_quillstack_simulates_its_only_complete_year():
    assert build_profit_history(_demo_rows("quillstack-ai")).simulated_year == 2025


def test_picks_worst_of_three_most_recent_complete_years():
    rows = _year_rows(2019, [0] * 12) + _year_rows(2020, [100] * 12) + _year_rows(2021, [10] * 12) + _year_rows(2022, [100] * 12)

    assert build_profit_history(rows).simulated_year == 2021


def test_ties_pick_most_recent_year():
    rows = _year_rows(2022, [100] * 12) + _year_rows(2023, [100] * 12)

    assert build_profit_history(rows).simulated_year == 2023


def test_detects_date_column_and_net_income_with_currency_formatting():
    rows = [{"Date": f"2023-{month + 1:02d}-01", "Net_Income": "$1,000"} for month in range(12)]

    history = build_profit_history(rows)

    assert history.simulated_year == 2023
    assert history.points[0] == ProfitPoint(period="Jan", expected=1000, actual=1000)


def test_month_with_no_other_years_uses_actual_as_expected():
    rows = _year_rows(2025, [float(month) for month in range(12)]) + [{"month": "2026-01", "operating_income": "50"}]

    history = build_profit_history(rows)

    assert history.points[0] == ProfitPoint(period="Jan", expected=50, actual=0)
    assert history.points[1] == ProfitPoint(period="Feb", expected=1, actual=1)


def test_skips_rows_with_blank_profit():
    rows = _year_rows(2024, [10] * 12) + [{"month": "2025-01", "operating_income": ""}]

    assert build_profit_history(rows).simulated_year == 2024


def test_raises_on_empty_rows():
    with pytest.raises(FinancialHistoryError, match="empty"):
        build_profit_history([])


def test_raises_without_month_column():
    with pytest.raises(FinancialHistoryError, match="month"):
        build_profit_history([{"when": "2024-01", "operating_income": "1"}])


def test_raises_without_profit_column():
    with pytest.raises(FinancialHistoryError, match="profit"):
        build_profit_history([{"month": "2024-01", "revenue": "1"}])


def test_raises_without_complete_year():
    rows = _year_rows(2024, [10] * 12)[:8]

    with pytest.raises(FinancialHistoryError, match="12 months"):
        build_profit_history(rows)


def test_monthly_notes_returns_nonempty_notes_for_year():
    notes = monthly_notes(_demo_rows("two-scoops-creamery"), 2024)

    assert set(notes) == {0, 4, 5, 9, 11}
    assert notes[4].startswith("Rainiest May")


def test_monthly_notes_without_notes_column_is_empty():
    assert monthly_notes(_year_rows(2024, [10] * 12), 2024) == {}
