#!/usr/bin/env bash
# Lobster setup script — run once to initialize everything.
set -euo pipefail

LOBSTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BRAIN_DIR="${HOME}/lobster-brain"
LAUNCH_AGENTS="${HOME}/Library/LaunchAgents"
PLIST_NAME="com.lobster.assistant.plist"
VENV_DIR="${LOBSTER_DIR}/.venv"

echo "==================================================="
echo "  🦞  Lobster Personal AI Assistant — Setup"
echo "==================================================="
echo ""

# ── 1. Create ~/lobster-brain/ and seed files ────────────────────────────────
echo "→ Creating ${BRAIN_DIR}/ …"
mkdir -p "${BRAIN_DIR}"

seed_file() {
    local path="$1"
    local content="$2"
    if [ ! -f "${path}" ]; then
        echo "${content}" > "${path}"
        echo "  Created: ${path}"
    else
        echo "  Skipped (exists): ${path}"
    fi
}

seed_file "${BRAIN_DIR}/role.md" "# Lobster — Role & Persona

You are Lobster, a personal AI assistant for your owner.
You are helpful, concise, and proactive.
You help manage daily tasks, work logs, todos, and calendar.
You communicate via Telegram.

Your owner's preferences:
- Prefer short, actionable responses.
- Use plain text or light markdown (Telegram-compatible).
- Always be honest if you are unsure of something."

seed_file "${BRAIN_DIR}/memory.md" "# Long-term Memory

<!-- Lobster appends facts here as they are discovered. -->
"

seed_file "${BRAIN_DIR}/worklog.md" "# Work Log

<!-- Entries are appended below in ### YYYY-MM-DD format. -->
"

seed_file "${BRAIN_DIR}/todos.md" "# Todos

- [ ] Set up Lobster and test the /start command
- [ ] Configure morning briefing time in config.yaml
"

echo ""

# ── 2. Create Python venv & install dependencies ─────────────────────────────
echo "→ Setting up Python virtual environment at ${VENV_DIR} …"
python3 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install --quiet --upgrade pip
"${VENV_DIR}/bin/pip" install --quiet -r "${LOBSTER_DIR}/requirements.txt"
echo "  Dependencies installed."
echo ""

# ── 3. Install launchd plist ─────────────────────────────────────────────────
VENV_PYTHON="${VENV_DIR}/bin/python3"

echo "→ Installing launchd plist …"
mkdir -p "${LAUNCH_AGENTS}"

# Substitute placeholders in the plist
sed \
    -e "s|VENV_PYTHON|${VENV_PYTHON}|g" \
    -e "s|LOBSTER_DIR|${LOBSTER_DIR}|g" \
    -e "s|BRAIN_PATH|${BRAIN_DIR}|g" \
    "${LOBSTER_DIR}/${PLIST_NAME}" \
    > "${LAUNCH_AGENTS}/${PLIST_NAME}"

echo "  Installed to: ${LAUNCH_AGENTS}/${PLIST_NAME}"
echo ""

# ── 4. Check config.yaml ─────────────────────────────────────────────────────
CONFIG="${LOBSTER_DIR}/config.yaml"
if grep -q "YOUR_ANTHROPIC_API_KEY" "${CONFIG}" || grep -q "YOUR_TELEGRAM_BOT_TOKEN" "${CONFIG}"; then
    echo "⚠️  ACTION REQUIRED: Edit config.yaml before loading the daemon."
    echo ""
    echo "   You need:"
    echo "   1. Anthropic API key  → https://console.anthropic.com/"
    echo "   2. Telegram bot token → message @BotFather on Telegram:"
    echo "      /newbot → follow prompts → copy the token"
    echo "   3. Your Telegram chat ID → after creating the bot, send it"
    echo "      any message, then run:"
    echo "      curl https://api.telegram.org/bot<TOKEN>/getUpdates"
    echo "      and look for 'chat' → 'id' in the response."
    echo "      (Or just start the bot — Lobster saves it automatically.)"
    echo ""
    echo "   Edit: ${CONFIG}"
    echo ""
    echo "   Then run:"
    echo "   launchctl load ${LAUNCH_AGENTS}/${PLIST_NAME}"
    echo ""
else
    # ── 5. Load the daemon ────────────────────────────────────────────────────
    echo "→ Loading Lobster daemon with launchctl …"
    # Unload first in case it's already loaded
    launchctl unload "${LAUNCH_AGENTS}/${PLIST_NAME}" 2>/dev/null || true
    launchctl load "${LAUNCH_AGENTS}/${PLIST_NAME}"
    echo "  Daemon loaded."
    echo ""
    echo "✅  Lobster is running!"
    echo "   Check status:  launchctl list | grep lobster"
    echo "   View logs:     tail -f ${BRAIN_DIR}/lobster.log"
    echo ""
fi

echo "==================================================="
echo "  Setup complete."
echo "==================================================="
