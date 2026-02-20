"""Tests for handlers/calendar_reader.py — subprocess is always mocked."""
import subprocess
from unittest.mock import MagicMock, patch

from handlers.calendar_reader import get_calendar_events


def _completed(stdout="", returncode=0, stderr=""):
    """Build a mock CompletedProcess-like object."""
    mock = MagicMock()
    mock.stdout = stdout
    mock.returncode = returncode
    mock.stderr = stderr
    return mock


# ── error paths ────────────────────────────────────────────────────────────────

def test_icalbuddy_not_found():
    with patch("handlers.calendar_reader.subprocess.run", side_effect=FileNotFoundError):
        result = get_calendar_events()
    assert "icalBuddy not found" in result


def test_timeout():
    exc = subprocess.TimeoutExpired(cmd="/opt/homebrew/bin/icalBuddy", timeout=15)
    with patch("handlers.calendar_reader.subprocess.run", side_effect=exc):
        result = get_calendar_events()
    assert "timed out" in result.lower()


def test_returncode_nonzero_not_authorized():
    with patch(
        "handlers.calendar_reader.subprocess.run",
        return_value=_completed(returncode=1, stderr="not authorized to access calendar"),
    ):
        result = get_calendar_events()
    assert "Calendar access denied" in result


def test_returncode_nonzero_other_error():
    with patch(
        "handlers.calendar_reader.subprocess.run",
        return_value=_completed(returncode=1, stderr="something went wrong"),
    ):
        result = get_calendar_events()
    assert "icalBuddy error" in result


# ── empty output ───────────────────────────────────────────────────────────────

def test_empty_stdout_today():
    with patch(
        "handlers.calendar_reader.subprocess.run",
        return_value=_completed(stdout=""),
    ):
        result = get_calendar_events(days_ahead=0)
    assert "No calendar events found for" in result


def test_empty_stdout_multi_day():
    with patch(
        "handlers.calendar_reader.subprocess.run",
        return_value=_completed(stdout=""),
    ):
        result = get_calendar_events(days_ahead=3)
    assert "No calendar events found for" in result


# ── valid event parsing ────────────────────────────────────────────────────────

def test_multi_event_stdout():
    stdout = (
        "EVENT:Stand-up (Work)\n"
        "    09:00 - 09:30\n"
        "EVENT:Lunch (Personal)\n"
        "    12:00 - 13:00\n"
    )
    with patch(
        "handlers.calendar_reader.subprocess.run",
        return_value=_completed(stdout=stdout),
    ):
        result = get_calendar_events()
    assert "• [Work] Stand-up  09:00 - 09:30" in result
    assert "• [Personal] Lunch  12:00 - 13:00" in result


def test_all_day_event_no_time_line():
    stdout = "EVENT:Birthday (Personal)\n"
    with patch(
        "handlers.calendar_reader.subprocess.run",
        return_value=_completed(stdout=stdout),
    ):
        result = get_calendar_events()
    assert "• [Personal] Birthday" in result


def test_event_without_calendar_parentheses():
    stdout = "EVENT:Standalone\n    10:00 - 11:00\n"
    with patch(
        "handlers.calendar_reader.subprocess.run",
        return_value=_completed(stdout=stdout),
    ):
        result = get_calendar_events()
    assert "Standalone" in result
    assert "10:00 - 11:00" in result
