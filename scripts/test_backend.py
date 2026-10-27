from __future__ import annotations

import asyncio

import httpx

from app.config import get_settings


async def main() -> None:
    settings = get_settings()
    url = f"http://{settings.backend_host}:{settings.backend_port}/health"
    async with httpx.AsyncClient(timeout=5.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        assert response.json() == {"status": "ok"}
    print(f"Backend OK: {url}")


if __name__ == "__main__":
    asyncio.run(main())
