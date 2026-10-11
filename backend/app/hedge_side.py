"""Working out which side of a market pays when the business is hurt.

The prompt asks the model to "pick the side that pays out when the business is
hurt", and nothing checks it. Getting it backwards is the worst failure this
pipeline has, because it does not look like a failure: the trade still appears
in the table, still costs its premium, and still shows a net - it just pays in
the months business was already good, which makes profit swing wider instead of
narrower.

It is also genuinely easy to get wrong, because the answer flips with how Kalshi
phrased the question rather than with the risk:

    hurt by cold  +  "will the low be BELOW 56?"   -> YES
    hurt by cold  +  "will the high be ABOVE 63?"  -> NO

So the model is asked for something it can actually know - whether the business
is hurt when the underlying factor rises or falls, a fact about the business -
and the side is derived from that plus the market's own `strike_type`. Where the
strike shape does not say (directional markets like "B200 price up next week?"),
the model's stated side is kept.
"""

# Kalshi strike shapes. A "greater" market resolves YES when the factor rises.
STRIKE_RISES_WITH_YES = frozenset({"greater", "greater_or_equal"})
STRIKE_FALLS_WITH_YES = frozenset({"less", "less_or_equal"})

DIRECTIONS = frozenset({"up", "down", "both"})


def normalise_direction(value: object) -> str | None:
    """`"up"`, `"down"` or `"both"`, or None when the model said something else."""
    if not isinstance(value, str):
        return None
    direction = value.strip().lower()
    return direction if direction in DIRECTIONS else None


def derive_side(direction: str, strike_type: str) -> str | None:
    """"YES" or "NO" - whichever pays in the bad state - or None if it cannot be told.

    `both` covers exposures that are not monotonic: an ice cream shop is hurt by
    a cold day *and* by a 100F day, while a warm one is its best. A threshold
    market is itself one tail, so either tail's YES pays in a bad state, and
    covering both ends means holding one of each.
    """
    shape = (strike_type or "").strip().lower()
    if shape in STRIKE_RISES_WITH_YES:
        yes_pays_when_factor_rises = True
    elif shape in STRIKE_FALLS_WITH_YES:
        yes_pays_when_factor_rises = False
    else:
        return None

    if direction == "both":
        return "YES"
    if direction not in ("up", "down"):
        return None
    return "YES" if (direction == "up") == yes_pays_when_factor_rises else "NO"


def resolved_side(direction: object, strike_type: str, stated_side: str) -> str:
    """The derived side where the strike shape allows it, otherwise the stated one."""
    normalised = normalise_direction(direction)
    if normalised is None:
        return stated_side
    return derive_side(normalised, strike_type) or stated_side
