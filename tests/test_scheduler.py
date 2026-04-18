"""Tests for scheduler.py — weekday-only briefing/check-in behaviour."""

import asyncio
import datetime
from unittest.mock import AsyncMock, patch

from apscheduler.triggers.cron import CronTrigger

from scheduler import _check_missed_jobs, build_scheduler


def _make_cfg(tmp_path):
    return {
        "brain_path": str(tmp_path),
        "timezone": "UTC",
        "morning_briefing_time": "09:00",
        "evening_checkin_time": "18:00",
    }


# ── build_scheduler: weekday-only cron triggers ───────────────────────────────

def test_morning_briefing_runs_only_on_weekdays(tmp_path):
    sched = build_scheduler(_make_cfg(tmp_path))
    trigger = sched.get_job("morning_briefing").trigger
    assert isinstance(trigger, CronTrigger)
    fields = {f.name: str(f) for f in trigger.fields}
    assert "mon-fri" in fields["day_of_week"]


def test_evening_checkin_runs_only_on_weekdays(tmp_path):
    sched = build_scheduler(_make_cfg(tmp_path))
    trigger = sched.get_job("evening_checkin").trigger
    assert isinstance(trigger, CronTrigger)
    fields = {f.name: str(f) for f in trigger.fields}
    assert "mon-fri" in fields["day_of_week"]


# ── _check_missed_jobs: weekend short-circuit ────────────────────────────────

_UTC = datetime.timezone.utc
_SATURDAY = datetime.datetime(2026, 4, 18, 10, 0, tzinfo=_UTC)
_SUNDAY = datetime.datetime(2026, 4, 19, 10, 0, tzinfo=_UTC)
_MONDAY_10H = datetime.datetime(2026, 4, 20, 10, 0, tzinfo=_UTC)


def _run_check_at(now, cfg):
    """Run _check_missed_jobs with a frozen `now` and mocked job fns. Returns (morning, evening) mocks."""
    morning = AsyncMock()
    evening = AsyncMock()
    with patch("scheduler.datetime.datetime") as mock_dt, \
         patch("scheduler._send_morning_briefing", morning), \
         patch("scheduler._send_evening_checkin", evening):
        mock_dt.now.return_value = now
        asyncio.run(_check_missed_jobs(cfg))
    return morning, evening


def test_check_missed_jobs_skips_saturday(tmp_path):
    morning, evening = _run_check_at(_SATURDAY, _make_cfg(tmp_path))
    morning.assert_not_called()
    evening.assert_not_called()


def test_check_missed_jobs_skips_sunday(tmp_path):
    morning, evening = _run_check_at(_SUNDAY, _make_cfg(tmp_path))
    morning.assert_not_called()
    evening.assert_not_called()


def test_check_missed_jobs_fires_on_weekday_within_window(tmp_path):
    # Monday 10:00 UTC — within the 4h catch-up window for the 09:00 briefing,
    # but before the 18:00 evening check-in.
    morning, evening = _run_check_at(_MONDAY_10H, _make_cfg(tmp_path))
    morning.assert_awaited_once()
    evening.assert_not_called()
