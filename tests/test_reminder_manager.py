"""Tests for handlers/reminder_manager.py"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from handlers.reminder_manager import (
    _build_trigger,
    _load_jobs,
    _save_jobs,
    cancel_reminder,
    list_reminders,
    load_recurring_reminders,
    set_recurring_reminder,
    set_reminder,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_cfg(tmp_path):
    scheduler = MagicMock()
    bot = MagicMock()
    return {
        "brain_path": str(tmp_path),
        "_scheduler": scheduler,
        "_bot": bot,
        "telegram_chat_id": 12345,
    }


# ── _build_trigger ─────────────────────────────────────────────────────────────

def test_build_trigger_daily():
    t = _build_trigger("09:30", "daily")
    assert isinstance(t, CronTrigger)
    fields = {f.name: str(f) for f in t.fields}
    assert fields["hour"] == "9"
    assert fields["minute"] == "30"


def test_build_trigger_weekdays():
    t = _build_trigger("08:00", "weekdays")
    assert isinstance(t, CronTrigger)
    fields = {f.name: str(f) for f in t.fields}
    assert "mon-fri" in fields["day_of_week"]


def test_build_trigger_weekly_monday():
    t = _build_trigger("10:00", "weekly:monday")
    assert isinstance(t, CronTrigger)
    fields = {f.name: str(f) for f in t.fields}
    assert "mon" in fields["day_of_week"]


def test_build_trigger_biweekly():
    t = _build_trigger("09:00", "biweekly:monday")
    assert isinstance(t, IntervalTrigger)


def test_build_trigger_interval_days():
    t = _build_trigger("12:00", "interval:3d")
    assert isinstance(t, IntervalTrigger)


def test_build_trigger_interval_weeks():
    t = _build_trigger("12:00", "interval:2w")
    assert isinstance(t, IntervalTrigger)


def test_build_trigger_invalid():
    with pytest.raises(ValueError, match="Unknown recurrence"):
        _build_trigger("09:00", "monthly")


def test_build_trigger_interval_with_anchor():
    anchor = datetime(2026, 4, 7)
    t = _build_trigger("10:00", "interval:2w", anchor_date=anchor)
    assert isinstance(t, IntervalTrigger)
    assert t.start_date is not None
    assert t.start_date.date() == anchor.date()


def test_build_trigger_biweekly_with_anchor():
    anchor = datetime(2026, 4, 7)  # a Tuesday
    t = _build_trigger("10:00", "biweekly:tuesday", anchor_date=anchor)
    assert isinstance(t, IntervalTrigger)
    assert t.start_date.year == 2026
    assert t.start_date.month == 4
    assert t.start_date.day == 7
    assert t.start_date.hour == 10
    assert t.start_date.minute == 0


def test_build_trigger_daily_with_anchor():
    anchor = datetime(2026, 4, 1)
    t = _build_trigger("09:00", "daily", anchor_date=anchor)
    assert isinstance(t, CronTrigger)
    assert t.start_date is not None
    assert t.start_date.date() == anchor.date()


# ── _load_jobs / _save_jobs ────────────────────────────────────────────────────

def test_load_jobs_missing_file(tmp_path):
    assert _load_jobs(str(tmp_path)) == []


def test_load_jobs_corrupt_file(tmp_path):
    (tmp_path / "recurring_reminders.json").write_text("not json{{{")
    assert _load_jobs(str(tmp_path)) == []


def test_save_and_load_roundtrip(tmp_path):
    jobs = [{"job_id": "recurring_1", "text": "Hi", "time": "09:00", "recurrence": "daily"}]
    _save_jobs(str(tmp_path), jobs)
    loaded = _load_jobs(str(tmp_path))
    assert loaded == jobs


def test_save_overwrites(tmp_path):
    _save_jobs(str(tmp_path), [{"job_id": "a", "text": "old", "time": "08:00", "recurrence": "daily"}])
    _save_jobs(str(tmp_path), [{"job_id": "b", "text": "new", "time": "10:00", "recurrence": "weekdays"}])
    loaded = _load_jobs(str(tmp_path))
    assert len(loaded) == 1
    assert loaded[0]["job_id"] == "b"


# ── set_reminder (one-shot) ────────────────────────────────────────────────────

def test_set_reminder_invalid_format(tmp_path):
    cfg = _make_cfg(tmp_path)
    result = set_reminder(cfg, "Hi", "not-a-date")
    assert "Invalid datetime format" in result


def test_set_reminder_past_date(tmp_path):
    cfg = _make_cfg(tmp_path)
    past = (datetime.now() - timedelta(hours=1)).isoformat()
    result = set_reminder(cfg, "Hi", past)
    assert "past" in result.lower()


def test_set_reminder_valid(tmp_path):
    cfg = _make_cfg(tmp_path)
    future = (datetime.now() + timedelta(hours=2)).isoformat()
    result = set_reminder(cfg, "Call Bob", future)
    assert "Call Bob" in result
    cfg["_scheduler"].add_job.assert_called_once()


# ── set_recurring_reminder ─────────────────────────────────────────────────────

def test_set_recurring_reminder_invalid_time(tmp_path):
    cfg = _make_cfg(tmp_path)
    result = set_recurring_reminder(cfg, "Stand-up", "25:99", "daily")
    assert "Invalid time format" in result


def test_set_recurring_reminder_invalid_recurrence(tmp_path):
    cfg = _make_cfg(tmp_path)
    result = set_recurring_reminder(cfg, "Stand-up", "09:00", "monthly")
    assert "Unknown recurrence" in result


def test_set_recurring_reminder_valid_daily(tmp_path):
    cfg = _make_cfg(tmp_path)
    result = set_recurring_reminder(cfg, "Check Slack", "09:30", "daily")
    assert "Check Slack" in result
    assert "daily" in result
    cfg["_scheduler"].add_job.assert_called_once()


def test_set_recurring_reminder_persists(tmp_path):
    cfg = _make_cfg(tmp_path)
    set_recurring_reminder(cfg, "Stand-up", "10:00", "weekdays")
    jobs = _load_jobs(str(tmp_path))
    assert len(jobs) == 1
    assert jobs[0]["text"] == "Stand-up"
    assert jobs[0]["recurrence"] == "weekdays"


def test_set_recurring_reminder_deduplicates(tmp_path):
    cfg = _make_cfg(tmp_path)
    set_recurring_reminder(cfg, "Stand-up", "10:00", "weekdays")
    set_recurring_reminder(cfg, "Stand-up", "10:00", "weekdays")
    jobs = _load_jobs(str(tmp_path))
    assert len(jobs) == 1


def test_set_recurring_reminder_job_id_in_result(tmp_path):
    cfg = _make_cfg(tmp_path)
    result = set_recurring_reminder(cfg, "Lunch", "12:00", "daily")
    assert "recurring_" in result


def test_set_recurring_reminder_invalid_anchor(tmp_path):
    cfg = _make_cfg(tmp_path)
    result = set_recurring_reminder(cfg, "Newsletter", "10:00", "interval:2w", anchor_date="not-a-date")
    assert "Invalid anchor_date format" in result


def test_set_recurring_reminder_anchor_persisted(tmp_path):
    cfg = _make_cfg(tmp_path)
    set_recurring_reminder(cfg, "Newsletter", "10:00", "interval:2w", anchor_date="2026-04-07")
    jobs = _load_jobs(str(tmp_path))
    assert len(jobs) == 1
    assert jobs[0]["anchor_date"] == "2026-04-07"


def test_set_recurring_reminder_no_anchor_persisted_as_none(tmp_path):
    cfg = _make_cfg(tmp_path)
    set_recurring_reminder(cfg, "Stand-up", "10:00", "weekdays")
    jobs = _load_jobs(str(tmp_path))
    assert jobs[0]["anchor_date"] is None


# ── cancel_reminder ────────────────────────────────────────────────────────────

def test_cancel_reminder_existing(tmp_path):
    cfg = _make_cfg(tmp_path)
    set_recurring_reminder(cfg, "Stand-up", "10:00", "weekdays")
    job_id = _load_jobs(str(tmp_path))[0]["job_id"]

    cfg["_scheduler"].reset_mock()
    result = cancel_reminder(cfg, job_id)

    assert "cancelled" in result.lower()
    assert _load_jobs(str(tmp_path)) == []
    cfg["_scheduler"].remove_job.assert_called_once_with(job_id)


def test_cancel_reminder_nonexistent(tmp_path):
    cfg = _make_cfg(tmp_path)
    # Scheduler raises when job not found — simulate that
    cfg["_scheduler"].remove_job.side_effect = Exception("Job not found")
    result = cancel_reminder(cfg, "recurring_999")
    assert "No reminder found" in result


# ── list_reminders ─────────────────────────────────────────────────────────────

def test_list_reminders_empty(tmp_path):
    cfg = _make_cfg(tmp_path)
    result = list_reminders(cfg)
    assert "No recurring reminders" in result


def test_list_reminders_populated(tmp_path):
    cfg = _make_cfg(tmp_path)
    set_recurring_reminder(cfg, "Stand-up", "10:00", "weekdays")
    set_recurring_reminder(cfg, "Weekly review", "14:00", "weekly:friday")
    result = list_reminders(cfg)
    assert "Stand-up" in result
    assert "Weekly review" in result
    assert "weekdays" in result
    assert "weekly:friday" in result


# ── load_recurring_reminders ───────────────────────────────────────────────────

def test_load_recurring_reminders_empty(tmp_path):
    cfg = _make_cfg(tmp_path)
    scheduler = MagicMock()
    load_recurring_reminders(cfg, scheduler)
    scheduler.add_job.assert_not_called()


def test_load_recurring_reminders_restores_jobs(tmp_path):
    jobs = [
        {"job_id": "recurring_abc", "text": "Check email", "time": "09:00", "recurrence": "daily"},
        {"job_id": "recurring_def", "text": "Stand-up", "time": "10:00", "recurrence": "weekdays"},
    ]
    _save_jobs(str(tmp_path), jobs)

    cfg = _make_cfg(tmp_path)
    scheduler = MagicMock()
    load_recurring_reminders(cfg, scheduler)

    assert scheduler.add_job.call_count == 2
    call_kwargs = [c.kwargs for c in scheduler.add_job.call_args_list]
    ids = {kw["id"] for kw in call_kwargs}
    assert ids == {"recurring_abc", "recurring_def"}


def test_load_recurring_reminders_passes_anchor(tmp_path):
    jobs = [
        {"job_id": "recurring_abc", "text": "Newsletter", "time": "10:00", "recurrence": "interval:2w", "anchor_date": "2026-04-07"},
    ]
    _save_jobs(str(tmp_path), jobs)

    cfg = _make_cfg(tmp_path)
    scheduler = MagicMock()
    load_recurring_reminders(cfg, scheduler)

    assert scheduler.add_job.call_count == 1
    call_kwargs = scheduler.add_job.call_args.kwargs
    trigger = call_kwargs["trigger"]
    assert isinstance(trigger, IntervalTrigger)
    assert trigger.start_date is not None
    assert trigger.start_date.year == 2026
    assert trigger.start_date.month == 4
    assert trigger.start_date.day == 7


def test_load_recurring_reminders_skips_bad_entry(tmp_path):
    jobs = [
        {"job_id": "recurring_ok", "text": "Good job", "time": "09:00", "recurrence": "daily"},
        {"job_id": "recurring_bad", "text": "Bad job", "time": "09:00", "recurrence": "INVALID"},
    ]
    _save_jobs(str(tmp_path), jobs)

    cfg = _make_cfg(tmp_path)
    scheduler = MagicMock()
    load_recurring_reminders(cfg, scheduler)

    # Only the valid job gets added
    assert scheduler.add_job.call_count == 1
