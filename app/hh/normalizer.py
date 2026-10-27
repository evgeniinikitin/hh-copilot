from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from bs4 import BeautifulSoup

from app.hh.schemas import NormalizedVacancy

VACANCY_URL_PATTERN = re.compile(r"(?:https?://(?:[a-z0-9-]+\.)?hh\.ru)?/vacancy/(\d+)", re.I)


def extract_vacancy_id(value: str) -> str:
    value = value.strip()
    if value.isdigit():
        return value
    match = VACANCY_URL_PATTERN.search(value)
    if not match:
        raise ValueError(f"Could not extract HH vacancy id from {value!r}")
    return match.group(1)


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text("\n", strip=True)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _nested_name(value: Any) -> str | None:
    return value.get("name") if isinstance(value, dict) else None


def normalize_api_vacancy(payload: dict[str, Any]) -> NormalizedVacancy:
    salary: dict[str, Any] = payload["salary"] if isinstance(payload.get("salary"), dict) else {}
    skills: list[Any] = payload.get("key_skills") or []
    roles: list[Any] = payload.get("professional_roles") or []
    return NormalizedVacancy(
        id=str(payload["id"]),
        title=str(payload.get("name") or "Без названия"),
        company_name=_nested_name(payload.get("employer")),
        description=html_to_text(str(payload.get("description") or "")),
        salary_from=salary.get("from"),
        salary_to=salary.get("to"),
        salary_currency=salary.get("currency"),
        area=_nested_name(payload.get("area")),
        experience=_nested_name(payload.get("experience")),
        employment=_nested_name(payload.get("employment")),
        schedule=_nested_name(payload.get("schedule")),
        key_skills=[
            str(item["name"]) for item in skills if isinstance(item, dict) and item.get("name")
        ],
        professional_roles=[
            str(item["name"]) for item in roles if isinstance(item, dict) and item.get("name")
        ],
        alternate_url=payload.get("alternate_url"),
        published_at=payload.get("published_at"),
    )


def normalize_html_vacancy(vacancy_id: str, html: str) -> NormalizedVacancy:
    soup = BeautifulSoup(html, "html.parser")

    def content(selector: str, attr: str = "content") -> str | None:
        node = soup.select_one(selector)
        value = node.get(attr) if node else None
        return str(value).strip() if value else None

    title_node = soup.select_one("[data-qa='vacancy-title'], h1")
    company_node = soup.select_one(
        "[data-qa='vacancy-company-name'], [data-qa='vacancy-company-name'] span"
    )
    description_node = soup.select_one("[data-qa='vacancy-description']")
    title = (
        title_node.get_text(" ", strip=True)
        if title_node
        else content("meta[property='og:title']") or "Без названия"
    )
    description = html_to_text(str(description_node) if description_node else "")
    if not description:
        description = content("meta[name='description']") or ""
    canonical = content("link[rel='canonical']", "href") or f"https://hh.ru/vacancy/{vacancy_id}"
    published_raw = content("meta[itemprop='datePosted']")
    published_at: datetime | None = None
    if published_raw:
        try:
            published_at = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
        except ValueError:
            pass
    return NormalizedVacancy(
        id=vacancy_id,
        title=title,
        company_name=company_node.get_text(" ", strip=True) if company_node else None,
        description=description,
        alternate_url=canonical,
        published_at=published_at,
    )
