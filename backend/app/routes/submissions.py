from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.csv_parsing import InvalidCsvError, parse_csv_rows

router = APIRouter()

MAX_FINANCIALS_CSV_SIZE_BYTES = 5 * 1024 * 1024
_CHUNK_SIZE_BYTES = 64 * 1024


async def _read_within_limit(file: UploadFile, max_size_bytes: int) -> bytes:
    chunks = bytearray()
    while chunk := await file.read(_CHUNK_SIZE_BYTES):
        chunks.extend(chunk)
        if len(chunks) > max_size_bytes:
            raise HTTPException(status_code=413, detail=f"financials file exceeds {max_size_bytes} byte limit")
    return bytes(chunks)


@router.post("/submissions")
async def create_submission(industry: str = Form(...), loss_factors: str = Form(...), financials: UploadFile = File(...)) -> dict:
    content = await _read_within_limit(financials, MAX_FINANCIALS_CSV_SIZE_BYTES)
    try:
        rows = parse_csv_rows(content)
    except InvalidCsvError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"industry": industry, "loss_factors": loss_factors, "financials": rows}
