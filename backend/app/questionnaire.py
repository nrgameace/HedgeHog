import json
from dataclasses import dataclass

_FIELD_MAP = {
    "businessDescription": "business_description",
    "customers": "customers",
    "location": "location",
    "operationalDependencies": "operational_dependencies",
    "keyMaterials": "key_materials",
    "pastImpacts": "past_impacts",
    "timeOfYear": "time_of_year",
    "lockedInCosts": "locked_in_costs",
    "riskBudget": "risk_budget",
}


class InvalidQuestionnaireAnswersError(Exception):
    pass


@dataclass
class QuestionnaireAnswers:
    business_description: str
    customers: str
    location: str
    operational_dependencies: str
    key_materials: str
    past_impacts: str
    time_of_year: str
    locked_in_costs: str
    risk_budget: str

    @classmethod
    def from_json(cls, payload: str) -> "QuestionnaireAnswers":
        try:
            data = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise InvalidQuestionnaireAnswersError(f"answers was not valid JSON: {payload}") from exc
        if not isinstance(data, dict):
            raise InvalidQuestionnaireAnswersError(f"answers must be a JSON object: {payload}")
        kwargs = {field_name: data.get(json_key, "") for json_key, field_name in _FIELD_MAP.items()}
        kwargs = {field_name: value if isinstance(value, str) else "" for field_name, value in kwargs.items()}
        return cls(**kwargs)
