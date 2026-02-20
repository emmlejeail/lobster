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
