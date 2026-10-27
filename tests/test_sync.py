from app.config import Settings
from app.database.models import VacancyStatus
from app.database.repository import VacancyRepository
from app.watcher.sync_service import SyncService


async def test_initial_sync_creates_baseline(
    repository: VacancyRepository, settings: Settings
) -> None:
    result = await SyncService(repository, settings).sync(["1", "2", "2"], "chrome_sync")
    assert result.baseline is True
    assert result.received == 2
    assert result.queued == 0
    assert repository.get("1").status == VacancyStatus.BASELINE.value  # type: ignore[union-attr]


async def test_subsequent_sync_queues_only_new_ids(
    repository: VacancyRepository, settings: Settings
) -> None:
    service = SyncService(repository, settings)
    await service.sync(["1", "2"], "chrome_sync")
    result = await service.sync(["1", "2", "3", "3"], "chrome_sync")
    assert result.new == 1
    assert result.existing == 2
    assert result.queued == 1
    assert repository.get("3").status == VacancyStatus.QUEUED.value  # type: ignore[union-attr]


async def test_empty_first_sync_is_valid(repository: VacancyRepository, settings: Settings) -> None:
    service = SyncService(repository, settings)
    first = await service.sync([], "chrome_sync")
    second = await service.sync(["5"], "chrome_sync")
    assert first.baseline is True
    assert second.queued == 1


async def test_large_sync_leaves_overflow_detected(
    repository: VacancyRepository, settings: Settings
) -> None:
    settings.max_new_vacancies_per_sync = 2
    service = SyncService(repository, settings)
    await service.sync([], "chrome_sync")
    result = await service.sync(["1", "2", "3"], "chrome_sync")
    assert result.queued == 2
    assert result.pending == 1
    statuses = {repository.get(item).status for item in ("1", "2", "3")}  # type: ignore[union-attr]
    assert statuses == {VacancyStatus.QUEUED.value, VacancyStatus.DETECTED.value}

    queued_ids = repository.next_queued_ids(10)
    for vacancy_id in queued_ids:
        repository.transition(vacancy_id, VacancyStatus.PROCESSING, expected={VacancyStatus.QUEUED})
    next_result = await service.sync(["1", "2", "3"], "chrome_sync")
    assert next_result.new == 0
    assert next_result.queued == 1
    assert next_result.pending == 0
