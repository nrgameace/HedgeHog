from app.prompts import TREND_DETECTION_SYSTEM_PROMPT, build_trend_detection_messages
from app.questionnaire import QuestionnaireAnswers

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
