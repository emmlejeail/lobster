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
from handlers.todo_manager import list_todos, get_completed_todos
from handlers.file_manager import get_today_worklog, get_date_range_worklog
from handlers.onboarding import get_onboarding_handler
from handlers.weekly_snippet import ask_weekly_questions, generate_weekly_snippet, get_weekly_context
from handlers.perf_review import ask_perf_review_questions, generate_perf_review, _default_period

logger = logging.getLogger(__name__)

_TELEGRAM_MAX = 4096


def _split_message(text: str, limit: int = _TELEGRAM_MAX) -> list[str]:
    """Split text into chunks that fit within Telegram's message size limit.

    Tries to split on section headers (### ) first, then on double newlines,
    then hard-cuts as a last resort.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    remaining = text
    while len(remaining) > limit:
        # Try to split at a section header before the limit
        cut = remaining.rfind("\n###", 1, limit)
        if cut == -1:
            # Fall back to last double-newline
            cut = remaining.rfind("\n\n", 1, limit)
        if cut == -1:
            cut = limit
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks

_history: dict[int, list[dict]] = {}
_weekly_sessions: dict[int, dict] = {}
# {"worklog": str, "todos": str, "period": str, "answers": list[str], "question_num": int}
_perf_review_sessions: dict[int, dict] = {}


def build_application(cfg: dict) -> Application:
    """Create and configure the Telegram Application."""
    app = Application.builder().token(cfg["telegram_bot_token"]).build()
    app.bot_data["cfg"] = cfg

    # Onboarding handler owns /start and must be registered first (higher priority)
    app.add_handler(get_onboarding_handler())
    app.add_handler(CommandHandler("todos", _cmd_todos))
    app.add_handler(CommandHandler("log", _cmd_log))
    app.add_handler(CommandHandler("weekly", _cmd_weekly))
    app.add_handler(CommandHandler("perfreview", _cmd_perfreview))
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
        "  /todos        — list todos\n"
        "  /log          — today's work log\n"
        "  /weekly       — generate weekly Confluence snippet\n"
        "  /perfreview   — generate self-performance review (last 6 months)\n"
        "  /clear        — clear conversation history\n"
        "  /help         — this message",
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


async def _cmd_perfreview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    cfg = context.bot_data["cfg"]
    chat_id = update.effective_chat.id
    await context.bot.send_chat_action(chat_id=chat_id, action="typing")

    # Optional period arg (e.g. "/perfreview Q1 2026")
    period_arg = " ".join(context.args) if context.args else ""

    try:
        start, end = _default_period()
        period = period_arg if period_arg else f"{start.strftime('%b %Y')}–{end.strftime('%b %Y')}"

        worklog = get_date_range_worklog(cfg["brain_path"], start, end)
        todos = get_completed_todos(cfg["brain_path"])

        question = await ask_perf_review_questions(worklog, todos, 0, "", cfg)

        _perf_review_sessions[chat_id] = {
            "worklog": worklog,
            "todos": todos,
            "period": period,
            "answers": [],
            "question_num": 1,
        }
        await update.message.reply_text(question)
    except Exception as exc:
        logger.exception("Perf review error")
        await update.message.reply_text(f"Sorry, could not start perf review: {exc}")


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

    if chat_id in _perf_review_sessions:
        session = _perf_review_sessions[chat_id]
        session["answers"].append(user_text)
        await context.bot.send_chat_action(chat_id=chat_id, action="typing")
        try:
            if session["question_num"] < 2:
                previous = "\n".join(session["answers"])
                question = await ask_perf_review_questions(
                    session["worklog"], session["todos"],
                    session["question_num"], previous, cfg,
                )
                session["question_num"] += 1
                await update.message.reply_text(question)
            else:
                _perf_review_sessions.pop(chat_id)
                extra_context = "\n".join(session["answers"])
                review = await generate_perf_review(
                    session["worklog"], session["todos"],
                    extra_context, session["period"], cfg,
                )
                chunks = _split_message(f"📄 *Performance Review*\n\n{review}")
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode="Markdown")
        except Exception as exc:
            logger.exception("Perf review error during Q&A")
            _perf_review_sessions.pop(chat_id, None)
            await update.message.reply_text(f"Sorry, could not generate perf review: {exc}")
        return

    history = _history.get(chat_id, [])

    try:
        reply, updated_history = await run_agent(user_text, cfg, history)
        _history[chat_id] = updated_history
    except Exception as exc:
        logger.exception("Agent error for message: %s", user_text)
        reply = f"Sorry, something went wrong: {exc}"

    await update.message.reply_text(reply)
