import pytest

from app.hedge_side import derive_side, normalise_direction, resolved_side


class TestDeriveSide:
    """The same risk flips sides with how Kalshi phrased the market."""

    @pytest.mark.parametrize(
        ("direction", "strike_type", "expected"),
        [
            ("up", "greater", "YES"),
            ("up", "less", "NO"),
            ("down", "less", "YES"),
            ("down", "greater", "NO"),
        ],
    )
    def test_side_follows_the_direction_and_the_strike_shape(self, direction, strike_type, expected):
        assert derive_side(direction, strike_type) == expected

    def test_an_ice_cream_shop_hurt_by_cold_buys_the_cold_end_either_way(self):
        assert derive_side("down", "less") == "YES"
        assert derive_side("down", "greater") == "NO"

    def test_both_tails_always_buys_yes_because_the_strike_picks_the_tail(self):
        assert derive_side("both", "greater") == "YES"
        assert derive_side("both", "less") == "YES"

    @pytest.mark.parametrize("strike_type", ["", "between", "custom", None])
    def test_an_unusable_strike_shape_cannot_be_derived(self, strike_type):
        assert derive_side("up", strike_type) is None

    def test_an_unknown_direction_cannot_be_derived(self):
        assert derive_side("sideways", "greater") is None

    @pytest.mark.parametrize("variant", ["greater_or_equal", "less_or_equal"])
    def test_handles_the_inclusive_strike_shapes(self, variant):
        assert derive_side("up", variant) in ("YES", "NO")


class TestNormaliseDirection:
    @pytest.mark.parametrize("raw", ["up", "UP", "  Down ", "both"])
    def test_accepts_the_three_directions_in_any_casing(self, raw):
        assert normalise_direction(raw) in ("up", "down", "both")

    @pytest.mark.parametrize("raw", ["sideways", "", None, 3, ["up"]])
    def test_rejects_anything_else(self, raw):
        assert normalise_direction(raw) is None


class TestResolvedSide:
    def test_the_derived_side_overrides_a_contradicting_stated_one(self):
        """strike_type is mechanical, so it wins over the model's own guess."""
        assert resolved_side("down", "less", "NO") == "YES"

    def test_keeps_the_stated_side_when_the_strike_shape_says_nothing(self):
        assert resolved_side("up", "", "NO") == "NO"

    def test_keeps_the_stated_side_when_no_direction_was_given(self):
        """Older replies carry no direction field, so nothing is silently changed."""
        assert resolved_side(None, "greater", "NO") == "NO"

    def test_keeps_the_stated_side_when_the_direction_is_nonsense(self):
        assert resolved_side("sideways", "greater", "NO") == "NO"

    def test_agrees_with_the_model_when_the_model_was_right(self):
        assert resolved_side("up", "greater", "YES") == "YES"
