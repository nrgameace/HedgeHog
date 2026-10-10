import csv
import io

TREND_DETECTION_SYSTEM_PROMPT = """You are a financial risk analyst for Hedgehog, a tool that helps small business owners hedge against market volatility using prediction markets (Kalshi).

Given a business's industry, the factors the owner believes affect their revenue, and their recent financial data, identify which real-world categories of risk this business could hedge against.

A hedgeable category is a specific, publicly-tradeable real-world factor (for example: rain/weather, fuel prices, natural gas prices, livestock prices, GPU/semiconductor prices, interest rates, or a named sports team's win/loss record) that plausibly correlates with this business's revenue or costs, based on the evidence given. Only propose categories grounded in what the owner said or what the financial data shows a pattern for. Do not invent categories unrelated to the business or the data.

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


def build_trend_detection_messages(industry: str, loss_factors: str, financials: list[dict[str, str]]) -> list[dict[str, str]]:
    row_count = len(financials)
    if row_count > 200:
        row_count_line = f"Financial data (CSV, showing first 200 of {row_count} rows):"
    else:
        row_count_line = f"Financial data (CSV, {row_count} rows):"
    csv_text = _format_financials_csv(financials)
    user_content = f"""Industry: {industry}
Owner-identified risk factors: {loss_factors}

{row_count_line}
{csv_text}"""
    return [
        {"role": "system", "content": TREND_DETECTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
