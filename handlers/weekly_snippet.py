"""Generate a weekly Confluence-ready snippet using Claude."""

from datetime import date, timedelta

from agent import run_agent
from handlers.file_manager import get_week_worklog
from handlers.todo_manager import list_todos


def _week_range() -> str:
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return f"{monday.strftime('%B %d')}–{today.strftime('%d, %Y')}"


async def generate_weekly_snippet(cfg: dict) -> str:
    brain_path = cfg["brain_path"]
    worklog = get_week_worklog(brain_path)
    todos = list_todos(brain_path)
    week_range = _week_range()

    prompt = (
        f"Generate a weekly Confluence snippet from this worklog. "
        f"Format it with exactly two sections:\n"
        f"**What I worked on** — bullet points derived from the worklog entries\n"
        f"**Next up** — open todos formatted as checkbox items (- [ ] ...)\n\n"
        f"Keep it concise and professional. Use plain Markdown compatible with Confluence.\n"
        f"Start with a heading: ## Weekly Update — Week of {week_range}\n\n"
        f"Worklog:\n{worklog}\n\n"
        f"Open todos:\n{todos}"
    )

    reply, _ = await run_agent(prompt, cfg)
    return reply
