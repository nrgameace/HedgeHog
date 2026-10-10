import pytest

from app.questionnaire import InvalidQuestionnaireAnswersError, QuestionnaireAnswers

VALID_PAYLOAD = """{
    "businessDescription": "Ice cream shop with outdoor seating",
    "customers": "Mostly tourists and families in summer",
    "location": "Austin, TX",
    "operationalDependencies": "Refrigeration, a delivery van, foot traffic",
    "keyMaterials": "Dairy, sugar, electricity, gas for the van",
    "pastImpacts": "Rainy weekends, heat waves, gas price spikes",
    "timeOfYear": "June-August is tourist season; winter is slow",
    "lockedInCosts": "Milk is on a fixed-price contract through 2027",
    "riskBudget": "$500 a month"
}"""


def test_from_json_parses_all_fields():
    answers = QuestionnaireAnswers.from_json(VALID_PAYLOAD)

    assert answers == QuestionnaireAnswers(
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


def test_from_json_defaults_missing_fields_to_empty_string():
    answers = QuestionnaireAnswers.from_json("{}")

    assert answers == QuestionnaireAnswers(
        business_description="",
        customers="",
        location="",
        operational_dependencies="",
        key_materials="",
        past_impacts="",
        time_of_year="",
        locked_in_costs="",
        risk_budget="",
    )


def test_from_json_coerces_non_string_value_to_empty_string():
    answers = QuestionnaireAnswers.from_json('{"customers": 42}')

    assert answers.customers == ""


def test_from_json_raises_on_invalid_json():
    with pytest.raises(InvalidQuestionnaireAnswersError):
        QuestionnaireAnswers.from_json("not json")


def test_from_json_raises_on_non_object_json():
    with pytest.raises(InvalidQuestionnaireAnswersError):
        QuestionnaireAnswers.from_json("[1, 2, 3]")
