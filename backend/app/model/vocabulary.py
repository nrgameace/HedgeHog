"""Asking the model what words Kalshi would use for a business's risk factor.

Kalshi titles its series by product and index name, not by business concern: the
series an AI startup needs is "B200 Monthly", which shares no word with "GPU
costs". Lexical scoring therefore scores it zero, and a hand-written expansion
table only bridges the factors somebody thought of in advance.

So the model proposes the vocabulary instead. It is a good fit for the job -
naming what a market is likely called is exactly the knowledge a language model
has and a keyword index does not - and it keeps the arithmetic elsewhere: this
call returns search words, never a number, a size or a ticker to trade.

Everything it returns is validated. Concepts the factor never mentioned are
dropped so the model cannot widen the search on its own, terms are reduced to
the tokens the index actually matches, and both are capped. On any failure the
curated table is used, so the pipeline degrades instead of breaking.
"""

from collections.abc import Mapping, Sequence

from app.kalshi.search import EXPANSIONS, normalize
from app.model.client import ModelClient, ModelError

MAX_CONCEPTS = 8
MAX_TERMS_PER_CONCEPT = 8

SYSTEM_PROMPT = """You map a small business's stated risk factor onto the words \
Kalshi uses to title its prediction markets.

Kalshi names series after products and published indices, not after business \
concerns. GPU compute appears as "B200 Monthly" or "H100 Weekly Price". \
Gasoline appears as "Truflation US CPI Gasoline Price Index". Temperature \
appears as "Low Temperature Atlanta".

For each distinct concept word in the factor you are given, list the lowercase \
single words most likely to appear in the title of a relevant Kalshi series. \
Prefer product names, index names and ticker-like words over generic business \
words such as "cost", "price" or "growth".

Reply with JSON only, in exactly this shape:
{"concepts": [{"concept": "<word from the factor>", "terms": ["<word>", ...]}]}"""


def search_vocabulary(factor: str, client: ModelClient | None, fallback: Mapping[str, Sequence[str]] = EXPANSIONS) -> Mapping[str, tuple[str, ...]]:
    """Expansions for a factor: the model's proposal merged over the curated table.

    Merging rather than replacing keeps the curated entries as a floor, so a thin
    or partial proposal cannot cost recall the demo scenarios already have. With
    no client configured this is just the curated table.
    """
    if client is None:
        return {term: tuple(terms) for term, terms in fallback.items()}

    try:
        proposed = _propose(factor, client)
    except ModelError:
        proposed = {}

    merged = {term: tuple(terms) for term, terms in fallback.items()}
    for concept, terms in proposed.items():
        merged[concept] = tuple(dict.fromkeys((*merged.get(concept, ()), *terms)))
    return merged


def _propose(factor: str, client: ModelClient) -> Mapping[str, tuple[str, ...]]:
    reply = client.complete_json(SYSTEM_PROMPT, f"Risk factor: {factor}")
    return _validated(reply, stated=frozenset(normalize(factor)))


def _validated(reply: Mapping, stated: frozenset[str]) -> Mapping[str, tuple[str, ...]]:
    """Keep only concepts the factor actually contains, with their terms tokenised."""
    entries = reply.get("concepts")
    if not isinstance(entries, list):
        return {}

    vocabulary: dict[str, tuple[str, ...]] = {}
    for entry in entries:
        if len(vocabulary) >= MAX_CONCEPTS:
            break
        concept, terms = _entry(entry)
        if concept not in stated or not terms:
            continue
        vocabulary[concept] = terms
    return vocabulary


def _entry(entry: object) -> tuple[str | None, tuple[str, ...]]:
    if not isinstance(entry, dict):
        return None, ()

    raw_concept = entry.get("concept")
    raw_terms = entry.get("terms")
    if not isinstance(raw_concept, str) or not isinstance(raw_terms, list):
        return None, ()

    concept = next(iter(normalize(raw_concept)), None)
    tokens = [
        token
        for term in raw_terms
        if isinstance(term, str)
        for token in normalize(term)
    ]
    return concept, tuple(dict.fromkeys(tokens))[:MAX_TERMS_PER_CONCEPT]
