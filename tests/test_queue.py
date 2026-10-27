from __future__ import annotations

import asyncio

from app.config import Settings
from app.database.models import VacancyStatus
from app.database.repository import VacancyRepository
from app.queue.processor import QueueProcessor


class FakeNotifier:
    configured = False


class FakeProcessor:
    def __init__(self, repository: VacancyRepository) -> None:
        self.repository = repository
        self.notifier = FakeNotifier()
        self.active = 0
        self.max_active = 0

    async def process(self, vacancy_id: str) -> None:
        if not self.repository.transition(
            vacancy_id, VacancyStatus.PROCESSING, expected={VacancyStatus.QUEUED}
        ):
            return
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.03)
        self.repository.transition(
            vacancy_id, VacancyStatus.NOTIFIED, expected={VacancyStatus.PROCESSING}
        )
        self.active -= 1


async def test_queue_processes_jobs_with_concurrency_limit(
    repository: VacancyRepository, settings: Settings
) -> None:
    for vacancy_id in ("1", "2", "3", "4"):
        repository.add_if_absent(vacancy_id, "test", VacancyStatus.QUEUED)
    fake = FakeProcessor(repository)
    queue = QueueProcessor(repository, fake, settings)  # type: ignore[arg-type]
    await queue.start()
    for _ in range(100):
        statuses = [repository.get(item).status for item in ("1", "2", "3", "4")]  # type: ignore[union-attr]
        if all(status == VacancyStatus.NOTIFIED.value for status in statuses):
            break
        await asyncio.sleep(0.02)
    await queue.stop()
    assert fake.max_active == 2


def test_recovery_requeues_fetched_job(repository: VacancyRepository) -> None:
    repository.add_if_absent("1", "test", VacancyStatus.QUEUED)
    repository.transition("1", VacancyStatus.PROCESSING, expected={VacancyStatus.QUEUED})
    repository.transition("1", VacancyStatus.FETCHED, expected={VacancyStatus.PROCESSING})
    assert repository.recover(600, 2) == 1
    assert repository.get("1").status == VacancyStatus.QUEUED.value  # type: ignore[union-attr]
