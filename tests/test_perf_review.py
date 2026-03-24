"""Tests for _truncate_worklog in handlers/perf_review.py"""
from handlers.perf_review import _truncate_worklog

_MARKER = "[earlier entries omitted]"


def test_short_worklog_unchanged():
    worklog = "### 2026-03-01\nDid stuff\n"
    assert _truncate_worklog(worklog) == worklog


def test_at_limit_unchanged():
    worklog = "x" * 12000
    assert _truncate_worklog(worklog) == worklog


def test_truncation_prepends_marker():
    worklog = "x" * 13000
    result = _truncate_worklog(worklog)
    assert result.startswith(_MARKER)


def test_truncated_length():
    worklog = "x" * 13000
    result = _truncate_worklog(worklog)
    assert len(result) <= 12000 + len(_MARKER) + 2  # +2 for "\n\n"


def test_trims_to_first_double_newline():
    # The tail after slicing at -12000 starts with a partial line, then \n\n then a real entry
    filler = "partial-line-garbage"
    real_entry = "### 2026-01-10\nReal entry"
    # Build so the tail at -12000 starts mid-entry then has a \n\n before the real entry
    padding = "x" * (12000 - len("\n\n" + real_entry) - len(filler))
    worklog = "y" * 2000 + filler + "\n\n" + real_entry + padding
    # Ensure total > 12000
    assert len(worklog) > 12000
    result = _truncate_worklog(worklog)
    assert "Real entry" in result
    # Should not contain the partial garbage line before the double-newline
    assert not result.lstrip(_MARKER).lstrip("\n").startswith(filler)


def test_no_double_newline_takes_raw_tail():
    worklog = "x" * 15000
    result = _truncate_worklog(worklog)
    # No \n\n in tail, so raw tail is used
    assert result == _MARKER + "\n\n" + worklog[-12000:]


def test_custom_limit():
    worklog = "x" * 50
    result = _truncate_worklog(worklog, limit=20)
    assert result.startswith(_MARKER)
    # Result length <= limit + marker overhead
    assert len(result) <= 20 + len(_MARKER) + 2
