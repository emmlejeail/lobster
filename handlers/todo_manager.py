"""Todo CRUD on ~/lobster-brain/todos.md (checkbox markdown format)."""

import re
from handlers.file_manager import read_file, write_file


_TODO_RE = re.compile(r"^- \[([ xX])\] (.+)$")


def _parse(brain_path: str) -> list[dict]:
    """Return list of {done: bool, text: str} dicts."""
    content = read_file(brain_path, "todos.md")
    todos = []
    for line in content.splitlines():
        m = _TODO_RE.match(line.strip())
        if m:
            todos.append({"done": m.group(1).lower() == "x", "text": m.group(2)})
    return todos


def _render(todos: list[dict]) -> str:
    lines = ["# Todos\n"]
    for t in todos:
        mark = "x" if t["done"] else " "
        lines.append(f"- [{mark}] {t['text']}")
    return "\n".join(lines) + "\n"


def list_todos(brain_path: str) -> str:
    """Return todos.md content as a formatted string."""
    todos = _parse(brain_path)
    if not todos:
        return "No todos yet."
    lines = []
    for i, t in enumerate(todos, 1):
        mark = "✅" if t["done"] else "⬜"
        lines.append(f"{i}. {mark} {t['text']}")
    return "\n".join(lines)


def add_todo(brain_path: str, text: str) -> str:
    """Append a new unchecked todo. Returns confirmation."""
    todos = _parse(brain_path)
    todos.append({"done": False, "text": text.strip()})
    write_file(brain_path, "todos.md", _render(todos))
    return f"Todo added: {text.strip()}"


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
