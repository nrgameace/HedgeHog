from app.prompts import POSITION_SIZING_SYSTEM_PROMPT, TREND_DETECTION_SYSTEM_PROMPT, build_position_sizing_messages, build_trend_detection_messages
from tests.sample_data import ANSWERS, CATEGORIES, HISTORY, MARKETS, NOTES


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


def test_build_trend_detection_messages_includes_csv_rows():
    financials = [{"date": "2026-01-01", "revenue": "412.50"}]

    messages = build_trend_detection_messages(ANSWERS, financials)

    assert "412.50" in messages[1]["content"]


def test_build_trend_detection_messages_truncates_rows_over_200_with_a_note():
    financials = [{"date": f"2026-01-{i:03d}", "revenue": str(i)} for i in range(1, 251)]

    messages = build_trend_detection_messages(ANSWERS, financials)

    user_content = messages[1]["content"]
    assert "first 200 of 250 rows" in user_content
    assert financials[199]["date"] in user_content
    assert financials[200]["date"] not in user_content


def test_build_trend_detection_messages_no_truncation_note_under_cap():
    financials = [{"date": "2026-01-01", "revenue": "412.50"}]

    messages = build_trend_detection_messages(ANSWERS, financials)

    assert "first 200" not in messages[1]["content"]


def test_build_trend_detection_messages_no_truncation_note_at_exactly_200_rows():
    financials = [{"date": f"2026-01-{i:03d}", "revenue": str(i)} for i in range(1, 201)]

    messages = build_trend_detection_messages(ANSWERS, financials)

    user_content = messages[1]["content"]
    assert "first 200" not in user_content
    assert financials[199]["date"] in user_content


def test_build_trend_detection_messages_notes_zero_rows_for_empty_financials():
    messages = build_trend_detection_messages(ANSWERS, [])

    assert "0 rows" in messages[1]["content"]


def _position_sizing_user_content() -> str:
    return build_position_sizing_messages(ANSWERS, CATEGORIES, HISTORY, NOTES, MARKETS)[1]["content"]


def test_build_position_sizing_messages_starts_with_system_prompt():
    messages = build_position_sizing_messages(ANSWERS, CATEGORIES, HISTORY, NOTES, MARKETS)

    assert messages[0] == {"role": "system", "content": POSITION_SIZING_SYSTEM_PROMPT}


def test_build_position_sizing_messages_includes_trend_detection_categories():
    user_content = _position_sizing_user_content()

    assert "rain | Rain | Rainy weekends empty the patio." in user_content
    assert "gas_prices | Gas prices | The delivery van runs on gas." in user_content


def test_build_position_sizing_messages_includes_candidate_markets_with_prices():
    user_content = _position_sizing_user_content()

    assert "KXRAINAUSM-26OCT-4 | Rain in Austin in Oct 2026? — Above 4 inches | YES price 0.20" in user_content
    assert "KXAAAGASM-26OCT31-3.50" in user_content


def test_build_position_sizing_messages_includes_simulated_year_and_notes():
    user_content = _position_sizing_user_content()

    assert "2024" in user_content
    assert "May: expected 1000 / actual 1000 — Rainiest May in years: patio empty most weekends" in user_content
    assert "Jan: expected 1000 / actual 1000\n" in user_content


def test_build_position_sizing_messages_includes_budget_and_context_answers():
    user_content = _position_sizing_user_content()

    for answer in (ANSWERS.risk_budget, ANSWERS.location, ANSWERS.time_of_year, ANSWERS.locked_in_costs, ANSWERS.business_description):
        assert answer in user_content


def test_position_sizing_prompt_treats_candidates_as_recurring_series():
    assert "recurring series" in POSITION_SIZING_SYSTEM_PROMPT
    assert "not by the month or date in the contract's title" in POSITION_SIZING_SYSTEM_PROMPT
