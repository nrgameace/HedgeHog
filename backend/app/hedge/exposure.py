"""Turning an uploaded CSV and a free-text budget into the numbers sizing needs.

`app/csv_parsing.py` returns untyped string rows, deliberately accepting any
shape, and `size_position` needs Decimals. This is the converter between them.

Two things make it more than a cast:

- **Column names are not fixed.** The demo CSVs call it `total_revenue`, but a
  real upload might say `revenue`, `net_sales` or `monthly_total_revenue_usd`,
  so columns are matched rather than indexed. Getting this wrong matters more
  than it looks: the shortfall scales linearly with the number found, so
  picking a cumulative column instead of a monthly one inflates the whole hedge.
- **Money arrives as humans write it**: `$1,234.50`, `(500)` for a negative,
  blanks and `n/a`. Unparseable values are skipped rather than guessed at.

Amounts come out as a **daily rate**, because that is what `Exposure` takes -
contract windows run from one day to a year, and only a daily rate can be
scaled to each of them.

Pure functions only: no network, no model calls.
"""

import re
from collections.abc import Sequence
from decimal import Decimal, InvalidOperation

# The calendar average, so a daily rate scaled over a year adds back to twelve
# months of the monthly figure rather than drifting about five days short.
DAYS_PER_MONTH = Decimal("365") / 12

DEFAULT_TRAILING_MONTHS = 12

_AMOUNT = re.compile(r"-?\(?\s*\$?\s*\d[\d,]*(?:\.\d+)?\s*\)?")
_PERIOD_MULTIPLIER = (
    (re.compile(r"\b(?:a|per|each|every)?\s*ye?a?r\b|\bannual(?:ly)?\b|\b/\s*yr?\b"), Decimal(1) / 12),
    (re.compile(r"\b(?:a|per|each|every)?\s*week\b|\bweekly\b|\b/\s*wk?\b"), Decimal(52) / 12),
    (re.compile(r"\b(?:a|per|each|every)?\s*day\b|\bdaily\b"), DAYS_PER_MONTH),
)


def parse_money(text: str) -> Decimal | None:
    """A single money value, or None if there is no number in it.

    Handles currency symbols, thousands separators and accountancy parentheses
    for negatives. Anything else - blanks, `n/a`, prose - returns None so the
    caller can skip the row instead of treating it as zero.
    """
    if not isinstance(text, str):
        return None

    match = _AMOUNT.search(text)
    if match is None:
        return None

    raw = match.group(0)
    digits = re.sub(r"[^\d.]", "", raw)
    if not digits or digits == ".":
        return None

    try:
        value = Decimal(digits)
    except InvalidOperation:
        return None

    negative = raw.lstrip().startswith("-") or ("(" in raw and ")" in raw)
    return -value if negative else value


def parse_risk_budget(text: str) -> Decimal | None:
    """The questionnaire's free-text budget as a monthly amount, or None if unstated.

    Reads the first amount mentioned and rescales it by any period named, matching
    the frontend's convention so both ends read the same answer the same way.
    A range like "$500 to $800 a month" takes the lower figure.
    """
    amount = parse_money(text or "")
    if amount is None or amount <= 0:
        return None

    lowered = (text or "").lower()
    for pattern, multiplier in _PERIOD_MULTIPLIER:
        if pattern.search(lowered):
            return amount * multiplier
    return amount


def find_column(rows: Sequence[dict[str, str]], *names: str) -> str | None:
    """The column best matching any of `names`, preferring exact then partial matches.

    Names are tried in order, so the caller states its preference: `find_column(
    rows, "total_revenue", "revenue")` takes a total over a bare revenue column.
    """
    if not rows:
        return None

    headers = list(rows[0].keys())
    normalised = {header: _normalise(header) for header in headers}

    for name in names:
        wanted = _normalise(name)
        for header in headers:
            if normalised[header] == wanted:
                return header
    for name in names:
        wanted = _normalise(name)
        for header in headers:
            if wanted in normalised[header]:
                return header
    return None


def recent_monthly_mean(rows: Sequence[dict[str, str]], column: str, months: int = DEFAULT_TRAILING_MONTHS) -> Decimal | None:
    """Mean of the last `months` parseable values in `column`, or None if there are none.

    Rows are assumed to be in chronological order, as both demo CSVs and any
    normal export are. Recent months are used rather than the whole history so a
    business's current scale drives the hedge, not its first year.
    """
    values = [parse_money(row.get(column, "")) for row in rows]
    parsed = [value for value in values if value is not None]
    if not parsed:
        return None

    window = parsed[-months:] if months > 0 else parsed
    return sum(window, start=Decimal("0")) / len(window)


def daily_rate(monthly_amount: Decimal | None) -> Decimal | None:
    """A monthly figure spread across an average calendar month."""
    if monthly_amount is None:
        return None
    return monthly_amount / DAYS_PER_MONTH


def _normalise(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())
