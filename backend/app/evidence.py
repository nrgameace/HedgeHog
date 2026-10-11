import re

from app.financial_history import MONTH_COLUMNS, PROFIT_COLUMNS, find_column, parse_amount, parse_month

NOTES_COLUMNS = ("notes",)
PRICE_LIKE_PATTERN = re.compile(r"per_|rate|price|pct|percent|yield", re.IGNORECASE)
EMPTY_SECTION = "(none)"


def _columns(rows: list[dict[str, str]]) -> tuple[str | None, str | None, str | None]:
    fieldnames = list(rows[0].keys()) if rows else []
    return find_column(fieldnames, MONTH_COLUMNS), find_column(fieldnames, PROFIT_COLUMNS), find_column(fieldnames, NOTES_COLUMNS)


def _monthly_profits(rows: list[dict[str, str]]) -> list[tuple[int, int, float, str]]:
    month_column, profit_column, notes_column = _columns(rows)
    if month_column is None or profit_column is None:
        return []
    records = []
    for row in rows:
        month, profit = parse_month(row[month_column]), parse_amount(row[profit_column])
        if month is not None and profit is not None:
            records.append((month[0], month[1], profit, (row.get(notes_column) or "").strip() if notes_column else ""))
    return records


def _shortfall_line(year: int, month: int, actual: float, normal: float, note: str) -> str:
    change = f" ({(actual - normal) / abs(normal) * 100:+.0f}%)" if normal else ""
    line = f"{year}-{month + 1:02d}: profit {actual:,.0f} vs normal {normal:,.0f}{change}"
    return f"{line} — {note}" if note else line


def worst_months(rows: list[dict[str, str]], limit: int = 6) -> list[str]:
    records = _monthly_profits(rows)
    ranked = []
    for year, month, actual, note in records:
        others = [profit for other_year, other_month, profit, _ in records if other_month == month and other_year != year]
        normal = sum(others) / len(others) if others else None
        if normal is not None and normal > actual:
            ranked.append((normal - actual, _shortfall_line(year, month, actual, normal, note)))
    return [line for _, line in sorted(ranked, key=lambda item: item[0], reverse=True)[:limit]]


def notes_timeline(rows: list[dict[str, str]]) -> list[str]:
    month_column, _, notes_column = _columns(rows)
    if month_column is None or notes_column is None:
        return []
    dated = [(parse_month(row[month_column]), row[notes_column].strip()) for row in rows if row[notes_column].strip()]
    return [f"{year}-{month + 1:02d}: {note}" for (year, month), note in sorted(item for item in dated if item[0] is not None)]


def _describe_point(point: tuple[float, str], decimals: int) -> str:
    return f"{point[0]:,.{decimals}f} ({point[1]})"


def _swing(column: str, rows: list[dict[str, str]], month_column: str) -> tuple[float, str] | None:
    values = [(parse_amount(row[column]), row[month_column]) for row in rows]
    values = [(value, month) for value, month in values if value is not None]
    if len(values) < 2 or sum(1 for value, _ in values if value == 0) > len(values) / 2:
        return None
    decimals = 2 if any("." in row[column] for row in rows) else 0
    low, high, latest = min(values), max(values), values[-1]
    mean = sum(value for value, _ in values) / len(values)
    summary = f"{column}: low {_describe_point(low, decimals)}, high {_describe_point(high, decimals)}, latest {_describe_point(latest, decimals)}"
    return (high[0] - low[0]) / max(abs(mean), 1), summary


def column_swings(rows: list[dict[str, str]], limit: int = 12) -> list[str]:
    month_column, _, notes_column = _columns(rows)
    if month_column is None:
        return []
    candidates = [column for column in rows[0] if column not in (month_column, notes_column)]
    swings = [swing for swing in (_swing(column, rows, month_column) for column in candidates) if swing is not None]
    ranked = sorted(swings, key=lambda item: (not PRICE_LIKE_PATTERN.search(item[1].split(":")[0]), -item[0]))
    return [line for _, line in ranked[:limit]]


def _section(title: str, lines: list[str]) -> str:
    body = "\n".join(f"- {line}" for line in lines) if lines else EMPTY_SECTION
    return f"{title}\n{body}"


def build_evidence_digest(rows: list[dict[str, str]]) -> str:
    return "\n\n".join([
        _section("Worst months vs. a normal year:", worst_months(rows)),
        _section("Owner's notes:", notes_timeline(rows)),
        _section("Biggest swings by column:", column_swings(rows)),
    ])
