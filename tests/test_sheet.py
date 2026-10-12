import pytest

from app.pipeline.sheet import (
    HEADERS,
    SheetFormatError,
    build_row,
    message_ids_from_column,
)
from tests.helpers import sample_record


def test_column_reads_ids_and_skips_the_header():
    values = [["message_id"], ["msg-1"], ["msg-2"]]
    assert message_ids_from_column(values) == {"msg-1", "msg-2"}


def test_empty_sheet_has_no_ids():
    assert message_ids_from_column([]) == set()


def test_wrong_header_is_rejected():
    with pytest.raises(SheetFormatError):
        message_ids_from_column([["other"]])


def test_formula_like_text_is_prefixed():
    row = build_row(sample_record(subject="=1+1", transcript="+cmd"))
    assert row[HEADERS.index("subject")] == "'=1+1"
    assert row[HEADERS.index("transcript")] == "'+cmd"
    assert row[0] == "msg-1"
