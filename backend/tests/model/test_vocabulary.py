import json

import httpx

from app.akamai_client import AkamaiConfig
from app.kalshi.search import EXPANSIONS, rank_series
from app.model.vocabulary import MAX_CONCEPTS, MAX_TERMS_PER_CONCEPT, search_vocabulary
from tests.kalshi.test_search import CATALOGUE

CONFIG = AkamaiConfig(
    base_url="https://inference.example/v1", api_key="test-key", chat_model="qwen-test"
)


def model_returning(content: str, recorder: list[httpx.Request] | None = None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if recorder is not None:
            recorder.append(request)
        return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})

    return httpx.Client(transport=httpx.MockTransport(handler))


def failing_model() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)))


def proposal(**concepts: list[str]) -> str:
    return json.dumps(
        {"concepts": [{"concept": c, "terms": t} for c, t in concepts.items()]}
    )


class TestProposal:
    def test_turns_the_models_reply_into_expansions(self):
        model = model_returning(proposal(gpu=["B200", "H100"]))

        vocabulary = search_vocabulary("GPU costs", config=CONFIG, client=model, fallback={})

        assert set(vocabulary["gpu"]) == {"b200", "h100"}

    def test_normalises_the_terms_the_model_returns(self):
        """Terms are matched as tokens, so casing, plurals and phrases must be reduced."""
        model = model_returning(proposal(gpu=["Compute Prices", "B200"]))

        vocabulary = search_vocabulary("GPU costs", config=CONFIG, client=model, fallback={})

        assert set(vocabulary["gpu"]) == {"compute", "price", "b200"}

    def test_includes_the_factor_in_the_prompt(self):
        seen: list[httpx.Request] = []
        model = model_returning(proposal(tpu=["b200"]), seen)

        search_vocabulary("TPU rental costs", config=CONFIG, client=model, fallback={})

        assert "TPU rental costs" in json.loads(seen[0].content)["messages"][1]["content"]


class TestValidation:
    def test_drops_concepts_the_factor_never_mentioned(self):
        """Guards against the model inventing a concept and widening the search itself."""
        model = model_returning(proposal(gpu=["b200"], bitcoin=["btc"]))

        vocabulary = search_vocabulary("GPU costs", config=CONFIG, client=model, fallback={})

        assert "gpu" in vocabulary
        assert "bitcoin" not in vocabulary

    def test_matches_concepts_against_the_normalised_factor(self):
        model = model_returning(proposal(cost=["cpi"]))

        vocabulary = search_vocabulary("rising costs", config=CONFIG, client=model, fallback={})

        assert "cost" in vocabulary

    def test_caps_the_number_of_concepts(self):
        many = {f"word{index}": ["term"] for index in range(MAX_CONCEPTS + 5)}
        factor = " ".join(many)
        model = model_returning(proposal(**many))

        vocabulary = search_vocabulary(factor, config=CONFIG, client=model, fallback={})

        assert len(vocabulary) == MAX_CONCEPTS

    def test_caps_the_terms_per_concept(self):
        model = model_returning(proposal(gpu=[f"term{index}" for index in range(20)]))

        vocabulary = search_vocabulary("GPU costs", config=CONFIG, client=model, fallback={})

        assert len(vocabulary["gpu"]) == MAX_TERMS_PER_CONCEPT

    def test_ignores_concepts_with_no_usable_terms(self):
        model = model_returning(proposal(gpu=["", "   ", "!!"]))

        vocabulary = search_vocabulary("GPU costs", config=CONFIG, client=model, fallback={})

        assert vocabulary == {}

    def test_ignores_a_reply_of_the_wrong_shape(self):
        model = model_returning('{"concepts": "not a list"}')

        assert search_vocabulary("GPU costs", config=CONFIG, client=model, fallback={}) == {}


class TestFallback:
    def test_falls_back_to_the_curated_table_when_the_model_fails(self):
        vocabulary = search_vocabulary("GPU costs", config=CONFIG, client=failing_model())

        assert "b200" in vocabulary["gpu"]

    def test_falls_back_when_the_model_returns_nothing_usable(self):
        model = model_returning('{"concepts": []}')

        vocabulary = search_vocabulary("GPU costs", config=CONFIG, client=model)

        assert "b200" in vocabulary["gpu"]

    def test_uses_the_curated_table_when_credentials_are_missing(self, monkeypatch):
        """An unconfigured endpoint is a supported state, not a failed request."""
        for name in ("AKAMAI_API_BASE_URL", "AKAMAI_API_KEY", "AKAMAI_CHAT_MODEL"):
            monkeypatch.delenv(name, raising=False)

        assert search_vocabulary("GPU costs") == EXPANSIONS

    def test_merges_the_proposal_over_the_curated_table(self):
        """Curated entries stay as a floor, so a thin proposal cannot lose recall."""
        model = model_returning(proposal(gpu=["mi300"]))

        vocabulary = search_vocabulary("GPU costs and rain", config=CONFIG, client=model)

        assert set(vocabulary["gpu"]) >= {"mi300", "b200"}
        assert "precipitation" in vocabulary["rain"]


class TestRankingWithProposedVocabulary:
    def test_a_proposal_reaches_a_series_the_curated_table_would_miss(self):
        """'TPU' is in no title and no curated entry, so only the model can bridge it."""
        curated = [
            c.series.ticker for c in rank_series("TPU costs", CATALOGUE, expansions=EXPANSIONS)
        ]
        assert "KXB200MS" not in curated
        assert curated == ["KXHEALTHCOST"], "only a generic 'cost' match, which is noise"

        model = model_returning(proposal(tpu=["b200"]))
        vocabulary = search_vocabulary("TPU costs", config=CONFIG, client=model, fallback={})

        proposed = rank_series("TPU costs", CATALOGUE, expansions=vocabulary)

        assert [c.series.ticker for c in proposed][0] == "KXB200MS"
