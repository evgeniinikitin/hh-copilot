from __future__ import annotations

import asyncio

from app.config import get_settings
from app.telegram.notifier import TelegramNotifier


async def main() -> None:
    notifier = TelegramNotifier(get_settings())
    try:
        await notifier._send("✅ HH Copilot: Telegram настроен и работает.")
        print("Telegram OK")
    finally:
        await notifier.close()


if __name__ == "__main__":
    asyncio.run(main())
