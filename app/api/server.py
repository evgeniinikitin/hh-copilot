from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.engine import Engine

from app.ai.analyzer import VacancyAnalyzer
from app.api.routes import router
from app.config import Settings, get_settings
from app.database.repository import VacancyRepository
from app.database.session import create_database_engine, create_session_factory, initialize_database
from app.hh.public_client import HHPublicClient
from app.logging_config import configure_logging
from app.queue.processor import QueueProcessor
from app.services.vacancy_processor import VacancyProcessor
from app.telegram.notifier import TelegramNotifier
from app.watcher.sync_service import SyncService


@dataclass
class AppContainer:
    settings: Settings
    engine: Engine
    repository: VacancyRepository
    hh_client: HHPublicClient
    notifier: TelegramNotifier
    sync_service: SyncService
    queue: QueueProcessor


def build_container(settings: Settings) -> AppContainer:
    engine = create_database_engine(settings)
    initialize_database(engine)
    repository = VacancyRepository(create_session_factory(engine))
    hh_client = HHPublicClient(settings)
    notifier = TelegramNotifier(settings)
    analyzer = VacancyAnalyzer(settings)
    vacancy_processor = VacancyProcessor(repository, hh_client, analyzer, notifier)
    queue = QueueProcessor(repository, vacancy_processor, settings)
    sync_service = SyncService(repository, settings, notifier)
    return AppContainer(
        settings=settings,
        engine=engine,
        repository=repository,
        hh_client=hh_client,
        notifier=notifier,
        sync_service=sync_service,
        queue=queue,
    )


def create_app(settings: Settings | None = None, *, start_workers: bool = True) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(resolved_settings)
        container = build_container(resolved_settings)
        app.state.container = container
        if start_workers:
            await container.queue.start()
        try:
            yield
        finally:
            if start_workers:
                await container.queue.stop()
            await container.hh_client.close()
            await container.notifier.close()
            container.engine.dispose()

    app = FastAPI(title="HH Copilot", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:8765", "http://localhost:8765"],
        allow_origin_regex=r"^chrome-extension://[a-p]{32}$",
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
    app.include_router(router)
    return app


app = create_app()
