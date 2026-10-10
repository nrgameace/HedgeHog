from app.prompts import TREND_DETECTION_SYSTEM_PROMPT, build_trend_detection_messages


def test_build_trend_detection_messages_starts_with_system_prompt():
    messages = build_trend_detection_messages("ice cream shop", "rainy days, gas prices", [])

    assert messages[0] == {"role": "system", "content": TREND_DETECTION_SYSTEM_PROMPT}


def test_build_trend_detection_messages_includes_industry_and_loss_factors():
    messages = build_trend_detection_messages("ice cream shop", "rainy days, gas prices", [])

    user_content = messages[1]["content"]
    assert "ice cream shop" in user_content
    assert "rainy days, gas prices" in user_content


def test_build_trend_detection_messages_includes_csv_rows():
    financials = [{"date": "2026-01-01", "revenue": "412.50"}]

    messages = build_trend_detection_messages("ice cream shop", "rainy days", financials)

    assert "412.50" in messages[1]["content"]


def test_build_trend_detection_messages_truncates_rows_over_200_with_a_note():
    financials = [{"date": f"2026-01-{i:03d}", "revenue": str(i)} for i in range(1, 251)]

    messages = build_trend_detection_messages("ice cream shop", "rainy days", financials)

    user_content = messages[1]["content"]
    assert "first 200 of 250 rows" in user_content
    assert financials[199]["date"] in user_content
    assert financials[200]["date"] not in user_content


def test_build_trend_detection_messages_no_truncation_note_under_cap():
    financials = [{"date": "2026-01-01", "revenue": "412.50"}]

    messages = build_trend_detection_messages("ice cream shop", "rainy days", financials)

    assert "first 200" not in messages[1]["content"]
