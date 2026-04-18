# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the full test suite
.venv/bin/python -m pytest tests/

# Run a single test file / single test
.venv/bin/python -m pytest tests/test_todo_manager.py
.venv/bin/python -m pytest tests/test_todo_manager.py::test_name

# Coverage report
.venv/bin/python -m pytest tests/ --cov=. --cov-report=term-missing

# Run the daemon in the foreground (useful for debugging — logs to stdout)
.venv/bin/python main.py

# launchd (production) daemon management
launchctl list | grep lobster
launchctl unload ~/Library/LaunchAgents/com.lobster.assistant.plist
launchctl load   ~/Library/LaunchAgents/com.lobster.assistant.plist
tail -f ~/lobster-brain/lobster.log
```

`pytest.ini` sets `pythonpath = .`, so tests import top-level modules (`agent`, `config`, `handlers.*`) directly — no package install needed.

## Architecture

Lobster is an async single-process daemon. `main.py` runs two concurrent subsystems in one asyncio loop:

1. **Telegram polling** (`handlers/telegram_handler.build_application`) — routes slash commands and free-text messages.
2. **APScheduler** (`scheduler.build_scheduler`) — fires morning briefing, evening check-in, optional weekly snippet, and persisted recurring reminders.

Both subsystems share a single `cfg` dict. `main.py` injects runtime objects into it (`cfg["_bot"]`, `cfg["_scheduler"]`) so handlers and tools can schedule new jobs or send Telegram messages without a global singleton.

### Config + secrets split

- `config.py` loads `.env` (secrets: `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`) and merges with `config.yaml` (non-secret settings). `config.yaml` is gitignored; `config.example.yaml` is the committed template.
- `telegram_chat_id` is written back into `config.yaml` by `save_chat_id()` the first time a user sends `/start` — do not expect it to be present on a fresh clone.

### Agent loop (`agent.py`)

`run_agent()` is the central LLM call. It:

1. Builds a system prompt (`prompts/system_prompt.build_system_prompt`) that stitches together `role.md`, `memory.md`, current todos, and today's worklog on every turn — the brain files are the source of truth, not in-memory state.
2. Runs an Anthropic tool-use loop: keeps calling the API and dispatching tools via `_dispatch_tool` until `stop_reason == "end_turn"`.
3. Trims conversation history to `max_history` (default 10) messages, and crucially **drops any leading orphan `tool_result` user messages** whose preceding `tool_use` assistant turn was trimmed away. Preserve this logic if you touch history handling — Anthropic rejects orphaned tool_result blocks.

Tools are defined in the `TOOLS` list and must be kept in sync with `_dispatch_tool`. Each tool ultimately reads/writes a file under `brain_path` or calls the scheduler — the LLM has no other side-effect surface.

### Brain files (`~/lobster-brain/`)

All persistent user state lives here as markdown — no database. Tests and handlers reference files by name:

- `role.md`, `memory.md` — injected into the system prompt.
- `worklog.md` — dated `### YYYY-MM-DD` sections. `get_date_range_worklog` parses this format; breaking the header format breaks worklog queries and weekly/perf-review generation.
- `todos.md` — checkbox markdown (`- [ ]` / `- [x]`), 1-based indexing exposed to the LLM.
- `recurring_reminders.json`, `.scheduler_state.json` — runtime state, created by the daemon. The scheduler rehydrates recurring reminders from the JSON on startup via `load_recurring_reminders`.
- `.onboarded` — marker written after the onboarding `ConversationHandler` completes. Delete it to re-run onboarding.

### Telegram specifics

- Hard 4096-char message limit. `scheduler._send_tg` and `telegram_handler._split_message` both chunk outbound text — `_split_message` prefers `\n### ` section boundaries, then `\n\n`, then a hard cut. Use it (or the scheduler helper) whenever emitting agent output that can exceed 4k chars (weekly snippet, perf review, briefings).
- Multi-turn flows (`/weekly`, `/perfreview`) keep per-chat session state in module-level dicts (`_weekly_sessions`, `_perf_review_sessions`) in `telegram_handler.py`. These are in-memory only — restarting the daemon drops in-progress Q&A sessions.

### Scheduler catch-up

`_check_missed_jobs` runs every 5 minutes and also immediately on startup. It consults `.scheduler_state.json` to decide whether today's briefing/check-in already fired and, if not, fires it as long as we're within `CATCHUP_HOURS` (4h) of the scheduled time. This is what makes Lobster resilient to laptop sleep — don't remove it, and if you add new scheduled jobs that should be catch-up-aware, wire them into the `checks` list.

### Timezone

`scheduler._get_local_timezone` reads `cfg["timezone"]` (IANA name) first, otherwise resolves macOS's `/etc/localtime` symlink, otherwise falls back to UTC. All cron triggers use this TZ — times in `config.yaml` are local.
