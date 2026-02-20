"""APScheduler jobs: morning briefing and evening check-in."""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

from agent import run_agent

logger = logging.getLogger(__name__)


def _parse_hhmm(time_str: str) -> tuple[int, int]:
    """Parse 'HH:MM' into (hour, minute) ints."""
    h, m = time_str.strip().split(":")
    return int(h), int(m)


async def _send_morning_briefing(cfg: dict) -> None:
    """Generate and send the morning briefing via Telegram."""
    chat_id = cfg.get("telegram_chat_id")
    if not chat_id:
        logger.warning("Morning briefing: telegram_chat_id not set, skipping.")
        return

    prompt = (
        "Good morning! Please give me a concise morning briefing:\n"
        "1. Check my calendar for today's events (use get_calendar_events tool)\n"
        "2. List my open todos\n"
        "3. Give me a motivating one-liner to start the day\n"
        "Keep it short and friendly."
    )

    try:
        reply = await run_agent(prompt, cfg)
        bot = Bot(token=cfg["telegram_bot_token"])
        await bot.send_message(chat_id=chat_id, text=f"☀️ *Morning Briefing*\n\n{reply}", parse_mode="Markdown")
        logger.info("Morning briefing sent to chat_id=%s", chat_id)
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
            text=(
                "🌆 *Evening Check-in*\n\n"
                "What did you work on today? "
                "Reply and I'll log it for you."
            ),
            parse_mode="Markdown",
        )
        logger.info("Evening check-in sent to chat_id=%s", chat_id)
    except Exception:
        logger.exception("Failed to send evening check-in")


def build_scheduler(cfg: dict) -> AsyncIOScheduler:
    """Create and configure the APScheduler instance."""
    scheduler = AsyncIOScheduler()

    morning_h, morning_m = _parse_hhmm(cfg.get("morning_briefing_time", "08:00"))
    evening_h, evening_m = _parse_hhmm(cfg.get("evening_checkin_time", "18:00"))

    scheduler.add_job(
        _send_morning_briefing,
        trigger=CronTrigger(hour=morning_h, minute=morning_m),
        args=[cfg],
        id="morning_briefing",
        name="Morning Briefing",
        replace_existing=True,
    )

    scheduler.add_job(
        _send_evening_checkin,
        trigger=CronTrigger(hour=evening_h, minute=evening_m),
        args=[cfg],
        id="evening_checkin",
        name="Evening Check-in",
        replace_existing=True,
    )

    logger.info(
        "Scheduler configured: morning=%02d:%02d, evening=%02d:%02d",
        morning_h, morning_m, evening_h, evening_m,
    )
    return scheduler
