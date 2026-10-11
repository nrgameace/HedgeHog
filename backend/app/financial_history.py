import math
import re
from dataclasses import dataclass

MONTH_LABELS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
MONTH_COLUMNS = ("month", "date", "period")
PROFIT_COLUMNS = ("operating_income", "net_income", "profit", "gross_profit")
RECENT_YEARS_CONSIDERED = 3

_YEAR_FIRST_PATTERN = re.compile(r"^\s*(\d{4})[-/](\d{1,2})(?:[-/]\d{1,2})?\s*$")
_US_DATE_PATTERN = re.compile(r"^\s*(\d{1,2})/\d{1,2}/(\d{4})\s*$")


@dataclass
class ProfitPoint:
    period: str
    expected: int
    actual: int


@dataclass
class ProfitHistory:
    simulated_year: int
    points: list[ProfitPoint]


class FinancialHistoryError(Exception):
    pass


def find_column(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    by_lowercase = {name.strip().lower(): name for name in fieldnames}
    return next((by_lowercase[candidate] for candidate in candidates if candidate in by_lowercase), None)


def parse_month(text: str) -> tuple[int, int] | None:
    if match := _YEAR_FIRST_PATTERN.match(text or ""):
        year, month = int(match.group(1)), int(match.group(2))
    elif match := _US_DATE_PATTERN.match(text or ""):
        year, month = int(match.group(2)), int(match.group(1))
    else:
        return None
    return (year, month - 1) if 1 <= month <= 12 else None


def parse_amount(text: str) -> float | None:
    cleaned = re.sub(r"[$,\s]", "", text or "")
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = f"-{cleaned[1:-1]}"
    try:
        value = float(cleaned)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def required_columns(rows: list[dict[str, str]]) -> tuple[str, str]:
    if not rows:
        raise FinancialHistoryError("The financials CSV is empty.")
    fieldnames = list(rows[0].keys())
    month_column = find_column(fieldnames, MONTH_COLUMNS)
    if month_column is None:
        raise FinancialHistoryError("The financials CSV needs a month column (month, date or period).")
    profit_column = find_column(fieldnames, PROFIT_COLUMNS)
    if profit_column is None:
        raise FinancialHistoryError("The financials CSV needs a profit column (operating_income, net_income, profit or gross_profit).")
    return month_column, profit_column


def _profit_by_year(rows: list[dict[str, str]]) -> dict[int, dict[int, float]]:
    month_column, profit_column = required_columns(rows)
    months = [parse_month(row[month_column]) for row in rows]
    if all(month is None for month in months):
        raise FinancialHistoryError(f"Couldn't read the dates in column '{month_column}'; use YYYY-MM (for example 2024-05).")
    by_year: dict[int, dict[int, float]] = {}
    for month, row in zip(months, rows):
        profit = parse_amount(row[profit_column])
        if month is not None and profit is not None:
            by_year.setdefault(month[0], {})[month[1]] = profit
    return by_year


def _expected_for(year: int, by_year: dict[int, dict[int, float]]) -> list[float]:
    expected = []
    for month in range(12):
        others = [months[month] for other, months in by_year.items() if other != year and month in months]
        expected.append(sum(others) / len(others) if others else by_year[year][month])
    return expected


def _shortfall(expected: list[float], actual: list[float]) -> float:
    return math.sqrt(sum(max(normal - real, 0) ** 2 for normal, real in zip(expected, actual)) / len(actual))


def _worst_recent_year(by_year: dict[int, dict[int, float]]) -> int:
    complete_years = sorted(year for year, months in by_year.items() if len(months) == 12)
    if not complete_years:
        raise FinancialHistoryError("The financials CSV needs at least one calendar year with all 12 months.")
    recent = complete_years[-RECENT_YEARS_CONSIDERED:]
    actuals = {year: [by_year[year][month] for month in range(12)] for year in recent}
    return max(reversed(recent), key=lambda year: _shortfall(_expected_for(year, by_year), actuals[year]))


def build_profit_history(rows: list[dict[str, str]]) -> ProfitHistory:
    by_year = _profit_by_year(rows)
    year = _worst_recent_year(by_year)
    expected = _expected_for(year, by_year)
    points = [ProfitPoint(period=MONTH_LABELS[month], expected=round(expected[month]), actual=round(by_year[year][month])) for month in range(12)]
    return ProfitHistory(simulated_year=year, points=points)


def monthly_notes(rows: list[dict[str, str]], year: int) -> dict[int, str]:
    if not rows:
        return {}
    fieldnames = list(rows[0].keys())
    month_column, notes_column = find_column(fieldnames, MONTH_COLUMNS), find_column(fieldnames, ("notes",))
    if month_column is None or notes_column is None:
        return {}
    notes = {}
    for row in rows:
        month = parse_month(row[month_column])
        if month is not None and month[0] == year and row[notes_column].strip():
            notes[month[1]] = row[notes_column].strip()
    return notes
