import pytest

from app.model.json_reply import ModelReplyError, parse_json_object


class TestExtraction:
    def test_parses_a_bare_json_object(self):
        assert parse_json_object('{"terms": ["b200"]}') == {"terms": ["b200"]}

    def test_strips_a_json_code_fence(self):
        """Models routinely wrap JSON in fences even when told not to."""
        assert parse_json_object('```json\n{"terms": ["b200"]}\n```') == {"terms": ["b200"]}

    def test_strips_a_bare_code_fence(self):
        assert parse_json_object('```\n{"a": 1}\n```') == {"a": 1}

    def test_tolerates_prose_before_and_after(self):
        chatty = 'Sure! Here is the mapping:\n{"terms": ["b200"]}\nHope that helps.'

        assert parse_json_object(chatty) == {"terms": ["b200"]}

    def test_tolerates_prose_after_a_closing_fence(self):
        """A fence plus a trailing sentence defeats a strict startswith/endswith check."""
        trailing = '```json\n{"a": 1}\n```\nLet me know if you need more.'

        assert parse_json_object(trailing) == {"a": 1}

    def test_handles_nested_objects(self):
        assert parse_json_object('{"a": {"b": {"c": 1}}}') == {"a": {"b": {"c": 1}}}

    def test_ignores_surrounding_whitespace(self):
        assert parse_json_object('\n\n  {"a": 1}  \n') == {"a": 1}


class TestRejection:
    def test_a_reply_with_no_object_is_rejected(self):
        with pytest.raises(ModelReplyError, match="no JSON object"):
            parse_json_object("I cannot help with that.")

    def test_truncated_json_is_rejected(self):
        with pytest.raises(ModelReplyError):
            parse_json_object('{"terms": [')

    def test_malformed_json_between_braces_is_rejected(self):
        with pytest.raises(ModelReplyError, match="not valid JSON"):
            parse_json_object('{"terms": [1 2 3]}')

    def test_a_json_array_is_rejected_because_an_object_was_requested(self):
        with pytest.raises(ModelReplyError):
            parse_json_object('["b200"]')

    def test_an_empty_reply_is_rejected(self):
        with pytest.raises(ModelReplyError):
            parse_json_object("")

    def test_the_error_excerpt_stays_short_enough_to_log(self):
        with pytest.raises(ModelReplyError) as caught:
            parse_json_object("no json here " * 500)

        assert len(str(caught.value)) < 400
