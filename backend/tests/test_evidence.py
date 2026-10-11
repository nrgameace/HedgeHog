from pathlib import Path

from app.csv_parsing import parse_csv_rows
from app.evidence import build_evidence_digest, column_swings, notes_timeline, worst_months

TWO_SCOOPS_ROWS = parse_csv_rows((Path(__file__).resolve().parents[2] / "demo-data/two-scoops-creamery/financials.csv").read_bytes())


def _rows(profits: dict[str, str], notes: dict[str, str] | None = None) -> list[dict[str, str]]:
    notes = notes or {}
    return [{"month": month, "operating_income": profit, "notes": notes.get(month, "")} for month, profit in profits.items()]


def test_worst_months_ranks_biggest_shortfall_first_with_its_note():
    rows = _rows({"2023-05": "100", "2024-05": "40", "2025-05": "100", "2024-06": "90", "2023-06": "100"}, {"2024-05": "Rainy May"})

    assert worst_months(rows) == [
        "2024-05: profit 40 vs normal 100 (-60%) — Rainy May",
        "2024-06: profit 90 vs normal 100 (-10%)",
    ]


def test_worst_months_respects_limit():
    rows = _rows({"2023-01": "100", "2024-01": "10", "2023-02": "100", "2024-02": "50"})

    assert len(worst_months(rows, limit=1)) == 1


def test_worst_months_finds_two_scoops_rain():
    assert any(line.startswith("2024-05") and "Rainiest May" in line for line in worst_months(TWO_SCOOPS_ROWS))


def test_notes_timeline_lists_notes_oldest_first():
    rows = _rows({"2024-02": "1", "2024-01": "1", "2024-03": "1"}, {"2024-02": "Second", "2024-01": "First"})

    assert notes_timeline(rows) == ["2024-01: First", "2024-02: Second"]


def test_notes_timeline_without_notes_column_is_empty():
    assert notes_timeline([{"month": "2024-01", "operating_income": "5"}]) == []


def test_column_swings_reports_low_high_and_latest():
    rows = [{"month": "2024-01", "fuel": "2.00"}, {"month": "2024-02", "fuel": "4.50"}, {"month": "2024-03", "fuel": "3.00"}]

    assert column_swings(rows) == ["fuel: low 2.00 (2024-01), high 4.50 (2024-02), latest 3.00 (2024-03)"]


def test_column_swings_ranks_relative_swing_and_skips_text_columns():
    rows = [{"month": "2024-01", "steady": "100", "spiky": "1", "notes": "x"}, {"month": "2024-02", "steady": "101", "spiky": "9", "notes": "y"}]

    assert [line.split(":")[0] for line in column_swings(rows)] == ["spiky", "steady"]


def test_column_swings_finds_two_scoops_fuel_spike():
    fuel = max(float(row["fuel_cost_per_gallon"]) for row in TWO_SCOOPS_ROWS)

    assert any(line.startswith("fuel_cost_per_gallon:") and f"high {fuel:,.2f} (2022-06)" in line for line in column_swings(TWO_SCOOPS_ROWS, limit=50))


def test_digest_has_three_sections():
    digest = build_evidence_digest(TWO_SCOOPS_ROWS)

    assert "Worst months vs. a normal year:" in digest
    assert "Owner's notes:" in digest
    assert "Biggest swings by column:" in digest
    assert "- 2016-01: Opened on South Congress" in digest


def test_digest_marks_empty_sections():
    digest = build_evidence_digest([{"month": "2024-01", "operating_income": "5"}])

    assert digest.count("(none)") == 3


def test_column_swings_lists_prices_and_rates_first():
    rows = [{"month": "2024-01", "revenue": "10", "fuel_cost_per_gallon": "3.00", "loan_rate": "5.0"}, {"month": "2024-02", "revenue": "90", "fuel_cost_per_gallon": "3.10", "loan_rate": "6.0"}]

    assert [line.split(":")[0] for line in column_swings(rows)] == ["loan_rate", "fuel_cost_per_gallon", "revenue"]


def test_column_swings_skips_mostly_zero_columns():
    rows = [{"month": f"2024-0{month}", "loan_proceeds": "68000" if month == 1 else "0", "rent": "4200"} for month in range(1, 4)]

    assert [line.split(":")[0] for line in column_swings(rows)] == ["rent"]


def test_two_scoops_swings_lead_with_its_prices():
    leaders = {line.split(":")[0] for line in column_swings(TWO_SCOOPS_ROWS)[:3]}

    assert leaders == {"dairy_cost_per_gallon", "fuel_cost_per_gallon", "loan_interest_rate"}
