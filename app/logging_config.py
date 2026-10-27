from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.config import PROJECT_ROOT, Settings


def configure_logging(settings: Settings) -> None:
    log_dir = PROJECT_ROOT / "runtime" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        log_dir / "hh_copilot.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        handlers=[file_handler, console_handler],
        force=True,
    )
    # httpx logs complete request URLs. Telegram embeds the bot token in the URL,
    # so INFO-level transport logs would persist a credential in the local log file.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
