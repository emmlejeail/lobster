"""Lobster MCP server — exposes personal brain tools to Claude Code."""

from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP

from handlers import calendar_reader, file_manager, todo_manager

# Load brain_path from config.yaml directly (no API key validation needed)
_CONFIG_PATH = Path(__file__).parent / "config.yaml"
with open(_CONFIG_PATH) as _f:
    _cfg = yaml.safe_load(_f)
brain_path = str(Path(_cfg.get("brain_path", "~/lobster-brain")).expanduser())

mcp = FastMCP("lobster")


@mcp.tool()
def list_todos() -> str:
    """Return the current todo list from todos.md."""
    return todo_manager.list_todos(brain_path)


@mcp.tool()
def add_todo(text: str, priority: str | None = None, due_date: str | None = None) -> str:
    """Add a new todo item.

    Args:
        text: The todo item text.
        priority: Optional priority level — 'high', 'medium', or 'low'.
        due_date: Optional due date in YYYY-MM-DD format.
    """
    return todo_manager.add_todo(brain_path, text, priority, due_date)


@mcp.tool()
def update_todo(index: int, priority: str | None = None, due_date: str | None = None) -> str:
    """Update the priority and/or due date of a todo by its 1-based index.

    Args:
        index: 1-based index of the todo to update.
        priority: New priority level — 'high', 'medium', or 'low'.
        due_date: New due date in YYYY-MM-DD format.
    """
    return todo_manager.update_todo(brain_path, index, priority, due_date)


@mcp.tool()
def complete_todo(index: int) -> str:
    """Mark a todo item as done by its 1-based index.

    Args:
        index: 1-based index of the todo to complete.
    """
    return todo_manager.complete_todo(brain_path, index)


@mcp.tool()
def remove_todo(index: int) -> str:
    """Remove a todo item by its 1-based index.

    Args:
        index: 1-based index of the todo to remove.
    """
    return todo_manager.remove_todo(brain_path, index)


@mcp.tool()
def append_worklog(entry: str) -> str:
    """Append a new dated entry to the work log (worklog.md).

    Args:
        entry: The work log entry text.
    """
    return file_manager.append_worklog(brain_path, entry)


@mcp.tool()
def update_memory(fact: str) -> str:
    """Append a new fact to memory.md.

    Args:
        fact: The fact or note to remember.
    """
    return file_manager.update_memory(brain_path, fact)


@mcp.tool()
def get_calendar_events(days_ahead: int = 0) -> str:
    """Fetch macOS Calendar events via icalBuddy.

    Args:
        days_ahead: 0 = today only; N > 0 = today through N days ahead.
    """
    return calendar_reader.get_calendar_events(days_ahead)


if __name__ == "__main__":
    mcp.run()
