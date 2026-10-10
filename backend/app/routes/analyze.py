from dataclasses import asdict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.akamai_client import AkamaiApiError, AkamaiConfigError
from app.csv_parsing import InvalidCsvError, parse_csv_rows
from app.questionnaire import InvalidQuestionnaireAnswersError, QuestionnaireAnswers
from app.trend_detection import TrendDetectionError, detect_hedgeable_categories

router = APIRouter()

MAX_FINANCIALS_CSV_SIZE_BYTES = 5 * 1024 * 1024
_CHUNK_SIZE_BYTES = 64 * 1024


async def _read_within_limit(file: UploadFile, max_size_bytes: int) -> bytes:
    chunks = bytearray()
    while chunk := await file.read(_CHUNK_SIZE_BYTES):
        chunks.extend(chunk)
        if len(chunks) > max_size_bytes:
            raise HTTPException(status_code=413, detail=f"financials file exceeds the {max_size_bytes}-byte limit")
    return bytes(chunks)


@router.post("/analyze")
async def analyze(answers: str = Form(...), financials: UploadFile | None = File(None)) -> dict:
    try:
        parsed_answers = QuestionnaireAnswers.from_json(answers)
    except InvalidQuestionnaireAnswersError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rows: list[dict[str, str]] = []
    if financials is not None:
        content = await _read_within_limit(financials, MAX_FINANCIALS_CSV_SIZE_BYTES)
        try:
            rows = parse_csv_rows(content)
        except InvalidCsvError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        categories = await run_in_threadpool(detect_hedgeable_categories, parsed_answers, rows)
    except AkamaiConfigError as exc:
        raise HTTPException(status_code=500, detail="the analysis service is misconfigured") from exc
    except AkamaiApiError as exc:
        raise HTTPException(status_code=502, detail="the analysis service is temporarily unavailable") from exc
    except TrendDetectionError as exc:
        raise HTTPException(status_code=502, detail="the analysis service returned an unexpected response") from exc

    return {"hedgeable_categories": [asdict(category) for category in categories]}
