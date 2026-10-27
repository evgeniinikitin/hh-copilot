from __future__ import annotations

from app.hh.normalizer import extract_vacancy_id


def normalize_vacancy_ids(values: list[str]) -> set[str]:
    return {extract_vacancy_id(value) for value in values}
