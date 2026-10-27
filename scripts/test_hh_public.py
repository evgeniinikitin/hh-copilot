from __future__ import annotations

import argparse
import asyncio

from app.config import get_settings
from app.hh.public_client import HHPublicClient


async def run(vacancy_id: str | None) -> None:
    client = HHPublicClient(get_settings())
    try:
        if vacancy_id is None:
            response = await client.client.get(
                "https://api.hh.ru/vacancies",
                params={"per_page": 1, "order_by": "publication_time"},
                headers=client._api_headers(),
            )
            response.raise_for_status()
            vacancy_id = str(response.json()["items"][0]["id"])
        vacancy, _raw = await client.get_vacancy(vacancy_id)
        print(f"HH vacancy fetch OK: {vacancy.id} — {vacancy.title}")
    finally:
        await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("vacancy_id", nargs="?", help="ID активной вакансии HH")
    asyncio.run(run(parser.parse_args().vacancy_id))
