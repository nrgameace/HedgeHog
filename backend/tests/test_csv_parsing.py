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


def test_raises_on_field_larger_than_csv_module_limit():
    content = b"note\n" + b"a" * 200_000 + b"\n"

    with pytest.raises(InvalidCsvError):
        parse_csv_rows(content)
