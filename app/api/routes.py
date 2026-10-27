from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from app.api.schemas import (
    ProcessBaselineRequest,
    ProcessBaselineResponse,
    StatusResponse,
    SyncRequest,
    SyncResponse,
    VacancyRequest,
)
from app.hh.normalizer import extract_vacancy_id

router = APIRouter()


def _container(request: Request) -> Any:
    return request.app.state.container


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/api/v1/vacancies")
async def add_vacancy(payload: VacancyRequest, request: Request) -> dict[str, object]:
    container = _container(request)
    vacancy_id = extract_vacancy_id(payload.vacancy_id)
    queued, status = container.sync_service.enqueue_instant(vacancy_id, payload.source)
    return {"vacancy_id": vacancy_id, "queued": queued, "status": status}


@router.post("/api/v1/sync", response_model=SyncResponse)
async def sync(payload: SyncRequest, request: Request) -> SyncResponse:
    result = await _container(request).sync_service.sync(payload.vacancy_ids, payload.source)
    return SyncResponse(**result.__dict__)


@router.get("/api/v1/status", response_model=StatusResponse)
async def status(request: Request) -> StatusResponse:
    stats = _container(request).repository.stats()
    return StatusResponse(**stats)


@router.post("/api/v1/process-baseline", response_model=ProcessBaselineResponse)
async def process_baseline(
    payload: ProcessBaselineRequest, request: Request
) -> ProcessBaselineResponse:
    ids = _container(request).repository.process_baseline(payload.limit)
    return ProcessBaselineResponse(queued=len(ids), vacancy_ids=ids)
