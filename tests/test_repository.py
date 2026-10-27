from app.database.models import VacancyStatus
from app.database.repository import VacancyRepository


def test_insert_and_duplicate_prevention(repository: VacancyRepository) -> None:
    first, created = repository.add_if_absent("123", "instant", VacancyStatus.QUEUED)
    second, duplicate_created = repository.add_if_absent("123", "sync", VacancyStatus.QUEUED)
    assert created is True
    assert duplicate_created is False
    assert first.id == second.id
    assert repository.count() == 1


def test_status_transition(repository: VacancyRepository) -> None:
    repository.add_if_absent("123", "sync", VacancyStatus.QUEUED)
    changed = repository.transition(
        "123", VacancyStatus.PROCESSING, expected={VacancyStatus.QUEUED}
    )
    repeated = repository.transition(
        "123", VacancyStatus.PROCESSING, expected={VacancyStatus.QUEUED}
    )
    assert changed is True
    assert repeated is False


def test_failed_vacancy_can_be_queued_again(repository: VacancyRepository) -> None:
    repository.add_if_absent("123", "instant", VacancyStatus.QUEUED)
    repository.mark_failed("123", "temporary failure")

    assert repository.queue_existing("123", "retry") is True
    row = repository.get("123")
    assert row is not None
    assert row.status == VacancyStatus.QUEUED.value
    assert row.source == "retry"
    assert row.error_message is None
    assert row.retry_count == 0
