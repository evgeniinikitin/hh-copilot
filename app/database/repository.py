from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.database.models import AppState, Vacancy, VacancyStatus, utcnow


class VacancyRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def add_if_absent(
        self, vacancy_id: str, source: str, status: VacancyStatus
    ) -> tuple[Vacancy, bool]:
        with self.session_factory() as session:
            existing = session.scalar(select(Vacancy).where(Vacancy.hh_vacancy_id == vacancy_id))
            if existing is not None:
                return existing, False
            vacancy = Vacancy(
                hh_vacancy_id=vacancy_id,
                source=source,
                status=status.value,
                queued_at=utcnow() if status is VacancyStatus.QUEUED else None,
            )
            session.add(vacancy)
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                existing = session.scalar(
                    select(Vacancy).where(Vacancy.hh_vacancy_id == vacancy_id)
                )
                if existing is None:
                    raise
                return existing, False
            session.refresh(vacancy)
            return vacancy, True

    def get(self, vacancy_id: str) -> Vacancy | None:
        with self.session_factory() as session:
            return session.scalar(select(Vacancy).where(Vacancy.hh_vacancy_id == vacancy_id))

    def known_ids(self) -> set[str]:
        with self.session_factory() as session:
            return set(session.scalars(select(Vacancy.hh_vacancy_id)).all())

    def ids_with_status(self, status: VacancyStatus) -> set[str]:
        with self.session_factory() as session:
            return set(
                session.scalars(
                    select(Vacancy.hh_vacancy_id).where(Vacancy.status == status.value)
                ).all()
            )

    def get_state(self, key: str) -> str | None:
        with self.session_factory() as session:
            row = session.get(AppState, key)
            return row.value if row else None

    def set_state(self, key: str, value: str) -> None:
        with self.session_factory() as session:
            row = session.get(AppState, key)
            if row:
                row.value = value
            else:
                session.add(AppState(key=key, value=value))
            session.commit()

    def queue_existing(self, vacancy_id: str, source: str | None = None) -> bool:
        with self.session_factory() as session:
            row = session.scalar(select(Vacancy).where(Vacancy.hh_vacancy_id == vacancy_id))
            if row is None:
                return False
            if row.status not in {
                VacancyStatus.BASELINE.value,
                VacancyStatus.DETECTED.value,
                VacancyStatus.FAILED.value,
            }:
                return False
            row.status = VacancyStatus.QUEUED.value
            row.queued_at = utcnow()
            row.error_message = None
            row.retry_count = 0
            if source:
                row.source = source
            session.commit()
            return True

    def process_baseline(self, limit: int) -> list[str]:
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(Vacancy)
                    .where(Vacancy.status == VacancyStatus.BASELINE.value)
                    .order_by(Vacancy.detected_at.desc(), Vacancy.id.desc())
                    .limit(limit)
                )
            )
            now = utcnow()
            for row in rows:
                row.status = VacancyStatus.QUEUED.value
                row.queued_at = now
            session.commit()
            return [row.hh_vacancy_id for row in rows]

    def next_queued_ids(self, limit: int) -> list[str]:
        with self.session_factory() as session:
            return list(
                session.scalars(
                    select(Vacancy.hh_vacancy_id)
                    .where(Vacancy.status == VacancyStatus.QUEUED.value)
                    .order_by(Vacancy.queued_at.asc(), Vacancy.id.asc())
                    .limit(limit)
                )
            )

    def analyzed_unnotified_ids(self, limit: int) -> list[str]:
        with self.session_factory() as session:
            return list(
                session.scalars(
                    select(Vacancy.hh_vacancy_id)
                    .where(Vacancy.status == VacancyStatus.ANALYZED.value)
                    .order_by(Vacancy.analyzed_at.asc())
                    .limit(limit)
                )
            )

    def transition(
        self,
        vacancy_id: str,
        status: VacancyStatus,
        *,
        expected: set[VacancyStatus] | None = None,
        fields: dict[str, Any] | None = None,
    ) -> bool:
        values: dict[str, Any] = {"status": status.value, "updated_at": utcnow()}
        values.update(fields or {})
        timestamp_fields = {
            VacancyStatus.QUEUED: "queued_at",
            VacancyStatus.PROCESSING: "processing_started_at",
            VacancyStatus.FETCHED: "fetched_at",
            VacancyStatus.ANALYZED: "analyzed_at",
            VacancyStatus.NOTIFIED: "notified_at",
        }
        if status in timestamp_fields:
            values[timestamp_fields[status]] = utcnow()
        with self.session_factory() as session:
            statement = update(Vacancy).where(Vacancy.hh_vacancy_id == vacancy_id)
            if expected:
                statement = statement.where(Vacancy.status.in_([item.value for item in expected]))
            result = session.execute(statement.values(**values))
            session.commit()
            return bool(getattr(result, "rowcount", 0))

    def mark_failed(self, vacancy_id: str, message: str) -> None:
        with self.session_factory() as session:
            row = session.scalar(select(Vacancy).where(Vacancy.hh_vacancy_id == vacancy_id))
            if row is None:
                return
            row.status = VacancyStatus.FAILED.value
            row.error_message = message[:4000]
            row.retry_count += 1
            session.commit()

    def recover(self, stale_seconds: int, max_retries: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(seconds=stale_seconds)
        with self.session_factory() as session:
            rows = list(
                session.scalars(
                    select(Vacancy).where(
                        (Vacancy.status == VacancyStatus.FETCHED.value)
                        | (
                            (Vacancy.status == VacancyStatus.PROCESSING.value)
                            & (Vacancy.processing_started_at < cutoff)
                        )
                    )
                )
            )
            recovered = 0
            for row in rows:
                if row.retry_count >= max_retries:
                    row.status = VacancyStatus.FAILED.value
                    row.error_message = "Processing became stale too many times"
                else:
                    row.status = VacancyStatus.QUEUED.value
                    row.queued_at = utcnow()
                    row.retry_count += 1
                    row.error_message = "Recovered interrupted processing job"
                    recovered += 1
            session.commit()
            return recovered

    def stats(self) -> dict[str, int | str | None]:
        with self.session_factory() as session:
            count_rows = session.execute(
                select(Vacancy.status, func.count(Vacancy.id)).group_by(Vacancy.status)
            ).all()
            counts: dict[str, int] = {str(status): int(count) for status, count in count_rows}
            total = int(session.scalar(select(func.count(Vacancy.id))) or 0)
            processed = sum(
                int(counts.get(status.value, 0))
                for status in (VacancyStatus.ANALYZED, VacancyStatus.NOTIFIED)
            )
        return {
            "status": "running",
            "known_total": total,
            "queue_size": int(counts.get(VacancyStatus.QUEUED.value, 0)),
            "processing": int(counts.get(VacancyStatus.PROCESSING.value, 0))
            + int(counts.get(VacancyStatus.FETCHED.value, 0)),
            "processed_total": processed,
            "baseline_total": int(counts.get(VacancyStatus.BASELINE.value, 0)),
            "last_sync_at": self.get_state("last_sync_at"),
        }

    def count(self) -> int:
        with self.session_factory() as session:
            return int(session.scalar(select(func.count(Vacancy.id))) or 0)
