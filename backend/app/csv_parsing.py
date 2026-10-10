import csv
import io


class InvalidCsvError(Exception):
    pass


def parse_csv_rows(content: bytes) -> list[dict[str, str]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise InvalidCsvError("financials file is not valid UTF-8 text") from exc

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise InvalidCsvError("financials file has no header row")

    rows: list[dict[str, str]] = []
    row_iterator = enumerate(reader, start=2)
    while True:
        try:
            line_number, row = next(row_iterator)
        except StopIteration:
            break
        except csv.Error as exc:
            raise InvalidCsvError(f"financials file is malformed: {exc}") from exc
        if None in row or None in row.values():
            raise InvalidCsvError(f"row {line_number} has a different number of columns than the header")
        rows.append(row)
    return rows
