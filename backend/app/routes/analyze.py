from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.akamai_client import AkamaiApiError, AkamaiConfigError
from app.csv_parsing import InvalidCsvError, parse_csv_rows
from app.financial_history import FinancialHistoryError
from app.pipeline import run_analysis
from app.position_sizing import PositionSizingError
from app.questionnaire import InvalidQuestionnaireAnswersError, QuestionnaireAnswers
from app.trend_detection import TrendDetectionError

router = APIRouter()

MAX_FINANCIALS_CSV_SIZE_BYTES = 5 * 1024 * 1024
_CHUNK_SIZE_BYTES = 64 * 1024
MISSING_FINANCIALS_MESSAGE = "Upload your financials CSV so we can simulate your trades."


async def _read_within_limit(file: UploadFile, max_size_bytes: int) -> bytes:
    chunks = bytearray()
    while chunk := await file.read(_CHUNK_SIZE_BYTES):
        chunks.extend(chunk)
        if len(chunks) > max_size_bytes:
            raise HTTPException(status_code=413, detail=f"financials file exceeds the {max_size_bytes}-byte limit")
    return bytes(chunks)


async def _read_financial_rows(financials: UploadFile | None) -> list[dict[str, str]]:
    if financials is None:
        raise HTTPException(status_code=400, detail=MISSING_FINANCIALS_MESSAGE)
    content = await _read_within_limit(financials, MAX_FINANCIALS_CSV_SIZE_BYTES)
    try:
        return parse_csv_rows(content)
    except InvalidCsvError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/analyze")
async def analyze(answers: str = Form(...), financials: UploadFile | None = File(None)) -> dict:
    try:
        parsed_answers = QuestionnaireAnswers.from_json(answers)
    except InvalidQuestionnaireAnswersError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rows = await _read_financial_rows(financials)

    try:
        return await run_in_threadpool(run_analysis, parsed_answers, rows)
    except FinancialHistoryError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AkamaiConfigError as exc:
        raise HTTPException(status_code=500, detail="the analysis service is misconfigured") from exc
    except AkamaiApiError as exc:
        raise HTTPException(status_code=502, detail="the analysis service is temporarily unavailable") from exc
    except (TrendDetectionError, PositionSizingError) as exc:
        raise HTTPException(status_code=502, detail="the analysis service returned an unexpected response") from exc
