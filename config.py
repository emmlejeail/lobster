"""Config loader: reads config.yaml for settings, .env for secrets."""

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


_CONFIG_PATH = Path(__file__).parent / "config.yaml"
_ENV_PATH = Path(__file__).parent / ".env"


def load_config() -> dict:
    """Load config.yaml for settings and .env for API secrets. Returns config dict."""
    # Load .env first so its values are available via os.environ
    load_dotenv(_ENV_PATH)

    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(f"config.yaml not found at {_CONFIG_PATH}")

    with open(_CONFIG_PATH) as f:
        cfg = yaml.safe_load(f)

    # Inject secrets from environment (set by .env or real env vars)
    cfg["anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY", "")
    cfg["telegram_bot_token"] = os.environ.get("TELEGRAM_BOT_TOKEN", "")

    for field in ("anthropic_api_key", "telegram_bot_token"):
        if not cfg[field]:
            raise ValueError(
                f"'{field.upper()}' is not set. "
                "Add it to the .env file next to config.yaml."
            )

    # Expand ~ in brain_path
    cfg["brain_path"] = str(Path(cfg.get("brain_path", "~/lobster-brain")).expanduser())

    return cfg


def save_chat_id(chat_id: int) -> None:
    """Persist telegram_chat_id back to config.yaml after first /start."""
    with open(_CONFIG_PATH) as f:
        raw = f.read()

    if "telegram_chat_id: null" in raw:
        raw = raw.replace("telegram_chat_id: null", f"telegram_chat_id: {chat_id}")
    else:
        # Already set — update the value
        lines = raw.splitlines()
        for i, line in enumerate(lines):
            if line.strip().startswith("telegram_chat_id:"):
                lines[i] = f"telegram_chat_id: {chat_id}"
                break
        raw = "\n".join(lines) + "\n"

    with open(_CONFIG_PATH, "w") as f:
        f.write(raw)
