"""Generate a weekly Confluence-ready snippet using Claude."""

from datetime import date, timedelta

from agent import run_agent
from handlers.file_manager import get_week_worklog


def _week_range() -> str:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return f"{monday.strftime('%B %d')}–{today.strftime('%d, %Y')}"


def get_weekly_context(cfg: dict) -> tuple[str, str]:
    """Return (worklog, week_range) for the current week."""
    worklog = get_week_worklog(cfg["brain_path"])
    return worklog, _week_range()


async def ask_weekly_questions(worklog: str, cfg: dict) -> str:
    """Ask 1-2 clarifying questions or return 'READY' if worklog is detailed enough."""
    prompt = (
        "You're helping write a professional weekly update for Confluence. "
        "Review this week's worklog. "
        "If you need 1-2 specific pieces of information to write a rich Highlights section "
        "(outcomes, impact, blockers), ask them now — be brief and direct. "
        "If the worklog is already detailed enough, reply with just the word: READY. "
        "Do not generate the snippet yet.\n\n"
        f"Worklog:\n{worklog}"
    )
    reply, _ = await run_agent(prompt, cfg)
    return reply


async def generate_weekly_snippet(worklog: str, extra_context: str, cfg: dict) -> str:
    """Generate the final weekly snippet with thematic prose paragraphs."""
    week_range = _week_range()
    prompt = (
        f"Generate a weekly Confluence update. Format:\n"
        f"## Weekly Update — Week of {week_range}\n\n"
        f"### Highlights\n"
        f"[Group the week's work into thematic sections (2–4 sections). "
        f"Give each section a short ### header. Write 2–3 sentences of professional prose per section. "
        f"Use first person: 'I' for individual work, 'the team' or 'we' when the work was collaborative. "
        f"Describe what was accomplished, key outcomes, and any notable decisions or challenges.]\n\n"
        f"Worklog:\n{worklog}\n"
        f"Additional context:\n{extra_context}"
    )
    reply, _ = await run_agent(prompt, cfg)
    return reply
