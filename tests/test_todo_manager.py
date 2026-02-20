"""Tests for handlers/todo_manager.py"""
from handlers.todo_manager import (
    _parse,
    _render,
    add_todo,
    complete_todo,
    list_todos,
    remove_todo,
)


# ── _render ────────────────────────────────────────────────────────────────────

def test_render_empty():
    assert _render([]) == "# Todos\n\n"


def test_render_single_pending():
    result = _render([{"done": False, "text": "Buy milk"}])
    assert "- [ ] Buy milk" in result


def test_render_single_done():
    result = _render([{"done": True, "text": "Read docs"}])
    assert "- [x] Read docs" in result


def test_render_mixed():
    todos = [{"done": False, "text": "Alpha"}, {"done": True, "text": "Beta"}]
    result = _render(todos)
    assert "- [ ] Alpha" in result
    assert "- [x] Beta" in result


# ── _parse ─────────────────────────────────────────────────────────────────────

def test_parse_missing_file(tmp_path):
    assert _parse(str(tmp_path)) == []


def test_parse_empty_file(tmp_path):
    (tmp_path / "todos.md").write_text("")
    assert _parse(str(tmp_path)) == []


def test_parse_roundtrip(tmp_path):
    (tmp_path / "todos.md").write_text("# Todos\n\n- [ ] Alpha\n- [x] Beta\n")
    todos = _parse(str(tmp_path))
    assert len(todos) == 2
    assert todos[0] == {"done": False, "text": "Alpha"}
    assert todos[1] == {"done": True, "text": "Beta"}


def test_parse_capital_x_done(tmp_path):
    (tmp_path / "todos.md").write_text("- [X] Capital X\n")
    todos = _parse(str(tmp_path))
    assert todos[0]["done"] is True


# ── list_todos ─────────────────────────────────────────────────────────────────

def test_list_todos_empty(tmp_path):
    assert list_todos(str(tmp_path)) == "No todos yet."


def test_list_todos_populated(tmp_path):
    (tmp_path / "todos.md").write_text("- [ ] Alpha\n- [x] Beta\n")
    result = list_todos(str(tmp_path))
    assert "1. ⬜ Alpha" in result
    assert "2. ✅ Beta" in result


# ── add_todo ───────────────────────────────────────────────────────────────────

def test_add_todo_returns_confirmation(tmp_path):
    msg = add_todo(str(tmp_path), "New task")
    assert "New task" in msg


def test_add_todo_persists(tmp_path):
    add_todo(str(tmp_path), "Persist me")
    todos = _parse(str(tmp_path))
    assert any(t["text"] == "Persist me" for t in todos)


def test_add_todo_new_item_is_undone(tmp_path):
    add_todo(str(tmp_path), "Fresh task")
    todos = _parse(str(tmp_path))
    assert todos[-1]["done"] is False


# ── complete_todo ──────────────────────────────────────────────────────────────

def test_complete_todo_valid(tmp_path):
    (tmp_path / "todos.md").write_text("- [ ] Task A\n")
    msg = complete_todo(str(tmp_path), 1)
    assert "done" in msg.lower()
    assert _parse(str(tmp_path))[0]["done"] is True


def test_complete_todo_out_of_range(tmp_path):
    (tmp_path / "todos.md").write_text("- [ ] Task A\n")
    msg = complete_todo(str(tmp_path), 5)
    assert "Invalid" in msg


# ── remove_todo ────────────────────────────────────────────────────────────────

def test_remove_todo_valid(tmp_path):
    (tmp_path / "todos.md").write_text("- [ ] Task A\n- [ ] Task B\n")
    msg = remove_todo(str(tmp_path), 1)
    assert "Task A" in msg
    todos = _parse(str(tmp_path))
    assert len(todos) == 1
    assert todos[0]["text"] == "Task B"


def test_remove_todo_out_of_range(tmp_path):
    (tmp_path / "todos.md").write_text("- [ ] Task A\n")
    msg = remove_todo(str(tmp_path), 99)
    assert "Invalid" in msg
