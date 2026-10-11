"""Keeping the backtest to months where something actually went wrong.

`hitMonths` decides every payout in the simulated year, and so every number the
results table shows - including variance mitigation. It currently comes straight
from the model, which means the model is choosing its own marks: asked which
months the risk materialised, it can simply name the ones that make the hedge
look good.

The honest fix would be historical data for the factor itself - did Austin
really get four inches of rain in May 2024 - and that does not exist here,
because the markets being recommended did not trade then. So instead a claimed
hit has to be corroborated by something in the business's own file: profit below
its seasonal normal that month, or the owner's note for it.

The bias is deliberately conservative. Dropping a month the factor really did
hit understates the hedge; keeping an uncorroborated one overstates it, and
overstating is the failure that matters when the number is being shown to
someone deciding whether to trust this.
"""

from app.financial_history import ProfitHistory


def corroborated_months(history: ProfitHistory, notes: dict[int, str]) -> set[int]:
    """Months with evidence of harm: profit under its seasonal normal, or a note."""
    shortfalls = {
        month
        for month, point in enumerate(history.points)
        if point.actual < point.expected
    }
    return shortfalls | {month for month, note in notes.items() if note.strip()}


def credible_hit_months(hit_months: list[int], history: ProfitHistory, notes: dict[int, str]) -> list[int]:
    """The claimed hit months that the business's own records back up.

    A year with no shortfall and no notes corroborates nothing, so everything is
    dropped rather than waved through - a hedge cannot be credited for rescuing
    a year that needed no rescuing.
    """
    corroborated = corroborated_months(history, notes)
    return [month for month in hit_months if month in corroborated]
