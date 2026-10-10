import re

_AMOUNT_PATTERN = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k)?", re.IGNORECASE)
_PERIODS_PER_MONTH = (("year", 12), ("annual", 12), ("yr", 12), ("quarter", 3))


def parse_monthly_budget(text: str) -> float | None:
    match = _AMOUNT_PATTERN.search(text)
    if match is None:
        return None
    amount = float(match.group(1).replace(",", "")) * (1000 if match.group(2) else 1)
    lowered = text.lower()
    months = next((months for word, months in _PERIODS_PER_MONTH if word in lowered), 1)
    return amount / months
