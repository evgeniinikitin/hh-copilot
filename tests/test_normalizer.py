from app.hh.normalizer import extract_vacancy_id, html_to_text, normalize_api_vacancy


def test_html_to_readable_text() -> None:
    assert html_to_text("<p>Hello <b>world</b></p><script>bad()</script>") == "Hello\nworld"


def test_missing_salary_and_skills() -> None:
    vacancy = normalize_api_vacancy(
        {"id": "123", "name": "Product Manager", "description": "<p>Build things</p>"}
    )
    assert vacancy.salary_from is None
    assert vacancy.key_skills == []
    assert vacancy.description == "Build things"


def test_extract_vacancy_id() -> None:
    assert extract_vacancy_id("https://spb.hh.ru/vacancy/123456?hhtmFrom=favorite") == "123456"
