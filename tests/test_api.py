from __future__ import annotations

import httpx

from app.api.server import create_app
from app.config import Settings


async def test_health_and_sync(settings: Settings) -> None:
    app = create_app(settings, start_workers=False)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            health = await client.get("/health")
            assert health.json() == {"status": "ok"}
            sync = await client.post(
                "/api/v1/sync",
                json={"vacancy_ids": ["123", "456"], "source": "chrome_sync"},
            )
            assert sync.status_code == 200
            assert sync.json()["baseline"] is True
            status = await client.get("/api/v1/status")
            assert status.json()["known_total"] == 2


async def test_instant_is_idempotent(settings: Settings) -> None:
    app = create_app(settings, start_workers=False)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            first = await client.post(
                "/api/v1/vacancies", json={"vacancy_id": "123", "source": "instant"}
            )
            second = await client.post(
                "/api/v1/vacancies", json={"vacancy_id": "123", "source": "instant"}
            )
            assert first.json()["queued"] is True
            assert second.json()["queued"] is False
            status = await client.get("/api/v1/status")
            assert status.json()["known_total"] == 1
