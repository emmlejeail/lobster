"""Tests for handlers/file_manager.py"""
from datetime import date

from handlers.file_manager import (
    append_file,
    append_worklog,
    get_date_range_worklog,
    get_today_worklog,
    read_file,
    update_memory,
    write_file,
)


# ── read_file ──────────────────────────────────────────────────────────────────

def test_read_missing_file(tmp_path):
    assert read_file(str(tmp_path), "missing.md") == ""


def test_read_existing_file(tmp_path):
    (tmp_path / "note.md").write_text("hello", encoding="utf-8")
    assert read_file(str(tmp_path), "note.md") == "hello"


# ── write_file ─────────────────────────────────────────────────────────────────

def test_write_creates_file(tmp_path):
    write_file(str(tmp_path), "new.md", "content")
    assert (tmp_path / "new.md").read_text(encoding="utf-8") == "content"


def test_write_overwrites_file(tmp_path):
    (tmp_path / "f.md").write_text("old", encoding="utf-8")
    write_file(str(tmp_path), "f.md", "new")
    assert (tmp_path / "f.md").read_text(encoding="utf-8") == "new"


# ── append_file ────────────────────────────────────────────────────────────────

def test_append_file_adds_content(tmp_path):
    (tmp_path / "f.md").write_text("line1\n", encoding="utf-8")
    append_file(str(tmp_path), "f.md", "line2")
    assert (tmp_path / "f.md").read_text(encoding="utf-8") == "line1\nline2\n"


def test_append_file_adds_newline_if_missing(tmp_path):
    append_file(str(tmp_path), "f.md", "no newline")
    content = (tmp_path / "f.md").read_text(encoding="utf-8")
    assert content.endswith("\n")


def test_append_file_preserves_existing_newline(tmp_path):
    append_file(str(tmp_path), "f.md", "already\n")
    content = (tmp_path / "f.md").read_text(encoding="utf-8")
    assert content == "already\n"


# ── append_worklog ─────────────────────────────────────────────────────────────

def test_append_worklog_contains_today_and_entry(tmp_path):
    append_worklog(str(tmp_path), "Did some work")
    today = date.today().isoformat()
    content = (tmp_path / "worklog.md").read_text(encoding="utf-8")
    assert today in content
    assert "Did some work" in content


def test_append_worklog_returns_confirmation(tmp_path):
    msg = append_worklog(str(tmp_path), "Did some work")
    assert "Work log entry added" in msg


# ── get_today_worklog ──────────────────────────────────────────────────────────

def test_get_today_worklog_no_entries(tmp_path):
    result = get_today_worklog(str(tmp_path))
    assert result.startswith("No work log entries for")


def test_get_today_worklog_with_entry(tmp_path):
    today = date.today().isoformat()
    (tmp_path / "worklog.md").write_text(f"\n### {today}\nDid X\n", encoding="utf-8")
    result = get_today_worklog(str(tmp_path))
    assert "Did X" in result


def test_get_today_worklog_old_entry_not_returned(tmp_path):
    (tmp_path / "worklog.md").write_text("\n### 2020-01-01\nOld entry\n", encoding="utf-8")
    result = get_today_worklog(str(tmp_path))
    assert "Old entry" not in result


# ── update_memory ──────────────────────────────────────────────────────────────

def test_update_memory_contains_today_and_fact(tmp_path):
    update_memory(str(tmp_path), "user likes cats")
    today = date.today().isoformat()
    content = (tmp_path / "memory.md").read_text(encoding="utf-8")
    assert today in content
    assert "user likes cats" in content


def test_update_memory_returns_confirmation(tmp_path):
    msg = update_memory(str(tmp_path), "any fact")
    assert msg == "Memory updated."


# ── get_date_range_worklog ─────────────────────────────────────────────────────

def test_date_range_empty_file(tmp_path):
    start = date(2026, 3, 1)
    end = date(2026, 3, 31)
    result = get_date_range_worklog(str(tmp_path), start, end)
    assert "No worklog entries for" in result


def test_date_range_single_matching_date(tmp_path):
    (tmp_path / "worklog.md").write_text(
        "\n### 2026-03-10\nFixed the bug\n", encoding="utf-8"
    )
    result = get_date_range_worklog(str(tmp_path), date(2026, 3, 10), date(2026, 3, 10))
    assert "Fixed the bug" in result


def test_date_range_filters_out_of_range(tmp_path):
    (tmp_path / "worklog.md").write_text(
        "\n### 2026-03-09\nBefore range\n"
        "\n### 2026-03-10\nIn range\n"
        "\n### 2026-03-11\nAfter range\n",
        encoding="utf-8",
    )
    result = get_date_range_worklog(str(tmp_path), date(2026, 3, 10), date(2026, 3, 10))
    assert "In range" in result
    assert "Before range" not in result
    assert "After range" not in result


def test_date_range_inclusive_boundaries(tmp_path):
    (tmp_path / "worklog.md").write_text(
        "\n### 2026-03-01\nStart day\n"
        "\n### 2026-03-15\nMiddle day\n"
        "\n### 2026-03-31\nEnd day\n",
        encoding="utf-8",
    )
    result = get_date_range_worklog(str(tmp_path), date(2026, 3, 1), date(2026, 3, 31))
    assert "Start day" in result
    assert "Middle day" in result
    assert "End day" in result


def test_date_range_no_matching_dates(tmp_path):
    (tmp_path / "worklog.md").write_text(
        "\n### 2026-01-01\nOld entry\n", encoding="utf-8"
    )
    result = get_date_range_worklog(str(tmp_path), date(2026, 3, 1), date(2026, 3, 31))
    assert "No worklog entries for" in result


def test_date_range_malformed_header_ignored(tmp_path):
    (tmp_path / "worklog.md").write_text(
        "\n### not-a-date\nBad header\n"
        "\n### 2026-03-10\nValid entry\n",
        encoding="utf-8",
    )
    # Should not crash, and should still return the valid entry
    result = get_date_range_worklog(str(tmp_path), date(2026, 3, 10), date(2026, 3, 10))
    assert "Valid entry" in result
