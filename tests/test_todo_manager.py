"""Tests for handlers/todo_manager.py"""
import datetime
from handlers.todo_manager import (
    _parse,
    _render,
    add_todo,
    complete_todo,
    get_completed_todos,
    get_pending_sorted,
    list_todos,
    remove_todo,
    update_todo,
)


# ── _render ────────────────────────────────────────────────────────────────────

def test_render_empty():
    assert _render([]) == "# Todos\n\n"


def test_render_single_pending():
    result = _render([{"done": False, "text": "Buy milk", "priority": None, "due": None}])
    assert "- [ ] Buy milk" in result


def test_render_single_done():
    result = _render([{"done": True, "text": "Read docs", "priority": None, "due": None}])
    assert "- [x] Read docs" in result


def test_render_mixed():
    todos = [
        {"done": False, "text": "Alpha", "priority": None, "due": None},
        {"done": True, "text": "Beta", "priority": None, "due": None},
    ]
    result = _render(todos)
    assert "- [ ] Alpha" in result
    assert "- [x] Beta" in result


def test_render_with_priority_and_due():
    todos = [{"done": False, "text": "Deploy", "priority": "high", "due": "2026-03-25"}]
    result = _render(todos)
    assert "[priority:high]" in result
    assert "[due:2026-03-25]" in result


def test_render_priority_only():
    todos = [{"done": False, "text": "Deploy", "priority": "low", "due": None}]
    result = _render(todos)
    assert "[priority:low]" in result
    assert "[due:" not in result


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
    assert todos[0] == {"done": False, "text": "Alpha", "priority": None, "due": None}
    assert todos[1] == {"done": True, "text": "Beta", "priority": None, "due": None}


def test_parse_capital_x_done(tmp_path):
    (tmp_path / "todos.md").write_text("- [X] Capital X\n")
    todos = _parse(str(tmp_path))
    assert todos[0]["done"] is True


def test_parse_priority_and_due(tmp_path):
    (tmp_path / "todos.md").write_text(
        "- [ ] Review PRs [priority:high] [due:2026-03-25]\n"
    )
    todos = _parse(str(tmp_path))
    assert todos[0]["text"] == "Review PRs"
    assert todos[0]["priority"] == "high"
    assert todos[0]["due"] == "2026-03-25"


def test_parse_preserves_freeform_brackets(tmp_path):
    (tmp_path / "todos.md").write_text(
        "- [ ] Review [AI Guard] module [priority:medium]\n"
    )
    todos = _parse(str(tmp_path))
    assert "[AI Guard]" in todos[0]["text"]
    assert todos[0]["priority"] == "medium"


def test_parse_no_tags(tmp_path):
    (tmp_path / "todos.md").write_text("- [ ] Just a plain todo\n")
    todos = _parse(str(tmp_path))
    assert todos[0] == {"done": False, "text": "Just a plain todo", "priority": None, "due": None}


# ── list_todos ─────────────────────────────────────────────────────────────────

def test_list_todos_empty(tmp_path):
    assert list_todos(str(tmp_path)) == "No todos yet."


def test_list_todos_populated(tmp_path):
    (tmp_path / "todos.md").write_text("- [ ] Alpha\n- [x] Beta\n")
    result = list_todos(str(tmp_path))
    assert "1. ⬜" in result
    assert "Alpha" in result
    assert "2. ✅" in result
    assert "Beta" in result


def test_list_todos_priority_icon(tmp_path):
    (tmp_path / "todos.md").write_text(
        "- [ ] High task [priority:high]\n"
        "- [ ] Med task [priority:medium]\n"
        "- [ ] Low task [priority:low]\n"
    )
    result = list_todos(str(tmp_path))
    assert "🔴" in result
    assert "🟡" in result
    assert "🔵" in result


def test_list_todos_overdue_marker(tmp_path):
    past = "2020-01-01"
    (tmp_path / "todos.md").write_text(f"- [ ] Old task [due:{past}]\n")
    result = list_todos(str(tmp_path))
    assert "⚠️ OVERDUE" in result


def test_list_todos_no_overdue_for_done(tmp_path):
    past = "2020-01-01"
    (tmp_path / "todos.md").write_text(f"- [x] Old done task [due:{past}]\n")
    result = list_todos(str(tmp_path))
    assert "⚠️ OVERDUE" not in result


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


def test_add_todo_with_priority_and_due(tmp_path):
    add_todo(str(tmp_path), "Deploy", priority="high", due_date="2026-03-25")
    todos = _parse(str(tmp_path))
    assert todos[-1]["priority"] == "high"
    assert todos[-1]["due"] == "2026-03-25"


# ── update_todo ────────────────────────────────────────────────────────────────

def test_update_todo_priority(tmp_path):
    (tmp_path / "todos.md").write_text("- [ ] Task A\n")
    msg = update_todo(str(tmp_path), 1, priority="low")
    assert "updated" in msg.lower()
    assert _parse(str(tmp_path))[0]["priority"] == "low"


def test_update_todo_due_date(tmp_path):
    (tmp_path / "todos.md").write_text("- [ ] Task A\n")
    update_todo(str(tmp_path), 1, due_date="2026-04-01")
    assert _parse(str(tmp_path))[0]["due"] == "2026-04-01"


def test_update_todo_out_of_range(tmp_path):
    (tmp_path / "todos.md").write_text("- [ ] Task A\n")
    msg = update_todo(str(tmp_path), 99)
    assert "Invalid" in msg


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


# ── get_pending_sorted ─────────────────────────────────────────────────────────

def test_get_pending_sorted_overdue_first(tmp_path):
    today = datetime.date.today().isoformat()
    past = "2020-01-01"
    future = "2099-12-31"
    (tmp_path / "todos.md").write_text(
        f"- [ ] Future [due:{future}]\n"
        f"- [ ] Overdue [due:{past}] [priority:low]\n"
        f"- [ ] Today [due:{today}]\n"
    )
    sorted_todos = get_pending_sorted(str(tmp_path))
    assert sorted_todos[0]["text"] == "Overdue"
    assert sorted_todos[1]["text"] == "Today"
    assert sorted_todos[-1]["text"] == "Future"


def test_get_pending_sorted_excludes_done(tmp_path):
    (tmp_path / "todos.md").write_text(
        "- [x] Done task\n"
        "- [ ] Pending task\n"
    )
    sorted_todos = get_pending_sorted(str(tmp_path))
    assert len(sorted_todos) == 1
    assert sorted_todos[0]["text"] == "Pending task"


def test_get_pending_sorted_no_due_by_priority(tmp_path):
    (tmp_path / "todos.md").write_text(
        "- [ ] Low task [priority:low]\n"
        "- [ ] High task [priority:high]\n"
        "- [ ] No priority\n"
    )
    sorted_todos = get_pending_sorted(str(tmp_path))
    # All no-due, so ordered by priority: high < low < None
    assert sorted_todos[0]["text"] == "High task"
    assert sorted_todos[1]["text"] == "Low task"
    assert sorted_todos[2]["text"] == "No priority"


# ── get_completed_todos ────────────────────────────────────────────────────────

def test_get_completed_empty_file(tmp_path):
    assert get_completed_todos(str(tmp_path)) == "No completed todos."


def test_get_completed_no_done_items(tmp_path):
    (tmp_path / "todos.md").write_text("- [ ] Pending task\n")
    assert get_completed_todos(str(tmp_path)) == "No completed todos."


def test_get_completed_returns_done_items(tmp_path):
    (tmp_path / "todos.md").write_text(
        "- [x] Done lowercase\n"
        "- [X] Done uppercase\n"
        "- [ ] Still pending\n"
    )
    result = get_completed_todos(str(tmp_path))
    assert "Done lowercase" in result
    assert "Done uppercase" in result
    assert "Still pending" not in result


def test_get_completed_format(tmp_path):
    (tmp_path / "todos.md").write_text("- [x] Review PR\n")
    result = get_completed_todos(str(tmp_path))
    assert result == "- Review PR"
