"""First-run onboarding: collects user info and writes brain files."""

import logging
from datetime import date
from pathlib import Path

from telegram import Update
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import save_chat_id
from handlers.file_manager import write_file, append_file

logger = logging.getLogger(__name__)

# Conversation states
ASKING_NAME, ASKING_OCCUPATION, ASKING_STYLE, ASKING_EXTRA = range(4)

_GREETING = (
    "Hi! I'm Lobster, your personal AI assistant.\n\n"
    "Commands:\n"
    "  /todos — show current todos\n"
    "  /log   — show today's work log\n"
    "  /help  — show this message\n\n"
    "Just send me a message to get started!"
)


# ── Marker helpers ────────────────────────────────────────────────────────────

def is_onboarded(brain_path: str) -> bool:
    return Path(brain_path).joinpath(".onboarded").exists()


def mark_onboarded(brain_path: str) -> None:
    Path(brain_path).joinpath(".onboarded").touch()


# ── Conversation callbacks ────────────────────────────────────────────────────

async def _onboarding_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cfg = context.bot_data["cfg"]
    chat_id = update.effective_chat.id

    # Persist chat_id on first contact
    if not cfg.get("telegram_chat_id"):
        cfg["telegram_chat_id"] = chat_id
        save_chat_id(chat_id)
        logger.info("Saved telegram_chat_id=%s", chat_id)

    if is_onboarded(cfg["brain_path"]):
        await update.message.reply_text(_GREETING)
        return ConversationHandler.END

    await update.message.reply_text(
        "Welcome! I'm Lobster, your personal AI assistant.\n\n"
        "Let's get you set up in a few quick questions.\n\n"
        "What's your name?"
    )
    return ASKING_NAME


async def _got_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["name"] = update.message.text.strip()
    await update.message.reply_text(
        "What do you do for work? "
        "(e.g. 'software engineer at Acme', 'indie hacker')"
    )
    return ASKING_OCCUPATION


async def _got_occupation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["occupation"] = update.message.text.strip()
    await update.message.reply_text(
        "How should I communicate with you? "
        "(e.g. 'brief and direct', 'casual, use bullet points')"
    )
    return ASKING_STYLE


async def _got_style(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["style"] = update.message.text.strip()
    await update.message.reply_text(
        "Anything else I should know? "
        "(timezone, key projects, goals…)\n\nSend /skip to skip."
    )
    return ASKING_EXTRA


async def _got_extra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # /skip command arrives as update.message.text == "/skip"
    text = update.message.text.strip()
    context.user_data["extra"] = None if text == "/skip" else text
    return await _finish_onboarding(update, context)


async def _cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Onboarding cancelled. Send /start whenever you're ready."
    )
    return ConversationHandler.END


# ── Finish: write files and confirm ──────────────────────────────────────────

async def _finish_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cfg = context.bot_data["cfg"]
    brain_path = cfg["brain_path"]
    today = date.today().isoformat()

    name = context.user_data["name"]
    occupation = context.user_data["occupation"]
    style = context.user_data["style"]
    extra = context.user_data.get("extra")

    # Write role.md
    role_content = (
        f"# {name}'s Personal AI Assistant\n\n"
        f"## About\n"
        f"{name} is a {occupation}.\n\n"
        f"## Communication Style\n"
        f"{style}\n\n"
        f"## Instructions\n"
        f"- You are a proactive personal AI assistant for {name}.\n"
        f"- Be concise and helpful. Communicate in the style described above.\n"
        f"- Use the available tools to manage todos, work log, calendar, and memory.\n"
        f"- Format responses for Telegram (plain text or light markdown, no HTML).\n"
    )
    write_file(brain_path, "role.md", role_content)

    # Append facts to memory.md
    facts = (
        f"\n- [{today}] Name: {name}\n"
        f"- [{today}] Occupation: {occupation}\n"
        f"- [{today}] Communication style: {style}\n"
    )
    if extra:
        facts += f"- [{today}] Extra context: {extra}\n"
    append_file(brain_path, "memory.md", facts)

    mark_onboarded(brain_path)
    logger.info("Onboarding complete for user '%s'", name)

    summary = (
        f"All set, {name}!\n\n"
        f"Here's what I've saved:\n"
        f"• Name: {name}\n"
        f"• Occupation: {occupation}\n"
        f"• Style: {style}\n"
    )
    if extra:
        summary += f"• Extra: {extra}\n"
    summary += "\nJust send me a message to get started!"

    await update.message.reply_text(summary)
    return ConversationHandler.END


# ── Public factory ────────────────────────────────────────────────────────────

def get_onboarding_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", _onboarding_start)],
        states={
            ASKING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, _got_name)],
            ASKING_OCCUPATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, _got_occupation)],
            ASKING_STYLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, _got_style)],
            ASKING_EXTRA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, _got_extra),
                CommandHandler("skip", _got_extra),
            ],
        },
        fallbacks=[CommandHandler("cancel", _cancel)],
    )
