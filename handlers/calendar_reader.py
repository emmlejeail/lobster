"""macOS Calendar reader via icalBuddy."""

import re
import subprocess
import sys
from datetime import date

# Strip ANSI escape codes
_ANSI_RE = re.compile(r"\x1B[@-_][0-?]*[ -/]*[@-~]")


def get_calendar_events(days_ahead: int = 0) -> str:
    """
    Query macOS Calendar.app for events via icalBuddy.
    Returns a human-readable string listing each event, or a note if none.

    Args:
        days_ahead: 0 = today only; N > 0 = today through N days ahead.

    Requires Calendar access permission (macOS will prompt once).
    icalBuddy must be installed: brew install ical-buddy
    """
    date_arg = "eventsToday" if days_ahead == 0 else f"eventsToday+{days_ahead}"
    cmd = [
        "/opt/homebrew/bin/icalBuddy",
        "-f",                        # force formatting (consistent output)
        "-b", "EVENT:",              # mark each event start
        "-iep", "title,datetime,calendar",  # only title, time, calendar
    ]
    if days_ahead > 0:
        cmd += ["-sd"]               # separate events by date for multi-day output
    cmd.append(date_arg)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except FileNotFoundError:
        return "icalBuddy not found at /opt/homebrew/bin/icalBuddy. Install with: brew install ical-buddy"
    except subprocess.TimeoutExpired:
        return "Calendar query timed out."

    if result.returncode != 0:
        err = result.stderr.strip()
        auth_keywords = ("not authorized", "not permitted", "-1743", "access denied", "access")
        if any(kw in err.lower() for kw in auth_keywords):
            return (
                "Calendar access denied.\n\n"
                "The daemon runs Python at:\n"
                f"  {sys.executable}\n\n"
                "To fix: System Settings → Privacy & Security → Calendars → "
                "click + and add the binary above."
            )
        return f"icalBuddy error: {err}"

    raw = _ANSI_RE.sub("", result.stdout).strip()
    if not raw:
        if days_ahead == 0:
            label = date.today().strftime("%A, %B %d")
        else:
            label = f"the next {days_ahead} day{'s' if days_ahead != 1 else ''}"
        return f"No calendar events found for {label}."

    events = []
    current_title = None
    current_cal = None

    for line in raw.splitlines():
        if line.startswith("EVENT:"):
            # "EVENT:Title (CalendarName)"
            rest = line[len("EVENT:"):].strip()
            # Extract calendar name from trailing parentheses
            cal_match = re.search(r"\(([^)]+)\)\s*$", rest)
            if cal_match:
                current_cal = cal_match.group(1)
                current_title = rest[: cal_match.start()].strip()
            else:
                current_title = rest
                current_cal = ""
        elif line.startswith("    ") and current_title is not None:
            # Indented time line: "09:45 - 10:00" or "all-day"
            time_str = line.strip()
            events.append(f"• [{current_cal}] {current_title}  {time_str}")
            current_title = None
            current_cal = None

    # Flush any event with no time line (all-day events sometimes lack it)
    if current_title is not None:
        events.append(f"• [{current_cal}] {current_title}")

    if not events:
        if days_ahead == 0:
            return "No calendar events for today."
        return f"No calendar events for the next {days_ahead} day{'s' if days_ahead != 1 else ''}."

    if days_ahead == 0:
        header = "Calendar events for " + date.today().strftime("%A, %B %d")
    else:
        header = f"Calendar events for the next {days_ahead} day{'s' if days_ahead != 1 else ''}"
    return f"{header}:\n" + "\n".join(events)
