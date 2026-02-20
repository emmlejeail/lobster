"""Core LLM agent: builds context, calls Anthropic API with tool use."""

import json
import logging
from typing import Any

import anthropic

from handlers.file_manager import append_worklog, update_memory
from handlers.todo_manager import add_todo, complete_todo, list_todos, remove_todo
from handlers.calendar_reader import get_calendar_events
from prompts.system_prompt import build_system_prompt

logger = logging.getLogger(__name__)

# ── Tool definitions sent to Claude ──────────────────────────────────────────

TOOLS: list[dict] = [
    {
        "name": "append_worklog",
        "description": "Append a new entry to the daily work log (worklog.md).",
        "input_schema": {
            "type": "object",
            "properties": {
                "entry": {"type": "string", "description": "The work log entry text."},
            },
            "required": ["entry"],
        },
    },
    {
        "name": "add_todo",
        "description": "Add a new todo item to the todo list (todos.md).",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The todo item text."},
            },
            "required": ["text"],
        },
    },
    {
        "name": "complete_todo",
        "description": "Mark a todo item as done by its 1-based index.",
        "input_schema": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "1-based index of the todo to complete."},
            },
            "required": ["index"],
        },
    },
    {
        "name": "remove_todo",
        "description": "Remove a todo item by its 1-based index.",
        "input_schema": {
            "type": "object",
            "properties": {
                "index": {"type": "integer", "description": "1-based index of the todo to remove."},
            },
            "required": ["index"],
        },
    },
    {
        "name": "list_todos",
        "description": "Return the current todo list as a formatted string.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "update_memory",
        "description": "Append an important fact or preference to memory.md for future recall.",
        "input_schema": {
            "type": "object",
            "properties": {
                "fact": {"type": "string", "description": "The fact or note to remember."},
            },
            "required": ["fact"],
        },
    },
    {
        "name": "get_calendar_events",
        "description": "Retrieve calendar events from macOS Calendar.app. Pass days_ahead=7 for the next 7 days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": "How many days ahead to include (0 = today only, 7 = next 7 days). Default: 0.",
                },
            },
            "required": [],
        },
    },
]


# ── Tool dispatcher ───────────────────────────────────────────────────────────

def _dispatch_tool(name: str, tool_input: dict[str, Any], brain_path: str) -> str:
    if name == "append_worklog":
        return append_worklog(brain_path, tool_input["entry"])
    if name == "add_todo":
        return add_todo(brain_path, tool_input["text"])
    if name == "complete_todo":
        return complete_todo(brain_path, tool_input["index"])
    if name == "remove_todo":
        return remove_todo(brain_path, tool_input["index"])
    if name == "list_todos":
        return list_todos(brain_path)
    if name == "update_memory":
        return update_memory(brain_path, tool_input["fact"])
    if name == "get_calendar_events":
        return get_calendar_events(tool_input.get("days_ahead", 0))
    return f"Unknown tool: {name}"


# ── Main agent function ───────────────────────────────────────────────────────

async def run_agent(
    user_message: str,
    cfg: dict,
    conversation_history: list[dict] | None = None,
    max_history: int = 10,
) -> tuple[str, list[dict]]:
    """
    Process a user message through the LLM agent with tool use.

    Args:
        user_message: The incoming message text.
        cfg: Loaded config dict.
        conversation_history: Optional prior turns (list of Anthropic message dicts).
        max_history: Maximum number of messages to retain in history.

    Returns:
        Tuple of (assistant's final text response, updated message history).
    """
    client = anthropic.Anthropic(api_key=cfg["anthropic_api_key"])
    brain_path = cfg["brain_path"]
    model = cfg.get("model", "claude-sonnet-4-6")
    max_tokens = cfg.get("max_tokens", 4096)

    system_prompt = build_system_prompt(brain_path)

    messages: list[dict] = list(conversation_history or [])
    messages.append({"role": "user", "content": user_message})

    # Agentic loop: keep going until the model stops using tools
    while True:
        logger.debug("Calling Anthropic API (model=%s, messages=%d)", model, len(messages))
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            tools=TOOLS,
            messages=messages,
        )

        # Collect text + tool_use blocks
        tool_calls = [b for b in response.content if b.type == "tool_use"]
        text_blocks = [b for b in response.content if b.type == "text"]

        if response.stop_reason == "end_turn" or not tool_calls:
            # No more tool calls — append final assistant turn and trim history
            messages.append({"role": "assistant", "content": response.content})
            if len(messages) > max_history:
                messages = messages[-max_history:]
                while messages and messages[0]["role"] != "user":
                    messages = messages[1:]
            text_reply = "\n".join(b.text for b in text_blocks).strip() or "(no response)"
            return text_reply, messages

        # Execute all tool calls
        tool_results = []
        for tc in tool_calls:
            logger.info("Tool call: %s(%s)", tc.name, json.dumps(tc.input))
            result = _dispatch_tool(tc.name, tc.input, brain_path)
            logger.info("Tool result: %s", result)
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tc.id,
                "content": result,
            })

        # Append assistant turn + tool results to messages
        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
