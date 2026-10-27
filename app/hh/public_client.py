from __future__ import annotations

import asyncio
import logging
from email.utils import parsedate_to_datetime
from typing import Any

import httpx

from app.config import Settings
from app.hh.normalizer import normalize_api_vacancy, normalize_html_vacancy
from app.hh.schemas import NormalizedVacancy

logger = logging.getLogger("hh")


class VacancyNotFoundError(RuntimeError):
    pass


class HHPublicClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._api_available = True
        self._owns_client = client is None
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(20.0),
            follow_redirects=True,
        )

    async def close(self) -> None:
        if self._owns_client:
            await self.client.aclose()

    async def _request(self, url: str, *, html: bool = False) -> httpx.Response:
        last_error: Exception | None = None
        headers = self._html_headers() if html else self._api_headers()
        for attempt in range(3):
            try:
                response = await self.client.get(url, headers=headers)
                if response.status_code == 404:
                    raise VacancyNotFoundError(url)
                if response.status_code == 429 or response.status_code >= 500:
                    if attempt == 2:
                        response.raise_for_status()
                    await asyncio.sleep(self._retry_delay(response, attempt))
                    continue
                response.raise_for_status()
                return response
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt == 2:
                    raise
                await asyncio.sleep(2**attempt)
        if last_error:
            raise last_error
        raise RuntimeError(f"Request failed: {url}")

    def _api_headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.settings.hh_user_agent,
            "HH-User-Agent": self.settings.hh_user_agent,
            "Accept": "application/json",
        }

    def _html_headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/140.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.7",
        }

    @staticmethod
    def _retry_delay(response: httpx.Response, attempt: int) -> float:
        value = response.headers.get("Retry-After")
        if value:
            try:
                return min(float(value), 30.0)
            except ValueError:
                try:
                    retry_at = parsedate_to_datetime(value)
                    server_time = parsedate_to_datetime(response.headers["Date"])
                    return max(0.0, min((retry_at - server_time).total_seconds(), 30.0))
                except (ValueError, KeyError, TypeError):
                    pass
        return float(2**attempt)

    async def get_vacancy(self, vacancy_id: str) -> tuple[NormalizedVacancy, dict[str, Any]]:
        api_url = f"https://api.hh.ru/vacancies/{vacancy_id}"
        if self._api_available:
            try:
                response = await self._request(api_url)
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("HH API returned a non-object")
                logger.info("Vacancy fetched id=%s source=api", vacancy_id)
                return normalize_api_vacancy(payload), payload
            except VacancyNotFoundError:
                raise
            except Exception as exc:
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {
                    401,
                    403,
                }:
                    self._api_available = False
                logger.warning("HH API failed id=%s error=%s; using HTML fallback", vacancy_id, exc)

        page_url = f"https://hh.ru/vacancy/{vacancy_id}"
        response = await self._request(page_url, html=True)
        normalized = normalize_html_vacancy(vacancy_id, response.text)
        raw = {
            "source": "html",
            "normalized": normalized.model_dump(mode="json"),
            "html_excerpt": response.text[:100_000],
        }
        logger.info("Vacancy fetched id=%s source=html", vacancy_id)
        return normalized, raw
