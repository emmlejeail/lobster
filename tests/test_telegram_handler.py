"""Tests for _split_message in handlers/telegram_handler.py"""
from handlers.telegram_handler import _split_message


def test_short_text_returns_single_chunk():
    text = "Hello, world!"
    assert _split_message(text) == [text]


def test_exactly_at_limit_returns_single_chunk():
    text = "x" * 4096
    result = _split_message(text)
    assert result == [text]


def test_splits_on_section_header():
    # Put a ### header before position 4096 so it becomes the split point
    header = "\n### Second Section"
    part1 = "a" * 3000
    part2 = "b" * 2000
    text = part1 + header + part2
    result = _split_message(text)
    assert len(result) == 2
    assert result[1].startswith("### Second Section")


def test_falls_back_to_double_newline():
    # No ### header before limit, but a \n\n around position 3000
    part1 = "a" * 3000
    part2 = "b" * 2000
    text = part1 + "\n\n" + part2
    result = _split_message(text)
    assert len(result) == 2
    # Both chunks must be within the default limit
    for chunk in result:
        assert len(chunk) <= 4096


def test_hard_cut_as_last_resort():
    # 9000 x-chars with no whitespace → must hard-cut into chunks all ≤ 4096
    text = "x" * 9000
    result = _split_message(text)
    assert len(result) == 3
    for chunk in result:
        assert len(chunk) <= 4096


def test_three_section_chunks():
    # Build text with 3 ### sections, total > 8192
    section = "### Heading\n" + "a" * 3000 + "\n"
    text = section * 3
    result = _split_message(text)
    assert len(result) == 3


def test_strips_whitespace_from_chunks():
    part1 = "a" * 3000
    part2 = "b" * 2000
    text = part1 + "\n\n" + part2
    result = _split_message(text)
    for chunk in result:
        assert chunk == chunk.strip()


def test_custom_limit():
    text = "abc\n\ndef"
    result = _split_message(text, limit=5)
    for chunk in result:
        assert len(chunk) <= 5


def test_empty_string():
    result = _split_message("")
    assert result == [""]
