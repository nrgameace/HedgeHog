"""Dropping proposed risk factors the business's own history does not support.

The model proposes up to ten factors and only has to clear a confidence of 20,
so a lot of barely-relevant ones get through. Confidence alone cannot fix that,
because it is the model's own opinion of its own suggestion. The financials can
check it.

**The check is whether the driver actually moved, not whether it correlates with
profit.** Correlating a cost column against profit looks like the obvious test
and is badly misleading here, because `operating_income` is computed *from*
those columns. Measured on the demo data, `office_rent` scored -0.55 against
profit and `headcount` -0.76, topping the table - not because either is a market
risk but because rent and payroll are subtracted from operating income. It is an
accounting identity. Meanwhile `gpu_cost_per_hour` scored *+0.89*, a cost moving
with profit, purely because the company grew. Detrending fixed one confound and
left the other.

Driver movement avoids all of that by never touching profit. A factor is only a
live risk if the thing behind it has been moving: Two Scoops' dairy price is
contracted flat at $4.25 (spread 0.012) and its rent never changes (0.000), and
`background.md` lists both under "should *not* hedge". Electricity (0.717) and
the variable loan rate (0.126) do move, and both are listed under "should
hedge".

The veto is one-directional on purpose. A factor with no matching column cannot
be tested and is kept - rain and temperature have no column in any of these
files, and they are the whole point of the product.
"""

import re
import statistics

from app.financial_history import MONTH_COLUMNS, PROFIT_COLUMNS, find_column, parse_amount, parse_month
from app.trend_detection import HedgeableCategory

# Below this relative spread the driver is treated as flat: it has not moved
# enough over the recent window to be a live exposure.
#
# Calibrated against the demo businesses' own judging checklists, which name
# what should and should not be hedged. On Two Scoops the drivers measure:
# rent 0.000 and contracted dairy 0.012 (both listed "should NOT hedge"),
# against fuel 0.053, the variable loan rate 0.126 and electricity 0.717 (all
# listed "should hedge"). 0.03 separates those two groups and 0.08 does not -
# it also vetoed fuel, which the checklist calls "a small dollar amount, but a
# real exposure".
MIN_DRIVER_SPREAD = 0.03
RECENT_MONTHS = 24
MIN_POINTS_FOR_SPREAD = 6

# Factor wording -> the words a CSV column is likely to use for the same thing.
DRIVER_SYNONYMS = {
    "gas": ("fuel", "gasoline", "diesel"),
    "gasoline": ("fuel", "gas"),
    "fuel": ("gas", "gasoline", "diesel"),
    # Deliberately no unit words here (kwh, gallons, hours): a unit names the
    # volume consumed, which moves with how much the business sold, and it would
    # outrank the price column on token overlap.
    "power": ("electricity", "electric"),
    "electricity": ("electric", "power"),
    "interest": ("rate", "loan"),
    "rate": ("interest", "yield"),
    "milk": ("dairy",),
    "dairy": ("milk",),
    "compute": ("gpu", "token"),
    "gpu": ("compute", "token"),
    "wage": ("payroll", "labor", "labour"),
    "shipping": ("freight", "delivery"),
    "insurance": ("insurance",),
    "rent": ("rent", "lease"),
}

_TOKEN = re.compile(r"[a-z0-9]+")
# A factor's driver is its *price*, not the volume the business bought. Both
# columns match on the same word, so "dairy prices" has to land on
# dairy_cost_per_gallon rather than dairy_gallons_purchased - whose swings track
# how much ice cream got sold, not the market.
_PRICE_LIKE = re.compile(r"price|cost|rate|yield|pct|percent", re.IGNORECASE)
_PER_UNIT = re.compile(r"per_|_per|/", re.IGNORECASE)
# Columns that are outputs of the business rather than external drivers. Matching
# one would test the wrong thing: these move because the business moved.
_OUTPUT_HINTS = ("revenue", "income", "profit", "margin", "sales", "transactions", "customers")


def _tokens(text: str) -> set[str]:
    return {token for token in _TOKEN.findall((text or "").lower()) if len(token) > 2}


def _driver_words(category: HedgeableCategory) -> set[str]:
    stated = _tokens(category.category) | _tokens(category.label)
    return stated | {synonym for word in stated for synonym in DRIVER_SYNONYMS.get(word, ())}


def proxy_column(rows: list[dict[str, str]], category: HedgeableCategory) -> str | None:
    """The CSV column that stands in for this factor's driver, if there is one.

    Output columns are skipped: a factor is not evidenced by the business's own
    revenue moving, only by its driver moving.
    """
    if not rows:
        return None

    wanted = _driver_words(category)
    reserved = {find_column(list(rows[0]), MONTH_COLUMNS), find_column(list(rows[0]), PROFIT_COLUMNS)}
    scored = []
    for column in rows[0]:
        if column in reserved or any(hint in column.lower() for hint in _OUTPUT_HINTS):
            continue
        overlap = len(_tokens(column) & wanted)
        if overlap:
            rank = (overlap, bool(_PRICE_LIKE.search(column)), bool(_PER_UNIT.search(column)))
            scored.append((rank, column))
    return max(scored, key=lambda item: item[0])[1] if scored else None


def relative_spread(rows: list[dict[str, str]], column: str, months: int = RECENT_MONTHS) -> float | None:
    """How far the column ranged over its recent history, relative to its own level.

    Relative rather than absolute so a $4 dairy price and a $4,000 power bill are
    judged on the same scale. None when there is too little to judge.
    """
    month_column = find_column(list(rows[0]), MONTH_COLUMNS) if rows else None
    if month_column is None:
        return None

    dated = []
    for row in rows:
        month, value = parse_month(row.get(month_column, "")), parse_amount(row.get(column, "") or "")
        if month is not None and value is not None:
            dated.append((month, value))

    values = [value for _, value in sorted(dated)][-months:]
    if len(values) < MIN_POINTS_FOR_SPREAD:
        return None

    mean = statistics.fmean(values)
    return (max(values) - min(values)) / abs(mean) if abs(mean) > 1e-9 else None


def driver_is_flat(rows: list[dict[str, str]], category: HedgeableCategory) -> bool:
    """Whether this factor's driver has sat still, making it a stale risk to hedge."""
    column = proxy_column(rows, category)
    if column is None:
        return False

    spread = relative_spread(rows, column)
    return spread is not None and spread < MIN_DRIVER_SPREAD


def drop_stale_factors(rows: list[dict[str, str]], categories: list[HedgeableCategory]) -> tuple[list[HedgeableCategory], list[HedgeableCategory]]:
    """Split the proposed factors into those still live and those whose driver is flat."""
    live, stale = [], []
    for category in categories:
        (stale if driver_is_flat(rows, category) else live).append(category)
    return live, stale
