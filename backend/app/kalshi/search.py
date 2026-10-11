"""Narrowing Kalshi's catalogue down to the handful of series a model can reason over.

Retrieval is deliberately recall-oriented. 14,942 series cannot go in a prompt,
and ~3,100 survive the business-category filter, so this stage's job is to get
the plausible candidates in front of the model - the model supplies precision,
and every ticker it returns is validated against the candidates it was shown.

Two findings from the live catalogue shape the design:

- **Score titles, never tickers.** Ticker substrings produce absurd matches:
  `KXGPUSDW` reads as a GPU market but is "Will GBPUSD end the week above
  1.3625?", `KXNFLOPOY` contains "flop" but is NFL Offensive Player of the Year,
  and `KXCHIPBURRITO` contains "chip" but is Chipotle.
- **Lexical matching alone is not enough.** Kalshi names products, not factors:
  the series an AI startup needs is titled "B200 Monthly", which shares no word
  with "GPU costs". A curated expansion table bridges that gap. It is a
  hackathon-scale stand-in for embeddings, which is the obvious upgrade.

Term weighting is inverse document frequency over the catalogue, which is what
keeps ubiquitous words like "price" from dominating a score without maintaining
a domain stopword list by hand.

Pure functions only: no network, no model calls.
"""

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from app.kalshi.models import Series

DEFAULT_LIMIT = 25

# Expansion matches are inferred rather than stated, so they count for less.
EXPANSION_WEIGHT = 0.7

# Words that describe any business quantity rather than a particular risk factor.
# IDF cannot suppress these: "cost" is lexically rare across 14,942 titles, so it
# scores highly while matching nothing topical - live, "GPU costs" ranked employer
# health insurance cost and Social Security COLA above every GPU price series.
GENERIC_WEIGHT = 0.3
GENERIC_TERMS = frozenset(
    """amount bill cost decrease expense growth increase index price pricing spend
    spending value""".split()
)

_TOKEN = re.compile(r"[a-z0-9]+")

STOPWORDS = frozenset(
    """a an and are as at be been by do does for from going has have i if in is it its
    my of on or our that the then this to up was we what when which will with would your"""
    .split()
)

# Factor wording -> the vocabulary Kalshi actually titles its products with.
EXPANSIONS: Mapping[str, tuple[str, ...]] = {
    "chip": ("semiconductor",),
    "cold": ("temperature", "low"),
    "compute": ("b200", "gpu"),
    "electricity": ("electric", "power"),
    "fuel": ("gasoline", "gas", "diesel"),
    "gas": ("gasoline",),
    "gasoline": ("gas",),
    "gpu": ("b200", "compute", "h100"),
    "heat": ("temperature", "high"),
    "hot": ("temperature", "high"),
    "inflation": ("cpi", "ppi"),
    "interest": ("rate", "fed"),
    "rain": ("precipitation", "rainfall"),
    "semiconductor": ("chip",),
    "shipping": ("freight",),
    "snow": ("snowfall",),
    "temperature": ("temp",),
    "weather": ("temperature", "rain", "precipitation"),
}


@dataclass(frozen=True)
class TermWeights:
    """Inverse document frequency over a catalogue of titles."""

    document_count: int
    document_frequency: Mapping[str, int] = field(default_factory=dict)

    @classmethod
    def from_texts(cls, texts: Iterable[str]) -> "TermWeights":
        frequency: Counter[str] = Counter()
        count = 0
        for text in texts:
            count += 1
            frequency.update(set(normalize(text)))
        return cls(document_count=count, document_frequency=dict(frequency))

    def weight(self, term: str) -> float:
        """Normalised IDF in (0, 1].

        Dividing by `log(1 + N)` keeps the scale comparable between a small test
        catalogue and the live 14,942 series, so thresholds mean the same thing
        in both. A term unique to one title approaches 1; one in most titles
        approaches 0.
        """
        if self.document_count == 0:
            return 0.0
        frequency = self.document_frequency.get(term, 0)
        return math.log(1 + self.document_count / (1 + frequency)) / math.log(
            1 + self.document_count
        )


@dataclass(frozen=True)
class Candidate:
    series: Series
    score: float
    matched_terms: tuple[str, ...]


@dataclass(frozen=True)
class _Query:
    """A factor expanded into searchable terms, each tracked back to what was stated."""

    stated: frozenset[str]
    weights: Mapping[str, float]
    origins: Mapping[str, frozenset[str]]


def normalize(text: str) -> tuple[str, ...]:
    """Lowercase, split on punctuation, drop filler, and strip plurals, order preserved.

    Plural stripping is what lets a stated "GPU prices" meet a titled "price".
    It is crude, but applied identically to factors and titles, so it cannot
    introduce an asymmetric mismatch.
    """
    seen: dict[str, None] = {}
    for token in _TOKEN.findall(text.lower()):
        if token in STOPWORDS:
            continue
        seen.setdefault(_singular(token), None)
    return tuple(seen)


def rank_series(factor: str, catalogue: Sequence[Series], limit: int = DEFAULT_LIMIT, min_score: float = 0.0, weights: TermWeights | None = None, expansions: Mapping[str, Sequence[str]] = EXPANSIONS) -> list[Candidate]:
    """The series most plausibly related to a stated risk factor, best first.

    Ranking deliberately does *not* filter on whether a horizon can be derived.
    That is a property of each market's ticker, not of the series frequency, and
    `app.kalshi.candidates` already drops markets whose window cannot be worked
    out. Filtering here instead cost real coverage: `KXRAINAUSM` is titled "RAIN
    AUSTIN" and is the best match there is for an Austin rain risk, but its
    frequency is `custom`, so a frequency check hid it - even though its
    month-only tickers give a perfectly good October window.

    `expansions` bridges factor wording to Kalshi's product names. The curated
    default covers the demo scenarios; `app.model.vocabulary` proposes one per
    factor so a business nobody anticipated is not limited to that table.
    """
    query = _query_terms(factor, expansions)
    if not query:
        return []

    # Document frequency comes from the whole catalogue, including series that are
    # then filtered out - how common a word is does not depend on what we keep.
    weights = weights or TermWeights.from_texts(series.title for series in catalogue)

    candidates = []
    for series in catalogue:
        if not series.is_business_relevant or series.is_test_series:
            continue
        score, matched = _score_title(query, series.title, weights)
        if not matched or score <= min_score:
            continue
        candidates.append(Candidate(series=series, score=score, matched_terms=matched))

    candidates.sort(key=lambda candidate: (-candidate.score, candidate.series.ticker))
    return candidates[:limit]


def _query_terms(factor: str, expansions: Mapping[str, Sequence[str]] = EXPANSIONS) -> _Query:
    """Stated terms at full weight, generic ones discounted, expansions discounted further."""
    stated = normalize(factor)
    weights: dict[str, float] = {}
    origins: dict[str, set[str]] = {}

    for term in stated:
        weights[term] = GENERIC_WEIGHT if term in GENERIC_TERMS else 1.0
        origins.setdefault(term, set()).add(term)

    for term in stated:
        for synonym in expansions.get(term, ()):
            expanded = _singular(synonym)
            weights.setdefault(expanded, EXPANSION_WEIGHT)
            origins.setdefault(expanded, set()).add(term)

    return _Query(
        stated=frozenset(stated),
        weights=weights,
        origins={term: frozenset(sources) for term, sources in origins.items()},
    )


def _score_title(query: _Query, title: str, weights: TermWeights) -> tuple[float, tuple[str, ...]]:
    """Weighted term overlap, scaled by how much of the stated factor it accounts for.

    The coverage factor is what stops one rare word from carrying a result: live,
    "cold weather" put a Dunkin' Cold Brew series above every temperature market on
    the strength of "cold" alone, while the temperature series answered both words.
    """
    tokens = set(normalize(title))
    matched = tuple(sorted(term for term in query.weights if term in tokens))
    if not matched:
        return 0.0, ()

    overlap = sum(query.weights[term] * weights.weight(term) for term in matched)
    covered = frozenset().union(*(query.origins[term] for term in matched))
    return overlap * len(covered) / len(query.stated), matched


def _singular(token: str) -> str:
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token
