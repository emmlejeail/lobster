"""Read/write helpers for ~/lobster-brain/*.md files."""

import re
from datetime import date, timedelta
from pathlib import Path


def _brain(brain_path: str) -> Path:
    return Path(brain_path)


# ── Generic file ops ─────────────────────────────────────────────────────────

def read_file(brain_path: str, filename: str) -> str:
    """Return contents of a brain file, or empty string if missing."""
    p = _brain(brain_path) / filename
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8")


def write_file(brain_path: str, filename: str, content: str) -> None:
    """Overwrite a brain file with content."""
    p = _brain(brain_path) / filename
    p.write_text(content, encoding="utf-8")


def append_file(brain_path: str, filename: str, text: str) -> None:
    """Append text (with newline) to a brain file."""
    p = _brain(brain_path) / filename
    with open(p, "a", encoding="utf-8") as f:
        f.write(text if text.endswith("\n") else text + "\n")


# ── Work log ─────────────────────────────────────────────────────────────────

def append_worklog(brain_path: str, entry: str) -> str:
    """Append a dated entry to worklog.md. Returns confirmation."""
    today = date.today().isoformat()
    line = f"\n### {today}\n{entry.strip()}\n"
    append_file(brain_path, "worklog.md", line)
    return f"Work log entry added for {today}."


def get_today_worklog(brain_path: str) -> str:
    """Return today's work log entries, or a note if none exist."""
    today = date.today().isoformat()
    content = read_file(brain_path, "worklog.md")
    lines = content.splitlines()
    capturing = False
    result: list[str] = []
    for line in lines:
        if line.startswith(f"### {today}"):
            capturing = True
        elif capturing and line.startswith("### "):
            break
        if capturing:
            result.append(line)
    if not result:
        return f"No work log entries for {today} yet."
    return "\n".join(result)


def get_week_worklog(brain_path: str) -> str:
    """Return worklog entries from Monday of the current week through today."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())  # Monday of current week

    content = read_file(brain_path, "worklog.md")
    lines = content.splitlines()

    # Collect sections keyed by date
    sections: dict[date, list[str]] = {}
    current_date: date | None = None

    date_re = re.compile(r"^### (\d{4}-\d{2}-\d{2})$")
    for line in lines:
        m = date_re.match(line)
        if m:
            d = date.fromisoformat(m.group(1))
            current_date = d if monday <= d <= today else None
            if current_date is not None:
                sections.setdefault(current_date, [])
        elif current_date is not None:
            sections[current_date].append(line)

    if not sections:
        return f"No worklog entries for the week of {monday.isoformat()} – {today.isoformat()}."

    parts = []
    for d in sorted(sections):
        entries = "\n".join(l for l in sections[d] if l.strip())
        if entries:
            parts.append(f"{d.isoformat()}:\n{entries}")

    return "\n\n".join(parts) if parts else f"No worklog entries for the week of {monday.isoformat()} – {today.isoformat()}."


# ── Memory ───────────────────────────────────────────────────────────────────

def update_memory(brain_path: str, fact: str) -> str:
    """Append a new fact to memory.md. Returns confirmation."""
    today = date.today().isoformat()
    line = f"\n- [{today}] {fact.strip()}"
    append_file(brain_path, "memory.md", line)
    return "Memory updated."
