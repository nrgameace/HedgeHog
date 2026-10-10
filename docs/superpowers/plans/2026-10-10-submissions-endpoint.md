# Submissions Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `POST /submissions` endpoint that accepts the questionnaire's two string answers plus a financials CSV upload, and returns them back as structured JSON (string fields + parsed CSV rows) for later forwarding to the Akamai model calls.

**Architecture:** A pure, synchronous CSV-parsing module (`app/csv_parsing.py`) that turns raw bytes into `list[dict[str, str]]` or raises a typed error — unit tested in isolation with no FastAPI/async machinery. A FastAPI router (`app/routes/submissions.py`) that accepts `multipart/form-data`, enforces the upload size limit by reading in chunks, delegates parsing to that module, and maps errors to HTTP status codes — tested via FastAPI's `TestClient`.

**Tech Stack:** FastAPI, Starlette's `UploadFile`/`Form`/`File`, Python's stdlib `csv` module, pytest + `TestClient`.

**Spec:** No separate spec file — this is a bounded task designed in chat. The decisions below (endpoint shape, field names, size limit, error codes, response shape) are the full spec; see [CLAUDE.md](../../../CLAUDE.md) for overall project context.

## Global Constraints

- All function/method declarations go on one line, however long (global coding rule) — no multi-line `def` signatures.
- TDD required: write the failing test before the implementation for every step below.
- Financials CSV size limit: **5 MB** (5 * 1024 * 1024 bytes), enforced by reading the upload in chunks rather than loading it fully first.
- Malformed/empty/ragged CSV content → `400 Bad Request` with a `detail` string explaining what's wrong.
- Oversized upload → `413 Payload Too Large`.
- Missing required `industry` / `loss_factors` / `financials` fields → FastAPI's built-in `422 Unprocessable Entity` (no custom handling needed — just verify it with a test).
- Backend tests run via `cd backend && ./venv/bin/pytest`.
- New modules import as `from app....` (matches the existing `pythonpath = .` setting in `backend/pytest.ini`).

## Review Focus

- Ragged CSV rows (a data row with more or fewer columns than the header) — Python's `csv.DictReader` silently puts a `None` key or `None` values in this case instead of raising; must be detected and turned into a `400`, not returned as broken JSON.
- CSV content that isn't valid UTF-8 (e.g. a binary file uploaded by mistake) — must return `400`, not an unhandled `UnicodeDecodeError` (which would surface as a `500`).
- Upload at or over the 5 MB limit — must return `413` before the whole file is buffered in memory, not after.
- An empty (0-byte) upload — has no header row to speak of, must return `400` rather than succeeding with an empty row list.
- A header-only CSV (valid header, zero data rows) — must succeed with `financials: []`, not be treated as an error (distinguishes "no data" from "no header").

---

### Task 1: CSV parsing helper

**Files:**
- Create: `backend/app/csv_parsing.py`
- Test: `backend/tests/test_csv_parsing.py`

**Interfaces:**
- Produces: `InvalidCsvError(Exception)` and `parse_csv_rows(content: bytes) -> list[dict[str, str]]` in `app.csv_parsing`, raising `InvalidCsvError` on any invalid input. Task 2 imports both directly from this module.

- [ ] **Step 1: Write the failing tests**

```python
import pytest

from app.csv_parsing import InvalidCsvError, parse_csv_rows


def test_parses_valid_csv_into_rows():
    content = b"date,revenue\n2026-01-01,412.50\n2026-01-02,380.00\n"

    rows = parse_csv_rows(content)

    assert rows == [
        {"date": "2026-01-01", "revenue": "412.50"},
        {"date": "2026-01-02", "revenue": "380.00"},
    ]


def test_returns_empty_list_for_header_only_csv():
    content = b"date,revenue\n"

    assert parse_csv_rows(content) == []


def test_raises_on_empty_content():
    with pytest.raises(InvalidCsvError):
        parse_csv_rows(b"")


def test_raises_on_non_utf8_content():
    with pytest.raises(InvalidCsvError):
        parse_csv_rows(b"\xff\xfe\x00\x01")


def test_raises_on_ragged_row():
    content = b"date,revenue\n2026-01-01,412.50,extra\n"

    with pytest.raises(InvalidCsvError):
        parse_csv_rows(content)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ./venv/bin/pytest tests/test_csv_parsing.py -v`
Expected: FAIL / ERROR with "No module named 'app.csv_parsing'"

- [ ] **Step 3: Implement `InvalidCsvError` and `parse_csv_rows(content: bytes) -> list[dict[str, str]]` in `backend/app/csv_parsing.py`**

Decode `content` as UTF-8, catching `UnicodeDecodeError` and re-raising as `InvalidCsvError`. Parse with `csv.DictReader` over the decoded text. If `reader.fieldnames` is `None` (nothing to read — covers the empty-content case), raise `InvalidCsvError`. For each row, check whether `csv.DictReader` populated a `None` key (extra columns) or any `None` value (missing columns) and raise `InvalidCsvError` naming the offending row if so; otherwise collect the row dict. Return the collected list (empty list for a header-only file).

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/pytest tests/test_csv_parsing.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/csv_parsing.py backend/tests/test_csv_parsing.py
git commit -m "feat: add CSV parsing helper for financials uploads"
```

---

### Task 2: Submissions endpoint

**Files:**
- Create: `backend/app/routes/__init__.py` (empty package marker)
- Create: `backend/app/routes/submissions.py`
- Modify: `backend/app/main.py` (register the new router)
- Test: `backend/tests/test_submissions.py`

**Interfaces:**
- Consumes: `InvalidCsvError`, `parse_csv_rows(content: bytes) -> list[dict[str, str]]` from `app.csv_parsing` (Task 1).
- Produces: `router: APIRouter` in `app.routes.submissions`, exposing `POST /submissions`. `app.main` imports it as `from app.routes.submissions import router as submissions_router` and registers it with `app.include_router(submissions_router)`.

- [ ] **Step 1: Write the failing tests**

```python
import io

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _post_submission(csv_bytes: bytes, industry: str = "ice cream shop", loss_factors: str = "rainy days, gas prices"):
    return client.post(
        "/submissions",
        data={"industry": industry, "loss_factors": loss_factors},
        files={"financials": ("financials.csv", io.BytesIO(csv_bytes), "text/csv")},
    )


def test_create_submission_returns_parsed_data():
    csv_bytes = b"date,revenue\n2026-01-01,412.50\n"

    response = _post_submission(csv_bytes)

    assert response.status_code == 200
    assert response.json() == {
        "industry": "ice cream shop",
        "loss_factors": "rainy days, gas prices",
        "financials": [{"date": "2026-01-01", "revenue": "412.50"}],
    }


def test_create_submission_rejects_file_over_size_limit():
    oversized_csv = b"date,revenue\n" + b"2026-01-01,412.50\n" * 400_000

    response = _post_submission(oversized_csv)

    assert response.status_code == 413


def test_create_submission_rejects_malformed_csv():
    ragged_csv = b"date,revenue\n2026-01-01,412.50,extra\n"

    response = _post_submission(ragged_csv)

    assert response.status_code == 400
    assert "detail" in response.json()


def test_create_submission_requires_industry_field():
    response = client.post(
        "/submissions",
        data={"loss_factors": "rainy days"},
        files={"financials": ("financials.csv", io.BytesIO(b"date,revenue\n"), "text/csv")},
    )

    assert response.status_code == 422
```

(`oversized_csv` must exceed 5 MB — `b"2026-01-01,412.50\n" * 400_000` is ~7 MB; adjust the repeat count if needed so the test file is comfortably over the limit without being unnecessarily large.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ./venv/bin/pytest tests/test_submissions.py -v`
Expected: FAIL / ERROR with "404 Not Found" (no `/submissions` route yet) or import error

- [ ] **Step 3: Implement the router in `backend/app/routes/submissions.py`**

Define `MAX_FINANCIALS_CSV_SIZE_BYTES = 5 * 1024 * 1024` at module level. Implement `async def _read_within_limit(file: UploadFile, max_size_bytes: int) -> bytes:` that reads `file` in fixed-size chunks (e.g. 64 KB via `await file.read(65536)`) accumulating into a `bytearray`, and raises `HTTPException(status_code=413, detail=...)` as soon as the accumulated size exceeds `max_size_bytes` — stop reading at that point rather than continuing to buffer the rest of the file. Implement `async def create_submission(industry: str = Form(...), loss_factors: str = Form(...), financials: UploadFile = File(...)) -> dict:` registered on `router` (an `APIRouter()`) as `@router.post("/submissions")`, which calls `_read_within_limit`, then calls `parse_csv_rows` on the resulting bytes catching `InvalidCsvError` and re-raising as `HTTPException(status_code=400, detail=str(exc))`, then returns `{"industry": industry, "loss_factors": loss_factors, "financials": rows}`.

- [ ] **Step 4: Wire the router into the app in `backend/app/main.py`**

Add `from app.routes.submissions import router as submissions_router` and `app.include_router(submissions_router)` alongside the existing `/health` route. Create the empty `backend/app/routes/__init__.py` package marker.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/pytest -v`
Expected: all tests pass, including the pre-existing `tests/test_main.py::test_health_check_returns_ok`

- [ ] **Step 6: Commit**

```bash
git add backend/app/routes/__init__.py backend/app/routes/submissions.py backend/app/main.py backend/tests/test_submissions.py
git commit -m "feat: add POST /submissions endpoint for questionnaire + financials CSV"
```
