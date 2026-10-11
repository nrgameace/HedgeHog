import pytest

from app.model_json import parse_model_json


def test_parses_plain_json():
    assert parse_model_json('{"a": 1}') == {"a": 1}


def test_strips_json_fence():
    assert parse_model_json('```json\n{"a": 1}\n```') == {"a": 1}


def test_strips_bare_fence():
    assert parse_model_json('  ```\n{"a": 1}\n```  ') == {"a": 1}


def test_raises_value_error_on_garbage():
    with pytest.raises(ValueError):
        parse_model_json("not json at all")
