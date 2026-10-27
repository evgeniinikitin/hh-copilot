from __future__ import annotations

from pathlib import Path

import pytest

from app.config import Settings
from app.database.repository import VacancyRepository
from app.database.session import create_database_engine, create_session_factory, initialize_database


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
        max_concurrent_ai_jobs=2,
        max_new_vacancies_per_sync=30,
    )


@pytest.fixture
def repository(settings: Settings) -> VacancyRepository:
    engine = create_database_engine(settings)
    initialize_database(engine)
    repo = VacancyRepository(create_session_factory(engine))
    yield repo
    engine.dispose()
