import csv
import io


class InvalidCsvError(Exception):
    pass


def parse_csv_rows(content: bytes) -> list[dict[str, str]]:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidCsvError("financials file is not valid UTF-8 text") from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise InvalidCsvError("financials file has no header row")

    rows: list[dict[str, str]] = []
    for line_number, row in enumerate(reader, start=2):
        if None in row or None in row.values():
            raise InvalidCsvError(f"row {line_number} has a different number of columns than the header")
        rows.append(row)
    return rows
