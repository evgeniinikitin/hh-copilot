from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from app.ai.schemas import VacancyAnalysis
from app.config import Settings
from app.hh.schemas import NormalizedVacancy

logger = logging.getLogger("telegram")

RECOMMENDATIONS = {
    "strong_apply": "СИЛЬНО РЕКОМЕНДУЮ",
    "apply": "ОТКЛИКАТЬСЯ",
    "maybe": "МОЖНО РАССМОТРЕТЬ",
    "skip": "ПРОПУСТИТЬ",
}


class TelegramError(RuntimeError):
    pass


class TelegramNotifier:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(timeout=20.0)

    @property
    def configured(self) -> bool:
        return bool(self.settings.telegram_bot_token and self.settings.telegram_chat_id)

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def send_batch_started(self, count: int) -> None:
        if not self.configured or count < 2:
            return
        await self._send(f"🔄 HH Copilot\n\nНайдено новых вакансий: {count}.\nНачинаю анализ.")

    async def send_analysis(self, vacancy: NormalizedVacancy, analysis: VacancyAnalysis) -> None:
        strengths = "\n".join(f"• {item}" for item in analysis.strengths) or "• —"
        gaps = "\n".join(f"• {item}" for item in analysis.gaps) or "• существенных нет"
        text = (
            f"🔥 {vacancy.title}\n"
            f"{vacancy.company_name or 'Компания не указана'}\n\n"
            f"Match: {analysis.match_score}/100\n"
            f"Рекомендация: {RECOMMENDATIONS[analysis.recommendation]}\n\n"
            f"Почему подходит:\n{strengths}\n\n"
            f"Что не совпадает:\n{gaps}\n\n"
            f"Сопроводительное:\n\n{analysis.cover_letter}"
        )
        markup: dict[str, Any] | None = None
        if vacancy.alternate_url:
            markup = {
                "inline_keyboard": [[{"text": "Открыть вакансию", "url": vacancy.alternate_url}]]
            }
        await self._send(text, reply_markup=markup)

    async def _send(self, text: str, reply_markup: dict[str, Any] | None = None) -> None:
        if not self.configured:
            raise TelegramError("Telegram is not configured")
        url = f"https://api.telegram.org/bot{self.settings.telegram_bot_token}/sendMessage"
        payload: dict[str, Any] = {"chat_id": self.settings.telegram_chat_id, "text": text}
        if reply_markup:
            payload["reply_markup"] = reply_markup
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await self.client.post(url, json=payload)
                response.raise_for_status()
                body = response.json()
                if not body.get("ok"):
                    raise TelegramError(str(body.get("description") or "Telegram API error"))
                return
            except (httpx.HTTPError, TelegramError) as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
        raise TelegramError(f"Telegram delivery failed: {last_error}")
