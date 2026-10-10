import re

_AMOUNT_PATTERN = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k|m)?\b(?!\s*%)", re.IGNORECASE)
_PERIOD_PATTERN = re.compile(r"month|mo\b|year|annual|yr|quarter", re.IGNORECASE)
_SUFFIX_MULTIPLIERS = {"k": 1_000, "m": 1_000_000}
_MONTHS_PER_PERIOD = {"year": 12, "annual": 12, "yr": 12, "quarter": 3}


def _months_in_period(text_after_amount: str) -> int:
    period = _PERIOD_PATTERN.search(text_after_amount)
    return _MONTHS_PER_PERIOD.get(period.group(0).lower(), 1) if period else 1


def parse_monthly_budget(text: str) -> float | None:
    match = _AMOUNT_PATTERN.search(text)
    if match is None:
        return None
    amount = float(match.group(1).replace(",", "")) * _SUFFIX_MULTIPLIERS.get((match.group(2) or "").lower(), 1)
    return amount / _months_in_period(text[match.end():]) if amount > 0 else None
