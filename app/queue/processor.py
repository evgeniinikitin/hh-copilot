from __future__ import annotations

import asyncio
import logging

from app.config import Settings
from app.database.repository import VacancyRepository
from app.services.vacancy_processor import VacancyProcessor

logger = logging.getLogger("queue")


class QueueProcessor:
    def __init__(
        self,
        repository: VacancyRepository,
        processor: VacancyProcessor,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.processor = processor
        self.settings = settings
        self._runner: asyncio.Task[None] | None = None
        self._active: dict[str, asyncio.Task[None]] = {}
        self._stop = asyncio.Event()

    async def start(self) -> None:
        recovered = self.repository.recover(
            self.settings.processing_stale_seconds, self.settings.max_processing_retries
        )
        if recovered:
            logger.info("Recovered jobs count=%s", recovered)
        self._runner = asyncio.create_task(self._run(), name="hh-copilot-queue")

    async def stop(self) -> None:
        self._stop.set()
        if self._runner:
            await self._runner
        if self._active:
            await asyncio.gather(*self._active.values(), return_exceptions=True)

    async def _run(self) -> None:
        while not self._stop.is_set():
            self._remove_completed()
            capacity = self.settings.max_concurrent_ai_jobs - len(self._active)
            if capacity > 0:
                for vacancy_id in self.repository.next_queued_ids(capacity):
                    if vacancy_id not in self._active:
                        self._active[vacancy_id] = asyncio.create_task(
                            self.processor.process(vacancy_id), name=f"vacancy-{vacancy_id}"
                        )
            if self.processor.notifier.configured:
                for vacancy_id in self.repository.analyzed_unnotified_ids(5):
                    if vacancy_id not in self._active:
                        self._active[vacancy_id] = asyncio.create_task(
                            self._notify(vacancy_id), name=f"notify-{vacancy_id}"
                        )
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=2.0)
            except TimeoutError:
                pass
        self._remove_completed()

    async def _notify(self, vacancy_id: str) -> None:
        try:
            await self.processor.notify(vacancy_id)
        except Exception as exc:
            logger.warning("Notification retry failed id=%s error=%s", vacancy_id, exc)
            await asyncio.sleep(10)

    def _remove_completed(self) -> None:
        self._active = {key: task for key, task in self._active.items() if not task.done()}
