"""Tests for _week_range in handlers/weekly_snippet.py"""
from datetime import date
from unittest.mock import patch, MagicMock

from handlers.weekly_snippet import _week_range


def _mock_date(iso: str):
    """Return a mock that replaces date.today() with the given ISO date."""
    real_date = date.fromisoformat(iso)
    mock = MagicMock(wraps=date)
    mock.today.return_value = real_date
    # Allow fromisoformat and other class methods to still work
    mock.fromisoformat = date.fromisoformat
    return mock


def test_week_range_on_monday():
    # Monday 2026-03-23 → Monday=March 23, today=March 23
    with patch("handlers.weekly_snippet.date", _mock_date("2026-03-23")):
        result = _week_range()
    assert result == "March 23–23, 2026"


def test_week_range_on_friday():
    # Friday 2026-03-27 → Monday=March 23, today=March 27
    with patch("handlers.weekly_snippet.date", _mock_date("2026-03-27")):
        result = _week_range()
    assert result == "March 23–27, 2026"


def test_week_range_on_sunday():
    # Sunday 2026-03-29 → Monday=March 23, today=March 29
    with patch("handlers.weekly_snippet.date", _mock_date("2026-03-29")):
        result = _week_range()
    assert result == "March 23–29, 2026"


def test_week_range_week_spans_month():
    # Wednesday 2026-04-01 → Monday=March 30, today=April 01
    with patch("handlers.weekly_snippet.date", _mock_date("2026-04-01")):
        result = _week_range()
    assert result == "March 30–01, 2026"
