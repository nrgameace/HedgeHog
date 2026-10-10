import pytest

from app.kalshi.models import Series
from app.kalshi.search import TermWeights, normalize, rank_series

# Titles and categories lifted from the live GET /series response, 2026-10-10,
# including the three ticker-substring traps that motivated title-based scoring.
CATALOGUE = tuple(
    Series.from_api(payload)
    for payload in [
        {
            "ticker": "KXHIGHNY",
            "title": "Highest temperature in NYC",
            "frequency": "daily",
            "categories": ["Climate and Weather"],
        },
        {
            "ticker": "KXLOWTSFO",
            "title": "Lowest Temperature San Francisco",
            "frequency": "daily",
            "categories": ["Climate and Weather"],
        },
        {
            "ticker": "RAINSEA",
            "title": "Seattle rain",
            "frequency": "daily",
            "categories": ["Climate and Weather"],
        },
        {
            "ticker": "KXB200MS",
            "title": "B200 Monthly",
            "frequency": "monthly",
            "categories": ["Science and Technology"],
        },
        {
            "ticker": "KXB200MAX",
            "title": "B100 Yearly Directional Price",
            "frequency": "annual",
            "categories": ["Science and Technology"],
        },
        {
            "ticker": "KXPPISEMI",
            "title": "Semiconductor PPI",
            "frequency": "monthly",
            "categories": ["Economics"],
        },
        {
            "ticker": "AAAGASM",
            "title": "National average gas price",
            "frequency": "monthly",
            "categories": ["Commodities"],
        },
        # Trap: ticker contains "GPUSD", but the market is GBP/USD forex.
        {
            "ticker": "KXGPUSDW",
            "title": "Will GBPUSD end the week above 1.3625?",
            "frequency": "weekly",
            "categories": ["Financials"],
        },
        # Trap: ticker contains "FLOP", but it is American football.
        {
            "ticker": "KXNFLOPOY",
            "title": "NFL Offensive Player of the Year",
            "frequency": "annual",
            "categories": ["Sports"],
        },
        # Trap: ticker contains "CHIP", but it is Chipotle.
        {
            "ticker": "KXCHIPBURRITO",
            "title": "Chipotle burrito price",
            "frequency": "monthly",
            "categories": ["Companies"],
        },
        {
            "ticker": "KXTESTB200",
            "title": "Weekly B200 Compute Price",
            "frequency": "weekly",
            "categories": ["Science and Technology"],
        },
        {
            "ticker": "KXNHLGOAL",
            "title": "NHL goals",
            "frequency": "daily",
            "categories": ["Sports"],
        },
        {
            "ticker": "KXGPURULE",
            "title": "GPU export restrictions",
            "frequency": "custom",
            "categories": ["Science and Technology"],
        },
        # Live false positive: "cost" is rare across titles, so it outranked GPU series.
        {
            "ticker": "KXHEALTHCOST",
            "title": "US employer health insurance cost growth",
            "frequency": "quarterly",
            "categories": ["Economics"],
        },
        # Live false positive: "cold" alone beat every temperature market.
        {
            "ticker": "KXDDCOLDBREW",
            "title": "Price of a Dunkin' Medium Cold Brew this month",
            "frequency": "monthly",
            "categories": ["Companies"],
        },
    ]
)


def tickers(factor: str, **kwargs) -> list[str]:
    return [candidate.series.ticker for candidate in rank_series(factor, CATALOGUE, **kwargs)]


class TestNormalize:
    def test_lowercases_and_splits_on_punctuation(self):
        assert normalize("Highest temperature in NYC!") == ("highest", "temperature", "nyc")

    def test_strips_plurals_so_a_stated_factor_matches_a_title(self):
        assert normalize("GPU prices") == ("gpu", "price")
        assert normalize("rising costs") == ("rising", "cost")

    def test_keeps_short_words_that_plural_stripping_would_mangle(self):
        assert normalize("gas") == ("gas",)

    def test_drops_filler_words(self):
        assert normalize("the price of my gas is in") == ("price", "gas")

    def test_keeps_numbers_inside_product_names(self):
        assert normalize("B200 Monthly") == ("b200", "monthly")


class TestTermWeights:
    WEIGHTS = TermWeights.from_texts(series.title for series in CATALOGUE)

    def test_a_distinctive_term_outweighs_a_ubiquitous_one(self):
        """IDF is what stops 'price' from dominating a score; no stopword list needed."""
        assert self.WEIGHTS.weight("semiconductor") > self.WEIGHTS.weight("price")

    def test_an_unseen_term_cannot_be_matched_but_carries_full_weight(self):
        assert self.WEIGHTS.weight("zebra") >= self.WEIGHTS.weight("semiconductor")

    def test_weights_stay_within_a_comparable_range(self):
        assert 0 < self.WEIGHTS.weight("price") <= 1
        assert 0 < self.WEIGHTS.weight("semiconductor") <= 1

    def test_an_empty_corpus_weighs_nothing(self):
        assert TermWeights.from_texts([]).weight("anything") == 0.0


class TestRanking:
    def test_ranks_the_matching_series_first(self):
        assert tickers("gas prices")[0] == "AAAGASM"
        assert tickers("rain")[0] == "RAINSEA"
        assert tickers("semiconductor PPI")[0] == "KXPPISEMI"

    def test_sorts_by_descending_score(self):
        scores = [c.score for c in rank_series("temperature", CATALOGUE)]

        assert scores == sorted(scores, reverse=True)

    def test_ties_break_on_ticker_so_results_are_deterministic(self):
        assert tickers("temperature") == sorted(tickers("temperature"))

    def test_reports_which_terms_matched(self):
        candidate = rank_series("gas prices", CATALOGUE)[0]

        assert candidate.matched_terms == ("gas", "price")

    def test_respects_the_limit(self):
        assert len(tickers("price", limit=2)) == 2

    def test_an_empty_factor_matches_nothing(self):
        assert tickers("") == []

    def test_a_factor_with_no_overlap_matches_nothing(self):
        assert tickers("zebra giraffe") == []

    def test_min_score_filters_weak_matches(self):
        """A ubiquitous term alone is a weak signal, and the threshold can drop it."""
        assert tickers("price") != []
        assert tickers("price", min_score=0.9) == []


class TestTickerTraps:
    """Scoring runs on titles because ticker substrings produce absurd matches."""

    def test_gpu_does_not_match_a_forex_series(self):
        assert "KXGPUSDW" not in tickers("GPU prices")

    def test_flop_does_not_match_american_football(self):
        assert "KXNFLOPOY" not in tickers("flop compute")

    def test_chip_does_not_match_chipotle(self):
        """'chip' must not match the token 'chipotle'; a shared 'price' is a fair match."""
        assert "KXCHIPBURRITO" not in tickers("chip")
        assert tickers("chip prices")[0] == "KXPPISEMI"


class TestFiltering:
    def test_test_series_are_never_offered(self):
        assert "KXTESTB200" not in tickers("B200 compute price")

    def test_non_business_categories_are_never_offered(self):
        assert "KXNHLGOAL" not in tickers("NHL goals")

    def test_series_without_a_derivable_horizon_are_excluded_by_default(self):
        """A custom-frequency series cannot be period-matched, so it cannot be sized."""
        assert "KXGPURULE" not in tickers("GPU export restrictions")

    def test_unsizeable_series_can_be_included_deliberately(self):
        assert "KXGPURULE" in tickers("GPU export restrictions", require_known_horizon=False)


class TestDomainExpansion:
    """Lexical matching alone cannot connect a stated factor to Kalshi's product names."""

    def test_gpu_reaches_the_b200_series_whose_title_never_says_gpu(self):
        assert "KXB200MS" in tickers("GPU costs")

    def test_a_directly_matching_title_still_outranks_an_expanded_one(self):
        ranked = tickers("semiconductor chip prices")

        assert ranked[0] == "KXPPISEMI"

    def test_cold_weather_reaches_temperature_series(self):
        assert set(tickers("cold weather")) >= {"KXHIGHNY", "KXLOWTSFO"}

    def test_a_generic_subject_word_reaches_its_concrete_series(self):
        """'weather' appears in no title, but expands to the words that do."""
        assert set(tickers("weather")) >= {"RAINSEA", "KXHIGHNY"}

    def test_a_weakly_matched_series_cannot_outrank_a_strongly_matched_one(self):
        """Guards the inversion a category boost caused: 'price' alone must not win."""
        ranked = tickers("chip prices")

        assert ranked.index("KXPPISEMI") < ranked.index("KXB200MAX")


class TestGenericBusinessWords:
    """Both cases below are live false positives from the 14,942-series catalogue."""

    def test_a_generic_cost_word_does_not_outrank_the_factors_own_subject(self):
        ranked = tickers("GPU costs")

        assert ranked.index("KXB200MS") < ranked.index("KXHEALTHCOST")

    def test_covering_more_of_the_factor_beats_one_rare_word(self):
        """'cold' alone matched a Cold Brew; the temperature series answer both words."""
        ranked = tickers("cold weather")

        assert ranked.index("KXHIGHNY") < ranked.index("KXDDCOLDBREW")
        assert ranked.index("KXLOWTSFO") < ranked.index("KXDDCOLDBREW")
