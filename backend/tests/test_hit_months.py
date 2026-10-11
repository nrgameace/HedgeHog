from app.financial_history import MONTH_LABELS, ProfitHistory, ProfitPoint
from app.hit_months import corroborated_months, credible_hit_months


def history(shortfall_months: tuple[int, ...] = ()) -> ProfitHistory:
    return ProfitHistory(
        simulated_year=2024,
        points=[
            ProfitPoint(period=label, expected=1000, actual=400 if m in shortfall_months else 1000)
            for m, label in enumerate(MONTH_LABELS)
        ],
    )


class TestCorroboratedMonths:
    def test_a_month_below_its_seasonal_normal_counts(self):
        assert corroborated_months(history((4, 5)), {}) == {4, 5}

    def test_a_month_with_an_owners_note_counts(self):
        assert corroborated_months(history(), {7: "Heat wave closed the patio"}) == {7}

    def test_evidence_from_either_source_counts(self):
        assert corroborated_months(history((4,)), {7: "Heat wave"}) == {4, 7}

    def test_a_blank_note_is_not_evidence(self):
        assert corroborated_months(history(), {7: "   "}) == set()

    def test_a_month_above_normal_is_not_evidence(self):
        assert corroborated_months(history(), {}) == set()


class TestCredibleHitMonths:
    def test_keeps_the_months_the_records_back_up(self):
        assert credible_hit_months([4, 5], history((4, 5)), {}) == [4, 5]

    def test_drops_a_claimed_hit_in_a_month_that_went_fine(self):
        """The model choosing its own marks is the thing being guarded against."""
        assert credible_hit_months([4, 5, 9], history((4, 5)), {}) == [4, 5]

    def test_a_note_alone_is_enough_corroboration(self):
        assert credible_hit_months([7], history(), {7: "Heat wave closed the patio"}) == [7]

    def test_a_flat_year_corroborates_nothing(self):
        """A hedge cannot be credited for rescuing a year that needed no rescuing."""
        assert credible_hit_months([4, 5], history(), {}) == []

    def test_no_claimed_hits_stays_empty(self):
        assert credible_hit_months([], history((4, 5)), {}) == []

    def test_order_is_preserved(self):
        assert credible_hit_months([5, 4], history((4, 5)), {}) == [5, 4]

    def test_the_result_is_always_a_subset_of_what_was_claimed(self):
        claimed = [1, 4]

        assert set(credible_hit_months(claimed, history((4, 5, 6)), {})) <= set(claimed)
