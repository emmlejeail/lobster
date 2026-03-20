"""One-shot Telegram reminders scheduled via APScheduler."""

from datetime import datetime


def set_reminder(cfg: dict, text: str, remind_at: str) -> str:
    """Schedule a one-shot reminder message.

    Args:
        cfg: Loaded config dict (must contain _scheduler and _bot).
        text: The reminder message to send.
        remind_at: ISO 8601 datetime string, e.g. '2026-03-20T15:00:00'.

    Returns:
        Human-readable confirmation or error string.
    """
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
