"""One-shot and recurring Telegram reminders scheduled via APScheduler."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

RECURRING_FILE = "recurring_reminders.json"

DAY_ABBREVS = {
    "monday": "mon", "tuesday": "tue", "wednesday": "wed",
    "thursday": "thu", "friday": "fri", "saturday": "sat", "sunday": "sun",
}


# ── Persistence helpers ────────────────────────────────────────────────────────

def _load_jobs(brain_path: str) -> list[dict]:
    p = Path(brain_path).expanduser() / RECURRING_FILE
    try:
        return json.loads(p.read_text()) if p.exists() else []
    except Exception:
        return []


def _save_jobs(brain_path: str, jobs: list[dict]) -> None:
    p = Path(brain_path).expanduser() / RECURRING_FILE
    p.write_text(json.dumps(jobs, indent=2))


# ── Trigger builder ────────────────────────────────────────────────────────────

def _build_trigger(time: str, recurrence: str):
    """Return an APScheduler trigger for the given time (HH:MM) and recurrence."""
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    h, m = map(int, time.split(":"))

    if recurrence == "daily":
        return CronTrigger(hour=h, minute=m)

    if recurrence == "weekdays":
        return CronTrigger(day_of_week="mon-fri", hour=h, minute=m)

    if recurrence.startswith("weekly:"):
        day = recurrence.split(":", 1)[1].lower()
        abbrev = DAY_ABBREVS.get(day, day[:3])
        return CronTrigger(day_of_week=abbrev, hour=h, minute=m)

    if recurrence.startswith("biweekly:"):
        day = recurrence.split(":", 1)[1].lower()
        abbrev = DAY_ABBREVS.get(day, day[:3])
        # Find next occurrence of that weekday at the given time
        now = datetime.now()
        target_dow = list(DAY_ABBREVS.keys()).index(day) if day in DAY_ABBREVS else int(day)
        days_ahead = (target_dow - now.weekday()) % 7
        start = now.replace(hour=h, minute=m, second=0, microsecond=0) + timedelta(days=days_ahead)
        if start <= now:
            start += timedelta(weeks=2)
        return IntervalTrigger(weeks=2, start_date=start)

    if recurrence.startswith("interval:"):
        spec = recurrence.split(":", 1)[1].lower()
        if spec.endswith("w"):
            return IntervalTrigger(weeks=int(spec[:-1]))
        if spec.endswith("d"):
            return IntervalTrigger(days=int(spec[:-1]))

    raise ValueError(f"Unknown recurrence pattern: '{recurrence}'")


# ── One-shot reminder ──────────────────────────────────────────────────────────

def set_reminder(cfg: dict, text: str, remind_at: str) -> str:
    """Schedule a one-shot reminder message."""
    try:
        dt = datetime.fromisoformat(remind_at)
    except ValueError:
        return f"Invalid datetime format: '{remind_at}'. Use ISO 8601, e.g. '2026-03-20T15:00:00'."

    if dt < datetime.now():
        return f"Cannot set a reminder in the past ({remind_at})."

    scheduler = cfg["_scheduler"]
    bot = cfg["_bot"]
    chat_id = cfg["telegram_chat_id"]

    job_id = f"reminder_{int(dt.timestamp())}_{abs(hash(text))}"

    async def _send_reminder():
        await bot.send_message(chat_id=chat_id, text=f"⏰ {text}")

    from apscheduler.triggers.date import DateTrigger

    scheduler.add_job(
        _send_reminder,
        trigger=DateTrigger(run_date=dt),
        id=job_id,
        replace_existing=True,
    )

    formatted = dt.strftime("%A, %B %-d at %-I:%M %p")
    return f"Reminder set for {formatted}: \"{text}\""


# ── Recurring reminders ────────────────────────────────────────────────────────

def set_recurring_reminder(cfg: dict, text: str, time: str, recurrence: str) -> str:
    """Validate, build trigger, add job to scheduler, persist to JSON."""
    # Validate time format
    try:
        parts = time.strip().split(":")
        if len(parts) != 2:
            raise ValueError
        h, m = int(parts[0]), int(parts[1])
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise ValueError
    except ValueError:
        return f"Invalid time format: '{time}'. Use HH:MM (e.g. '09:30')."

    # Validate recurrence
    try:
        trigger = _build_trigger(time, recurrence)
    except ValueError as e:
        return str(e)

    scheduler = cfg["_scheduler"]
    bot = cfg["_bot"]
    chat_id = cfg["telegram_chat_id"]
    brain_path = cfg["brain_path"]

    job_id = f"recurring_{abs(hash(text + time + recurrence))}"

    async def _send():
        await bot.send_message(chat_id=chat_id, text=f"⏰ {text}")

    scheduler.add_job(
        _send,
        trigger=trigger,
        id=job_id,
        name=f"Recurring: {text[:40]}",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    jobs = _load_jobs(brain_path)
    jobs = [j for j in jobs if j["job_id"] != job_id]  # deduplicate
    jobs.append({"job_id": job_id, "text": text, "time": time, "recurrence": recurrence})
    _save_jobs(brain_path, jobs)

    return f"Recurring reminder set ({recurrence} at {time}): \"{text}\" [id: {job_id}]"


def cancel_reminder(cfg: dict, job_id: str) -> str:
    """Remove job from scheduler + JSON file."""
    scheduler = cfg["_scheduler"]
    brain_path = cfg["brain_path"]

    try:
        scheduler.remove_job(job_id)
    except Exception:
        pass  # job may have already expired or been removed

    jobs = _load_jobs(brain_path)
    before = len(jobs)
    jobs = [j for j in jobs if j["job_id"] != job_id]

    if len(jobs) == before:
        return f"No reminder found with id '{job_id}'."

    _save_jobs(brain_path, jobs)
    return f"Reminder '{job_id}' cancelled."


def list_reminders(cfg: dict) -> str:
    """Return formatted list of all recurring reminders from JSON."""
    brain_path = cfg["brain_path"]
    jobs = _load_jobs(brain_path)

    if not jobs:
        return "No recurring reminders set."

    lines = ["Recurring reminders:"]
    for j in jobs:
        lines.append(f"• [{j['job_id']}] {j['recurrence']} at {j['time']}: \"{j['text']}\"")
    return "\n".join(lines)


def load_recurring_reminders(cfg: dict, scheduler) -> None:
    """Called at startup: read JSON, re-add all jobs to scheduler."""
    brain_path = cfg["brain_path"]
    jobs = _load_jobs(brain_path)

    if not jobs:
        return

    bot = cfg["_bot"]
    chat_id = cfg.get("telegram_chat_id")

    for job_def in jobs:
        try:
            trigger = _build_trigger(job_def["time"], job_def["recurrence"])
            text = job_def["text"]

            async def _send(t=text):
                await bot.send_message(chat_id=chat_id, text=f"⏰ {t}")

            scheduler.add_job(
                _send,
                trigger=trigger,
                id=job_def["job_id"],
                name=f"Recurring: {text[:40]}",
                replace_existing=True,
                misfire_grace_time=3600,
            )
            logger.info("Loaded recurring reminder: %s", job_def["job_id"])
        except Exception:
            logger.exception("Failed to reload recurring reminder: %s", job_def.get("job_id"))
