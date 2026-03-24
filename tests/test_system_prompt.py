"""Tests for prompts/system_prompt.py"""
from datetime import date

import pytest
from prompts.system_prompt import build_system_prompt


def _seed(tmp_path, role="", memory="", todos="", worklog=""):
    (tmp_path / "role.md").write_text(role, encoding="utf-8")
    (tmp_path / "memory.md").write_text(memory, encoding="utf-8")
    (tmp_path / "todos.md").write_text(todos, encoding="utf-8")
    (tmp_path / "worklog.md").write_text(worklog, encoding="utf-8")


# ── date ───────────────────────────────────────────────────────────────────────

def test_prompt_contains_today(tmp_path):
    _seed(tmp_path, role="You are helpful.", memory="- fact", todos="- [ ] Task\n")
    result = build_system_prompt(str(tmp_path))
    today = date.today().strftime("%A, %B %d, %Y")
    assert today in result


# ── role section ───────────────────────────────────────────────────────────────

def test_prompt_contains_role_text(tmp_path):
    _seed(tmp_path, role="You are a lobster.")
    result = build_system_prompt(str(tmp_path))
    assert "You are a lobster." in result


def test_prompt_empty_role_absent(tmp_path):
    _seed(tmp_path, role="", memory="some fact")
    result = build_system_prompt(str(tmp_path))
    # With no role, the only content before the first "##" header should be the date line.
    today = date.today().strftime("%A, %B %d, %Y")
    before_first_header = result.split("##")[0]
    assert before_first_header.strip() == f"Today is {today}."


# ── memory section ─────────────────────────────────────────────────────────────

def test_prompt_contains_memory_header(tmp_path):
    _seed(tmp_path, memory="- [2024-01-01] some fact")
    result = build_system_prompt(str(tmp_path))
    assert "## Long-term Memory" in result


def test_prompt_empty_memory_header_absent(tmp_path):
    _seed(tmp_path, role="Role text", memory="")
    result = build_system_prompt(str(tmp_path))
    assert "## Long-term Memory" not in result


# ── todos section ──────────────────────────────────────────────────────────────

def test_prompt_contains_todos_header(tmp_path):
    _seed(tmp_path)
    result = build_system_prompt(str(tmp_path))
    assert "## Current Todos" in result


def test_prompt_contains_todo_items(tmp_path):
    _seed(tmp_path, todos="- [ ] Task A\n- [x] Task B\n")
    result = build_system_prompt(str(tmp_path))
    assert "Task A" in result
    assert "Task B" in result


# ── worklog section ────────────────────────────────────────────────────────────

def test_prompt_contains_worklog_header(tmp_path):
    _seed(tmp_path)
    result = build_system_prompt(str(tmp_path))
    assert "## Today's Work Log" in result


# ── section ordering + completeness ───────────────────────────────────────────

def test_section_order_all_present(tmp_path):
    today = date.today().isoformat()
    _seed(
        tmp_path,
        role="Be helpful.",
        memory="- a fact",
        todos="- [ ] Task\n",
        worklog=f"\n### {today}\nDid work\n",
    )
    result = build_system_prompt(str(tmp_path))
    idx_date = result.index("Today is")
    idx_memory = result.index("## Long-term Memory")
    idx_todos = result.index("## Current Todos")
    idx_worklog = result.index("## Today's Work Log")
    idx_instructions = result.index("## Instructions")
    assert idx_date < idx_memory < idx_todos < idx_worklog < idx_instructions


def test_instructions_always_present(tmp_path):
    _seed(tmp_path)  # empty brain
    result = build_system_prompt(str(tmp_path))
    assert "## Instructions" in result


def test_full_prompt_no_duplicate_headers(tmp_path):
    today = date.today().isoformat()
    _seed(
        tmp_path,
        role="Role text",
        memory="- fact",
        todos="- [ ] Task\n",
        worklog=f"\n### {today}\nEntry\n",
    )
    result = build_system_prompt(str(tmp_path))
    headers = [line for line in result.splitlines() if line.startswith("## ")]
    assert len(headers) == len(set(headers))


def test_worklog_no_entry_fallback(tmp_path):
    _seed(tmp_path)  # empty worklog
    result = build_system_prompt(str(tmp_path))
    assert "No work log entries" in result
