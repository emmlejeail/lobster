"""Build the LLM system prompt from role.md + memory.md + today's context."""

from datetime import date
from handlers.file_manager import read_file, get_today_worklog
from handlers.todo_manager import list_todos


def build_system_prompt(brain_path: str) -> str:
    today = date.today().strftime("%A, %B %d, %Y")

    role = read_file(brain_path, "role.md").strip()
    memory = read_file(brain_path, "memory.md").strip()
    level_expectations = read_file(brain_path, "level_expectations.md").strip()
    todos = list_todos(brain_path)
    worklog = get_today_worklog(brain_path)

    parts = [
        f"Today is {today}.",
        "",
    ]

    if role:
        parts += [role, ""]

    if memory:
        parts += ["## Long-term Memory", memory, ""]

    if level_expectations:
        parts += ["## Level Expectations", level_expectations, ""]

    parts += [
        "## Current Todos",
        todos,
        "",
        "## Today's Work Log",
        worklog,
        "",
        "## Instructions",
        "- You are a proactive personal AI assistant. Be concise and helpful.",
        "- Use the available tools to read/write files, manage todos, and query the calendar.",
        "- When the user logs work, call append_worklog. When they mention a task, offer to add it.",
        "- Keep memory.md updated with important facts (preferences, decisions, context).",
        "- Format responses for Telegram (plain text or light markdown, no HTML).",
    ]

    return "\n".join(parts)
