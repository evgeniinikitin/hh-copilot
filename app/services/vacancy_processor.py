from __future__ import annotations

import logging

from app.ai.analyzer import VacancyAnalyzer
from app.ai.schemas import VacancyAnalysis
from app.database.models import VacancyStatus
from app.database.repository import VacancyRepository
from app.hh.public_client import HHPublicClient
from app.hh.schemas import NormalizedVacancy
from app.telegram.notifier import TelegramError, TelegramNotifier

logger = logging.getLogger("processor")


class VacancyProcessor:
    def __init__(
        self,
        repository: VacancyRepository,
        hh_client: HHPublicClient,
        analyzer: VacancyAnalyzer,
        notifier: TelegramNotifier,
    ) -> None:
        self.repository = repository
        self.hh_client = hh_client
        self.analyzer = analyzer
        self.notifier = notifier

    async def process(self, vacancy_id: str) -> None:
        claimed = self.repository.transition(
            vacancy_id,
            VacancyStatus.PROCESSING,
            expected={VacancyStatus.QUEUED},
            fields={"error_message": None},
        )
        if not claimed:
            return
        try:
            vacancy, raw = await self.hh_client.get_vacancy(vacancy_id)
            self.repository.transition(
                vacancy_id,
                VacancyStatus.FETCHED,
                expected={VacancyStatus.PROCESSING},
                fields={
                    "title": vacancy.title,
                    "company_name": vacancy.company_name,
                    "alternate_url": vacancy.alternate_url,
                    "raw_vacancy_json": raw,
                },
            )
            analysis = await self.analyzer.analyze(vacancy)
            self.repository.transition(
                vacancy_id,
                VacancyStatus.ANALYZED,
                expected={VacancyStatus.FETCHED},
                fields={
                    "match_score": analysis.match_score,
                    "recommendation": analysis.recommendation,
                    "cover_letter": analysis.cover_letter,
                    "analysis_json": analysis.model_dump(mode="json"),
                },
            )
            await self.notify(vacancy_id)
        except TelegramError as exc:
            logger.warning("Telegram pending id=%s error=%s", vacancy_id, exc)
        except Exception as exc:
            logger.exception("Vacancy processing failed id=%s", vacancy_id)
            self.repository.mark_failed(vacancy_id, str(exc))

    async def notify(self, vacancy_id: str) -> None:
        row = self.repository.get(vacancy_id)
        if row is None or row.status != VacancyStatus.ANALYZED.value:
            return
        if not row.analysis_json or not row.raw_vacancy_json:
            self.repository.mark_failed(vacancy_id, "Stored analysis or vacancy data is missing")
            return
        analysis = VacancyAnalysis.model_validate(row.analysis_json)
        vacancy = self._vacancy_from_row(row.raw_vacancy_json, vacancy_id)
        await self.notifier.send_analysis(vacancy, analysis)
        self.repository.transition(
            vacancy_id,
            VacancyStatus.NOTIFIED,
            expected={VacancyStatus.ANALYZED},
        )
        logger.info("Notification sent id=%s", vacancy_id)

    @staticmethod
    def _vacancy_from_row(raw: dict[str, object], vacancy_id: str) -> NormalizedVacancy:
        if raw.get("source") == "html":
            normalized = raw.get("normalized")
            if not isinstance(normalized, dict):
                raise ValueError("Stored normalized HTML fallback vacancy is missing")
            return NormalizedVacancy.model_validate(normalized)
        from app.hh.normalizer import normalize_api_vacancy

        return normalize_api_vacancy(raw)
