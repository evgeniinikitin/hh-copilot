from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from app.config import Settings
from app.database.models import VacancyStatus
from app.database.repository import VacancyRepository
from app.telegram.notifier import TelegramError, TelegramNotifier
from app.watcher.deduplicator import normalize_vacancy_ids

logger = logging.getLogger("sync")


@dataclass(frozen=True)
class SyncResult:
    received: int
    new: int
    existing: int
    queued: int
    baseline: bool = False
    pending: int = 0


class SyncService:
    def __init__(
        self,
        repository: VacancyRepository,
        settings: Settings,
        notifier: TelegramNotifier | None = None,
    ) -> None:
        self.repository = repository
        self.settings = settings
        self.notifier = notifier

    async def sync(self, vacancy_ids: list[str], source: str) -> SyncResult:
        current_ids = normalize_vacancy_ids(vacancy_ids)
        initialized = self.repository.get_state("favorites_initialized") == "true"
        known_ids = self.repository.known_ids()

        if not initialized:
            for vacancy_id in sorted(current_ids):
                self.repository.add_if_absent(vacancy_id, source, VacancyStatus.BASELINE)
            self.repository.set_state("favorites_initialized", "true")
            self.repository.set_state("last_sync_at", datetime.now(UTC).isoformat())
            logger.info("Initial baseline created count=%s", len(current_ids))
            return SyncResult(
                received=len(current_ids),
                new=0,
                existing=len(current_ids & known_ids),
                queued=0,
                baseline=True,
            )

        new_ids = sorted(current_ids - known_ids, key=int, reverse=True)
        pending_ids = sorted(
            current_ids & self.repository.ids_with_status(VacancyStatus.DETECTED),
            key=int,
            reverse=True,
        )
        candidate_ids = new_ids + pending_ids
        limit = self.settings.max_new_vacancies_per_sync
        queue_ids = set(candidate_ids[:limit])
        for vacancy_id in new_ids:
            status = VacancyStatus.QUEUED if vacancy_id in queue_ids else VacancyStatus.DETECTED
            self.repository.add_if_absent(vacancy_id, source, status)
        for vacancy_id in pending_ids:
            if vacancy_id in queue_ids:
                self.repository.queue_existing(vacancy_id, source)
        self.repository.set_state("last_sync_at", datetime.now(UTC).isoformat())
        if self.notifier and queue_ids:
            try:
                await self.notifier.send_batch_started(len(queue_ids))
            except TelegramError as exc:
                logger.warning("Batch notification failed error=%s", exc)
        pending = max(0, len(candidate_ids) - len(queue_ids))
        logger.info(
            "Sync complete received=%s new=%s queued=%s pending=%s",
            len(current_ids),
            len(new_ids),
            len(queue_ids),
            pending,
        )
        return SyncResult(
            received=len(current_ids),
            new=len(new_ids),
            existing=len(current_ids & known_ids),
            queued=len(queue_ids),
            pending=pending,
        )

    def enqueue_instant(self, vacancy_id: str, source: str) -> tuple[bool, str]:
        row, created = self.repository.add_if_absent(vacancy_id, source, VacancyStatus.QUEUED)
        if created:
            logger.info("Vacancy queued id=%s source=%s", vacancy_id, source)
            return True, VacancyStatus.QUEUED.value
        queued = self.repository.queue_existing(vacancy_id, source)
        current = self.repository.get(vacancy_id)
        return queued, current.status if current else row.status
