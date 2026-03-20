"""Telegram bot: message routing and command handlers."""

import logging

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent import run_agent
from config import save_chat_id
from handlers.todo_manager import list_todos
from handlers.file_manager import get_today_worklog
from handlers.onboarding import get_onboarding_handler
from handlers.weekly_snippet import ask_weekly_questions, generate_weekly_snippet, get_weekly_context

logger = logging.getLogger(__name__)

_history: dict[int, list[dict]] = {}
_weekly_sessions: dict[int, dict] = {}


def build_application(cfg: dict) -> Application:
    """Create and configure the Telegram Application."""
    app = Application.builder().token(cfg["telegram_bot_token"]).build()
    app.bot_data["cfg"] = cfg

    # Onboarding handler owns /start and must be registered first (higher priority)
    app.add_handler(get_onboarding_handler())
    app.add_handler(CommandHandler("todos", _cmd_todos))
    app.add_handler(CommandHandler("log", _cmd_log))
    app.add_handler(CommandHandler("weekly", _cmd_weekly))
    app.add_handler(CommandHandler("help", _cmd_help))
    app.add_handler(CommandHandler("clear", _cmd_clear))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, _on_message))

    return app


# ── Command handlers ──────────────────────────────────────────────────────────

async def _cmd_todos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    todos = list_todos(cfg["brain_path"])
    await update.message.reply_text(f"📋 *Todos*\n\n{todos}", parse_mode="Markdown")


async def _cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    log = get_today_worklog(cfg["brain_path"])
    await update.message.reply_text(f"📓 *Today's Work Log*\n\n{log}", parse_mode="Markdown")


async def _cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🦞 *Lobster Help*\n\n"
        "Just talk to me in plain English! Examples:\n"
        "• \"Add a todo: review pull requests\"\n"
        "• \"Mark todo 2 as done\"\n"
        "• \"Log: spent 2h on API integration\"\n"
        "• \"What's on my calendar today?\"\n"
        "• \"Remember that I prefer dark mode\"\n\n"
        "Commands:\n"
        "  /todos   — list todos\n"
        "  /log     — today's work log\n"
        "  /weekly  — generate weekly Confluence snippet\n"
        "  /clear   — clear conversation history\n"
        "  /help    — this message",
        parse_mode="Markdown",
    )


async def _cmd_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    try:
        worklog, week_range = get_weekly_context(cfg)
        response = await ask_weekly_questions(worklog, cfg)
        if response.strip().upper() == "READY":
            snippet = await generate_weekly_snippet(worklog, "", cfg)
            await update.message.reply_text(f"📋 *Weekly Snippet*\n\n{snippet}", parse_mode="Markdown")
        else:
            _weekly_sessions[chat_id] = {"worklog": worklog, "week_range": week_range}
            await update.message.reply_text(response)
    except Exception as exc:
        logger.exception("Weekly snippet error")
        await update.message.reply_text(f"Sorry, could not generate snippet: {exc}")


async def _cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _history.pop(update.effective_chat.id, None)
    await update.message.reply_text("Conversation history cleared.")


# ── Free-text message handler ─────────────────────────────────────────────────

async def _on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    user_text = update.message.text.strip()

    if not user_text:
        return

    # Persist chat_id if not yet set
    if not cfg.get("telegram_chat_id"):
        chat_id = update.effective_chat.id
        cfg["telegram_chat_id"] = chat_id
        save_chat_id(chat_id)

    # Show typing indicator while processing
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action="typing"
    )

    chat_id = update.effective_chat.id

    if chat_id in _weekly_sessions:
        session = _weekly_sessions.pop(chat_id)
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        try:
            snippet = await generate_weekly_snippet(session["worklog"], user_text, cfg)
            await update.message.reply_text(f"📋 *Weekly Snippet*\n\n{snippet}", parse_mode="Markdown")
        except Exception as exc:
            logger.exception("Weekly snippet error after Q&A")
            await update.message.reply_text(f"Sorry, could not generate snippet: {exc}")
        return

    history = _history.get(chat_id, [])

    try:
        reply, updated_history = await run_agent(user_text, cfg, history)
        _history[chat_id] = updated_history
    except Exception as exc:
        logger.exception("Agent error for message: %s", user_text)
        reply = f"Sorry, something went wrong: {exc}"

    await update.message.reply_text(reply)
