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


async def ask_perf_review_questions(
    worklog: str,
    todos: str,
    question_num: int,
    previous_answers: str,
    cfg: dict,
) -> str:
    """Ask the next targeted question for the perf review Q&A.

    question_num: 0 = first question (accomplishments), 1 = second (growth/challenges).
    Returns "READY" once both questions have been asked (question_num >= 2).
    """
    if question_num >= 2:
        return "READY"

    worklog = _truncate_worklog(worklog)
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

    prompt = (
        "You're helping a software engineer write their self-performance review. "
        "Ask the following question in a warm, concise way. "
        "Do NOT generate the review yet — just ask the question.\n\n"
        f"Worklog summary:\n{worklog}\n\n"
        f"Completed todos:\n{todos}\n\n"
        f"Previous answers so far:\n{previous_answers or 'None'}\n\n"
        f"Question to ask: {questions[question_num]}"
    )
    reply, _ = await run_agent(prompt, cfg)
    return reply


async def generate_perf_review(
    worklog: str,
    todos: str,
    extra_context: str,
    period: str,
    cfg: dict,
) -> str:
    """Generate a structured self-performance review document."""
    worklog = _truncate_worklog(worklog)
    prompt = (
        f"Generate a structured self-performance review for the period: {period}.\n\n"
        f"Use this exact format:\n"
        f"## Self Performance Review — {period}\n\n"
        f"### Summary\n"
        f"[2–3 sentence overview of the period]\n\n"
        f"### Key Accomplishments\n"
        f"[Bullet points with concrete details pulled from worklog and context]\n\n"
        f"### Challenges & Growth\n"
        f"[Honest reflection, framed positively]\n\n"
        f"### Collaboration & Impact\n"
        f"[Cross-team work, mentorship, code reviews, etc.]\n\n"
        f"### Goals for Next Period\n"
        f"[Forward-looking, based on current context]\n\n"
        f"Write in first person. Be specific and concrete. "
        f"Use worklog entries as evidence for accomplishments.\n\n"
        f"Worklog:\n{worklog}\n\n"
        f"Completed todos:\n{todos}\n\n"
        f"Additional context from Q&A:\n{extra_context}"
    )
    reply, _ = await run_agent(prompt, cfg)
    return reply
