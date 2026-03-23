"""Todo CRUD on ~/lobster-brain/todos.md (checkbox markdown format)."""

import datetime
import re
from handlers.file_manager import read_file, write_file


_TODO_RE = re.compile(r"^- \[([ xX])\] (.+)$")
_PRIORITY_RE = re.compile(r"\[priority:(high|medium|low)\]", re.IGNORECASE)
_DUE_RE = re.compile(r"\[due:(\d{4}-\d{2}-\d{2})\]")

_PRIORITY_ICON = {"high": "🔴", "medium": "🟡", "low": "🔵"}
_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, None: 3}


def _parse(brain_path: str) -> list[dict]:
    """Return list of {done, text, priority, due} dicts."""
    content = read_file(brain_path, "todos.md")
    todos = []
    for line in content.splitlines():
        m = _TODO_RE.match(line.strip())
        if m:
            raw_text = m.group(2)
            priority_m = _PRIORITY_RE.search(raw_text)
            due_m = _DUE_RE.search(raw_text)
            priority = priority_m.group(1).lower() if priority_m else None
            due = due_m.group(1) if due_m else None
            # Strip structured tags from display text
            text = _PRIORITY_RE.sub("", raw_text)
            text = _DUE_RE.sub("", text).strip()
            todos.append({"done": m.group(1).lower() == "x", "text": text, "priority": priority, "due": due})
    return todos


def _render(todos: list[dict]) -> str:
    lines = ["# Todos\n"]
    for t in todos:
        mark = "x" if t["done"] else " "
        suffix = ""
        if t.get("priority"):
            suffix += f" [priority:{t['priority']}]"
        if t.get("due"):
            suffix += f" [due:{t['due']}]"
        lines.append(f"- [{mark}] {t['text']}{suffix}")
    return "\n".join(lines) + "\n"


def list_todos(brain_path: str) -> str:
    """Return todos.md content as a formatted string."""
    todos = _parse(brain_path)
    if not todos:
        return "No todos yet."
    today = datetime.date.today().isoformat()
    lines = []
    for i, t in enumerate(todos, 1):
        mark = "✅" if t["done"] else "⬜"
        icon = _PRIORITY_ICON.get(t.get("priority"), "  ") if t.get("priority") else "  "
        parts = [f"{i}. {mark} {icon} {t['text']}".rstrip()]
        if t.get("due"):
            overdue = t["due"] < today and not t["done"]
            due_str = f" — due {t['due']}"
            if overdue:
                due_str += " ⚠️ OVERDUE"
            parts[0] += due_str
        lines.append(parts[0])
    return "\n".join(lines)


def add_todo(brain_path: str, text: str, priority: str | None = None, due_date: str | None = None) -> str:
    """Append a new unchecked todo. Returns confirmation."""
    todos = _parse(brain_path)
    todos.append({"done": False, "text": text.strip(), "priority": priority, "due": due_date})
    write_file(brain_path, "todos.md", _render(todos))
    return f"Todo added: {text.strip()}"


def update_todo(brain_path: str, index: int, priority: str | None = None, due_date: str | None = None) -> str:
    """Update priority and/or due date of a todo at 1-based index."""
    todos = _parse(brain_path)
    if index < 1 or index > len(todos):
        return f"Invalid todo index {index}. There are {len(todos)} todos."
    if priority is not None:
        todos[index - 1]["priority"] = priority
    if due_date is not None:
        todos[index - 1]["due"] = due_date
    write_file(brain_path, "todos.md", _render(todos))
    return f"Todo {index} updated: {todos[index - 1]['text']}"


def complete_todo(brain_path: str, index: int) -> str:
    """Mark todo at 1-based index as done. Returns confirmation."""
    todos = _parse(brain_path)
    if index < 1 or index > len(todos):
        return f"Invalid todo index {index}. There are {len(todos)} todos."
    todos[index - 1]["done"] = True
    write_file(brain_path, "todos.md", _render(todos))
    return f"Todo {index} marked as done: {todos[index - 1]['text']}"


def remove_todo(brain_path: str, index: int) -> str:
    """Remove todo at 1-based index. Returns confirmation."""
    todos = _parse(brain_path)
    if index < 1 or index > len(todos):
        return f"Invalid todo index {index}. There are {len(todos)} todos."
    removed = todos.pop(index - 1)
    write_file(brain_path, "todos.md", _render(todos))
    return f"Todo removed: {removed['text']}"


def get_pending_sorted(brain_path: str) -> list[dict]:
    """Return pending todos sorted by urgency.

    Order:
      1. Overdue (due < today), by priority then date
      2. Due today
      3. Due within 7 days, by date then priority
      4. No due date, by priority
      5. Future beyond 7 days
    """
    today = datetime.date.today()
    today_str = today.isoformat()
    week_str = (today + datetime.timedelta(days=7)).isoformat()

    pending = [t for t in _parse(brain_path) if not t["done"]]

    def sort_key(t):
        due = t.get("due")
        p = _PRIORITY_ORDER.get(t.get("priority"), 3)
        if due and due < today_str:
            return (0, p, due)
        if due == today_str:
            return (1, p, due)
        if due and due <= week_str:
            return (2, due, p)
        if not due:
            return (3, p, "")
        return (4, due, p)

    return sorted(pending, key=sort_key)
