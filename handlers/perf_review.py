"""Generate a structured self-performance review using Claude."""

from datetime import date, timedelta

from agent import run_agent

_WORKLOG_CHAR_LIMIT = 12_000  # keep most recent entries if worklog is very large


def _truncate_worklog(worklog: str, limit: int = _WORKLOG_CHAR_LIMIT) -> str:
    """Keep the most recent entries if worklog exceeds limit."""
    if len(worklog) <= limit:
        return worklog
    truncated = worklog[-limit:]
    # Don't start mid-entry — trim to the first complete date header
    first_header = truncated.find("\n\n")
    if first_header != -1:
        truncated = truncated[first_header + 2:]
    return "[earlier entries omitted]\n\n" + truncated


def _default_period() -> tuple[date, date]:
    """Return (6 months ago, today)."""
    today = date.today()
    # Approximate 6 months as 183 days
    return today - timedelta(days=183), today


def _build_question_prompt(
    worklog: str,
    todos: str,
    question: str,
    previous_answers: str,
    level_expectations: str,
) -> str:
    worklog = _truncate_worklog(worklog)
    parts = [
        "You're helping a software engineer write their self-performance review. "
        "Ask the following question in a warm, concise way. "
        "Do NOT generate the review yet — just ask the question.",
        "",
        f"Worklog summary:\n{worklog}",
        "",
        f"Completed todos:\n{todos}",
        "",
        f"Previous answers so far:\n{previous_answers or 'None'}",
        "",
    ]
    if level_expectations.strip():
        parts += [f"Level expectations you're being evaluated against:\n{level_expectations.strip()}", ""]
    parts.append(f"Question to ask: {question}")
    return "\n".join(parts)


def _build_review_prompt(
    worklog: str,
    todos: str,
    extra_context: str,
    period: str,
    level_expectations: str,
) -> str:
    worklog = _truncate_worklog(worklog)
    parts = [
        f"Generate a structured self-performance review for the period: {period}.",
        "",
        "Use this exact format:",
        f"## Self Performance Review — {period}",
        "",
        "### Summary",
        "[2–3 sentence overview of the period]",
        "",
        "### Key Accomplishments",
        "[Bullet points with concrete details pulled from worklog and context]",
        "",
        "### Challenges & Growth",
        "[Honest reflection, framed positively]",
        "",
        "### Collaboration & Impact",
        "[Cross-team work, mentorship, code reviews, etc.]",
        "",
        "### Goals for Next Period",
        "[Forward-looking, based on current context]",
        "",
        "Write in first person. Be specific and concrete. "
        "Use worklog entries as evidence for accomplishments.",
    ]
    if level_expectations.strip():
        parts += [
            "For each key accomplishment, note which level expectation(s) it demonstrates. "
            "In Goals for Next Period, flag expectations that aren't yet well-evidenced.",
        ]
    parts += ["", f"Worklog:\n{worklog}", "", f"Completed todos:\n{todos}", ""]
    if level_expectations.strip():
        parts += [f"Level expectations you're being evaluated against:\n{level_expectations.strip()}", ""]
    parts.append(f"Additional context from Q&A:\n{extra_context}")
    return "\n".join(parts)


async def ask_perf_review_questions(
    worklog: str,
    todos: str,
    question_num: int,
    previous_answers: str,
    cfg: dict,
    level_expectations: str = "",
) -> str:
    """Ask the next targeted question for the perf review Q&A.

    question_num: 0 = first question (accomplishments), 1 = second (growth/challenges).
    Returns "READY" once both questions have been asked (question_num >= 2).
    """
    if question_num >= 2:
        return "READY"

    questions = [
        (
            "What are 1–2 accomplishments you're most proud of from this period "
            "that may not be fully reflected in the worklog?"
        ),
        (
            "Were there any significant challenges, learnings, or areas where you "
            "grew professionally during this period?"
        ),
    ]

    prompt = _build_question_prompt(
        worklog, todos, questions[question_num], previous_answers, level_expectations,
    )
    reply, _ = await run_agent(prompt, cfg)
    return reply


async def generate_perf_review(
    worklog: str,
    todos: str,
    extra_context: str,
    period: str,
    cfg: dict,
    level_expectations: str = "",
) -> str:
    """Generate a structured self-performance review document."""
    prompt = _build_review_prompt(worklog, todos, extra_context, period, level_expectations)
    reply, _ = await run_agent(prompt, cfg)
    return reply
