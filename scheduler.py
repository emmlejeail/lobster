"""APScheduler jobs: morning briefing and evening check-in."""

import datetime
import json
import logging
import os
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import telegram
from telegram import Bot

from agent import run_agent
from handlers.weekly_snippet import generate_weekly_snippet

logger = logging.getLogger(__name__)

TG_MAX = 4096  # Telegram hard limit per message


async def _send_tg(bot: Bot, chat_id: int | str, text: str, parse_mode: str | None = None) -> None:
    """Send *text* to *chat_id*, splitting into ≤4096-char chunks if needed."""
    chunks = [text[i : i + TG_MAX] for i in range(0, len(text), TG_MAX)]
    for chunk in chunks:
        await bot.send_message(chat_id=chat_id, text=chunk, parse_mode=parse_mode)


def _get_local_timezone(cfg: dict):
    """Detect local timezone as a ZoneInfo object.

    Priority:
    1. ``timezone`` key in config (explicit IANA name)
    2. macOS ``/etc/localtime`` symlink
    3. UTC fallback with a warning
    """
    tz_name = cfg.get("timezone")
    if tz_name:
        return ZoneInfo(tz_name)
    try:
        link = os.readlink("/etc/localtime")  # e.g. /var/db/timezone/zoneinfo/Europe/Paris
        tz_name = link.split("zoneinfo/")[-1]
        return ZoneInfo(tz_name)
    except Exception:
        logger.warning("Could not detect local timezone; falling back to UTC")
        return datetime.timezone.utc


def _parse_hhmm(time_str: str) -> tuple[int, int]:
    """Parse 'HH:MM' into (hour, minute) ints."""
    h, m = time_str.strip().split(":")
    return int(h), int(m)


def _state_path(cfg: dict) -> Path:
    return Path(cfg["brain_path"]).expanduser() / ".scheduler_state.json"


def _load_state(cfg: dict) -> dict:
    p = _state_path(cfg)
    try:
        return json.loads(p.read_text()) if p.exists() else {}
    except Exception:
        return {}


def _mark_job_done(cfg: dict, job_id: str) -> None:
    state = _load_state(cfg)
    state[job_id] = datetime.date.today().isoformat()
    try:
        _state_path(cfg).write_text(json.dumps(state))
    except Exception:
        logger.warning("Could not write scheduler state")


async def _send_morning_briefing(cfg: dict) -> None:
    """Generate and send the morning briefing via Telegram."""
    chat_id = cfg.get("telegram_chat_id")
    if not chat_id:
        logger.warning("Morning briefing: telegram_chat_id not set, skipping.")
        return

    today = datetime.date.today().isoformat()
    prompt = (
        f"Good morning! Today is {today}. Give me a brief morning briefing in 3 short sections — "
        "aim for 150 words total, never exceed 200:\n"
        "1. Today's calendar events (use get_calendar_events tool) — bullet list, one line each\n"
        "2. Todos — use list_todos tool, then highlight: overdue items first (mark ⚠️), "
        "then due today, then due this week. Skip future/no-deadline todos if the list is long. "
        "One line each, include due date and priority if set.\n"
        "3. One motivating sentence to start the day\n"
        "Be concise. No intro, no outro."
    )

    try:
        reply, _ = await run_agent(prompt, cfg)
        bot = Bot(token=cfg["telegram_bot_token"])
        await bot.send_message(chat_id=chat_id, text="☀️ *Morning Briefing*", parse_mode="Markdown")
        await _send_tg(bot, chat_id, reply)
        logger.info("Morning briefing sent to chat_id=%s", chat_id)
        _mark_job_done(cfg, "morning_briefing")
    except Exception:
        logger.exception("Failed to send morning briefing")


async def _send_evening_checkin(cfg: dict) -> None:
    """Send the evening check-in prompt via Telegram."""
    chat_id = cfg.get("telegram_chat_id")
    if not chat_id:
        logger.warning("Evening check-in: telegram_chat_id not set, skipping.")
        return

    try:
        bot = Bot(token=cfg["telegram_bot_token"])
        await bot.send_message(
            chat_id=chat_id,
            text="🌆 *Evening Check-in*\n\nWhat did you work on today? Reply and I'll log it for you.",
            parse_mode="Markdown",
        )
        logger.info("Evening check-in sent to chat_id=%s", chat_id)
        _mark_job_done(cfg, "evening_checkin")
    except Exception:
        logger.exception("Failed to send evening check-in")


async def _send_weekly_snippet(cfg: dict) -> None:
    """Generate and send the weekly Confluence snippet via Telegram."""
    chat_id = cfg.get("telegram_chat_id")
    if not chat_id:
        logger.warning("Weekly snippet: telegram_chat_id not set, skipping.")
        return

    try:
        from handlers.weekly_snippet import get_weekly_context
        worklog, _ = get_weekly_context(cfg)
        snippet = await generate_weekly_snippet(worklog, "", cfg)
        bot = Bot(token=cfg["telegram_bot_token"])
        await bot.send_message(chat_id=chat_id, text="📋 *Weekly Snippet*", parse_mode="Markdown")
        await _send_tg(bot, chat_id, snippet)
        logger.info("Weekly snippet sent to chat_id=%s", chat_id)
    except Exception:
        logger.exception("Failed to send weekly snippet")


CATCHUP_HOURS = 4  # fire up to this many hours after scheduled time


async def _check_missed_jobs(cfg: dict) -> None:
    """Run at startup and every 5 min; fires any job missed today within its catch-up window."""
    local_tz = _get_local_timezone(cfg)
    now = datetime.datetime.now(local_tz)
    today = now.date().isoformat()
    state = _load_state(cfg)

    morning_h, morning_m = _parse_hhmm(cfg.get("morning_briefing_time", "09:00"))
    evening_h, evening_m = _parse_hhmm(cfg.get("evening_checkin_time", "18:00"))

    checks = [
        ("morning_briefing", morning_h, morning_m, _send_morning_briefing),
        ("evening_checkin",  evening_h, evening_m,  _send_evening_checkin),
    ]
    for job_id, h, m, fn in checks:
        if state.get(job_id) == today:
            continue  # already sent today
        scheduled = now.replace(hour=h, minute=m, second=0, microsecond=0)
        cutoff = scheduled + datetime.timedelta(hours=CATCHUP_HOURS)
        if scheduled <= now <= cutoff:
            logger.info("Catch-up: firing %s (missed, still within window)", job_id)
            await fn(cfg)


def build_scheduler(cfg: dict) -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    local_tz = _get_local_timezone(cfg)
    scheduler = AsyncIOScheduler(timezone=local_tz)

    morning_h, morning_m = _parse_hhmm(cfg.get("morning_briefing_time", "08:00"))
    evening_h, evening_m = _parse_hhmm(cfg.get("evening_checkin_time", "18:00"))

    scheduler.add_job(
        _send_morning_briefing,
        trigger=CronTrigger(hour=morning_h, minute=morning_m),
        args=[cfg],
        id="morning_briefing",
        name="Morning Briefing",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        _send_evening_checkin,
        trigger=CronTrigger(hour=evening_h, minute=evening_m),
        args=[cfg],
        id="evening_checkin",
        name="Evening Check-in",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.add_job(
        _check_missed_jobs,
        trigger="interval",
        minutes=5,
        args=[cfg],
        id="catchup_check",
        name="Catch-up check",
        next_run_time=datetime.datetime.now(local_tz),
        replace_existing=True,
    )

    from handlers.reminder_manager import load_recurring_reminders
    load_recurring_reminders(cfg, scheduler)

    _DAY_MAP = {
        "monday": "mon", "tuesday": "tue", "wednesday": "wed", "thursday": "thu",
        "friday": "fri", "saturday": "sat", "sunday": "sun",
    }
    snippet_day = cfg.get("weekly_snippet_day")
    if snippet_day:
        dow = _DAY_MAP.get(snippet_day.lower(), snippet_day.lower()[:3])
        snippet_h, snippet_m = _parse_hhmm(cfg.get("weekly_snippet_time", "17:00"))
        scheduler.add_job(
            _send_weekly_snippet,
            trigger=CronTrigger(day_of_week=dow, hour=snippet_h, minute=snippet_m),
            args=[cfg],
            id="weekly_snippet",
            name="Weekly Confluence Snippet",
            replace_existing=True,
            misfire_grace_time=3600,
        )
        logger.info(
            "Weekly snippet scheduled: %s at %02d:%02d", snippet_day, snippet_h, snippet_m
        )

    logger.info(
        "Scheduler configured: morning=%02d:%02d, evening=%02d:%02d (timezone=%s)",
        morning_h, morning_m, evening_h, evening_m, local_tz,
    )
    return scheduler
