import csv
import io

from app.questionnaire import QuestionnaireAnswers

TREND_DETECTION_SYSTEM_PROMPT = """You are a financial risk analyst for Hedgehog, a tool that helps small business owners hedge against market volatility using prediction markets (Kalshi).

You are given a business owner's answers to a short questionnaire about their business, plus their recent financial data. Your job is to identify which real-world categories of risk this business could hedge against.

The questionnaire covers: what the business does, who its customers are, where it operates, what it depends on day to day, what materials or services it relies on most, what outside events have hurt it before or worry the owner, what times of year matter most and why, which costs (if any) are already locked in at a fixed price, and how much budget the owner has for risk mitigation.

A hedgeable category is a specific, publicly-tradeable real-world factor (for example: rain/weather, fuel prices, natural gas prices, livestock prices, GPU/semiconductor prices, interest rates, or a named sports team's win/loss record) that plausibly correlates with this business's revenue or costs, based on the evidence given. Only propose categories grounded in what the owner said or what the financial data shows a pattern for. Do not invent categories unrelated to the business or the data. A cost the owner already locked in at a fixed price is not a current risk — do not propose hedging it.

Respond with ONLY a single JSON object. No markdown code fences, no explanation before or after it. Match exactly this shape:

{"hedgeable_categories": [{"category": "<short_snake_case_slug>", "label": "<Human Readable Name>", "reasoning": "<one or two sentences grounded in the business's stated factors or financial data>"}]}

Return between 1 and 5 categories, ordered from most to least relevant. If the data gives no clear signal for a category, do not include it."""


def _format_financials_csv(financials: list[dict[str, str]], max_rows: int = 200) -> str:
    if not financials:
        return ""
    rows = financials[:max_rows]
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def build_trend_detection_messages(answers: QuestionnaireAnswers, financials: list[dict[str, str]]) -> list[dict[str, str]]:
    row_count = len(financials)
    if row_count > 200:
        row_count_line = f"Financial data (CSV, showing first 200 of {row_count} rows):"
    else:
        row_count_line = f"Financial data (CSV, {row_count} rows):"
    csv_text = _format_financials_csv(financials)
    user_content = f"""What the business does: {answers.business_description}
Customers: {answers.customers}
Location: {answers.location}
Day-to-day operational dependencies: {answers.operational_dependencies}
Key materials or services relied on: {answers.key_materials}
Past impacts / biggest worries: {answers.past_impacts}
Important times of year: {answers.time_of_year}
Costs already locked in at a fixed price: {answers.locked_in_costs}
Risk mitigation budget: {answers.risk_budget}

{row_count_line}
{csv_text}"""
    return [
        {"role": "system", "content": TREND_DETECTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
