from app.prompts import POSITION_SIZING_SYSTEM_PROMPT, TREND_DETECTION_SYSTEM_PROMPT, build_position_sizing_messages, build_trend_detection_messages
from tests.sample_data import ANSWERS, CANDIDATES, CATEGORIES, HISTORY, NOTES


def test_build_trend_detection_messages_starts_with_system_prompt():
    messages = build_trend_detection_messages(ANSWERS, [])

    assert messages[0] == {"role": "system", "content": TREND_DETECTION_SYSTEM_PROMPT}


def test_build_trend_detection_messages_includes_every_answer_field():
    messages = build_trend_detection_messages(ANSWERS, [])

    user_content = messages[1]["content"]
    assert ANSWERS.business_description in user_content
    assert ANSWERS.customers in user_content
    assert ANSWERS.location in user_content
    assert ANSWERS.operational_dependencies in user_content
    assert ANSWERS.key_materials in user_content
    assert ANSWERS.past_impacts in user_content
    assert ANSWERS.time_of_year in user_content
    assert ANSWERS.locked_in_costs in user_content
    assert ANSWERS.risk_budget in user_content


def test_build_trend_detection_messages_includes_evidence_digest():
    financials = [{"month": "2024-01", "operating_income": "100", "notes": "Opened"}]

    user_content = build_trend_detection_messages(ANSWERS, financials)[1]["content"]

    assert "Worst months vs. a normal year:" in user_content
    assert "- 2024-01: Opened" in user_content
    assert "Biggest swings by column:" in user_content


def test_build_trend_detection_messages_sends_only_the_last_24_rows():
    financials = [{"month": f"{2020 + index // 12}-{index % 12 + 1:02d}", "operating_income": str(index)} for index in range(30)]

    user_content = build_trend_detection_messages(ANSWERS, financials)[1]["content"].split("Most recent rows")[1]

    assert "2020-06,5" not in user_content
    assert "2020-07,6" in user_content
    assert "2022-06,29" in user_content
    assert "last 24 of 30 rows" in user_content


def test_build_trend_detection_messages_handles_empty_financials():
    assert "0 rows" in build_trend_detection_messages(ANSWERS, [])[1]["content"]


def test_trend_detection_prompt_asks_for_every_factor_with_confidence():
    assert "every factor" in TREND_DETECTION_SYSTEM_PROMPT
    assert "confidence" in TREND_DETECTION_SYSTEM_PROMPT
    assert "market_family" in TREND_DETECTION_SYSTEM_PROMPT


def _position_sizing_user_content() -> str:
    return build_position_sizing_messages(ANSWERS, CATEGORIES, HISTORY, NOTES, CANDIDATES)[1]["content"]


def test_build_position_sizing_messages_starts_with_system_prompt():
    messages = build_position_sizing_messages(ANSWERS, CATEGORIES, HISTORY, NOTES, CANDIDATES)

    assert messages[0] == {"role": "system", "content": POSITION_SIZING_SYSTEM_PROMPT}


def test_build_position_sizing_messages_groups_candidates_under_each_factor():
    user_content = _position_sizing_user_content()

    rain_block = user_content.split("Factor: rain")[1].split("Factor: gas_prices")[0]
    assert "Rain (confidence 90) — Rainy weekends empty the patio." in rain_block
    assert "- KXRAINAUSM-26OCT-4 | Rain in Austin in Oct 2026? — Above 4 inches | YES price 0.20" in rain_block
    assert "KXAAAGASM" not in rain_block


def test_build_position_sizing_messages_includes_simulated_year_and_notes():
    user_content = _position_sizing_user_content()

    assert "2024" in user_content
    assert "May: expected 1000 / actual 400 — Rainiest May in years: patio empty most weekends" in user_content
    assert "Jan: expected 1000 / actual 1000\n" in user_content


def test_build_position_sizing_messages_includes_budget_and_context_answers():
    user_content = _position_sizing_user_content()

    for answer in (ANSWERS.risk_budget, ANSWERS.location, ANSWERS.time_of_year, ANSWERS.locked_in_costs, ANSWERS.business_description):
        assert answer in user_content


def test_position_sizing_prompt_treats_candidates_as_recurring_series():
    assert "recurring series" in POSITION_SIZING_SYSTEM_PROMPT
    assert "not by the month or date in the contract's title" in POSITION_SIZING_SYSTEM_PROMPT


def test_position_sizing_prompt_requires_every_factor_and_leaves_budget_to_the_backend():
    assert "Plan every factor" in POSITION_SIZING_SYSTEM_PROMPT
    assert "never leave out a factor to save money" in POSITION_SIZING_SYSTEM_PROMPT


def test_prompts_keep_explanations_short():
    assert "at most 25 words" in TREND_DETECTION_SYSTEM_PROMPT
    assert "at most 25 words" in POSITION_SIZING_SYSTEM_PROMPT
