"""Lobster — Personal AI Assistant daemon entrypoint."""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

from config import load_config
from handlers.telegram_handler import build_application
from scheduler import build_scheduler

# ── Logging setup ─────────────────────────────────────────────────────────────

def _setup_logging(brain_path: str) -> None:
    log_path = Path(brain_path) / "lobster.log"
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

async def main() -> None:
    cfg = load_config()
    _setup_logging(cfg["brain_path"])
    logger = logging.getLogger(__name__)
    logger.info("🦞 Lobster starting up…")

    # Build Telegram application
    tg_app = build_application(cfg)

    # Build scheduler
    scheduler = build_scheduler(cfg)

    # Inject runtime objects so agent tools can access them
    cfg["_scheduler"] = scheduler
    cfg["_bot"] = tg_app.bot

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _handle_signal(*_):
        logger.info("Shutdown signal received.")
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _handle_signal)

    # Start Telegram polling and scheduler
    async with tg_app:
        await tg_app.start()
        scheduler.start()
        logger.info("Lobster is running. Listening for Telegram messages…")

        await tg_app.updater.start_polling(drop_pending_updates=True)

        # Block until shutdown signal
        await stop_event.wait()

        logger.info("Shutting down…")
        await tg_app.updater.stop()
        scheduler.shutdown(wait=False)
        await tg_app.stop()

    logger.info("Lobster stopped. Goodbye.")


if __name__ == "__main__":
    # Ensure we're running from the project directory so relative imports work
    os.chdir(Path(__file__).parent)
    sys.path.insert(0, str(Path(__file__).parent))

    asyncio.run(main())
