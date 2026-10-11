from app.financial_history import MONTH_LABELS, ProfitHistory, ProfitPoint
from app.kalshi_client import KalshiMarket
from app.questionnaire import QuestionnaireAnswers
from app.trend_detection import HedgeableCategory

ANSWERS = QuestionnaireAnswers(
    business_description="Ice cream shop with outdoor seating",
    customers="Mostly tourists and families in summer",
    location="Austin, TX",
    operational_dependencies="Refrigeration, a delivery van, foot traffic",
    key_materials="Dairy, sugar, electricity, gas for the van",
    past_impacts="Rainy weekends, heat waves, gas price spikes",
    time_of_year="June-August is tourist season; winter is slow",
    locked_in_costs="Milk is on a fixed-price contract through 2027",
    risk_budget="$500 a month",
)

CATEGORIES = [
    HedgeableCategory(category="rain", label="Rain", reasoning="Rainy weekends empty the patio.", confidence=90, market_family="rain"),
    HedgeableCategory(category="gas_prices", label="Gas prices", reasoning="The delivery van runs on gas.", confidence=60, market_family="gas"),
]

MARKETS = [
    KalshiMarket(ticker="KXRAINAUSM-26OCT-4", title="Rain in Austin in Oct 2026?", subtitle="Above 4 inches", yes_price=0.2, no_price=0.85),
    KalshiMarket(ticker="KXAAAGASM-26OCT31-3.50", title="Will average gas prices be above $3.50?", subtitle="Above $3.50", yes_price=0.3, no_price=0.75),
]

# A washed-out May and June, mirroring demo-data/two-scoops-creamery: the point of
# a simulated year is that something went wrong in it. A flat year corroborates no
# hit months at all (see app/hit_months.py), which makes it useless as a fixture.
_WASHED_OUT_MONTHS = (4, 5)
HISTORY = ProfitHistory(
    simulated_year=2024,
    points=[
        ProfitPoint(period=label, expected=1000, actual=400 if month in _WASHED_OUT_MONTHS else 1000)
        for month, label in enumerate(MONTH_LABELS)
    ],
)

NOTES = {4: "Rainiest May in years: patio empty most weekends"}

CANDIDATES = {"rain": [MARKETS[0]], "gas_prices": [MARKETS[1]]}
