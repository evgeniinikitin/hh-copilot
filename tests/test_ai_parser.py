import json

import pytest

from app.ai.analyzer import parse_analysis
from app.ai.cover_letter import cover_letter_issues

# Synthetic fixture: the project, candidate experience, and outcome are invented for this test.
VALID_LETTER = (
    "Здравствуйте! В демонстрационном проекте я изучил, как пользователи выбирают тариф, "
    "сопоставил их вопросы с шагами оформления и подготовил несколько вариантов нового сценария. "
    "Команда проверила варианты на тестовых задачах и выбрала тот, в котором условия понятнее.\n\n"
    "Для продукта, который растёт через пользовательские сценарии и монетизацию, такая связка "
    "исследования и экономики даёт практическую основу для выбора гипотез.\n\n"
    "Предлагаю короткий созвон: обсудим, какой пользовательский сценарий команда считает "
    "главной точкой роста и как проверяет его влияние на экономику продукта."
)
VALID_PAYLOAD = {
    "match_score": 78,
    "recommendation": "apply",
    "summary": "Хорошее совпадение",
    "strengths": ["Product management"],
    "gaps": ["SQL"],
    "relevant_experience": ["Demonstration product"],
    "cover_letter": VALID_LETTER,
}
VALID = json.dumps(VALID_PAYLOAD, ensure_ascii=False)


def test_valid_json() -> None:
    assert parse_analysis(VALID).match_score == 78


def test_fenced_json() -> None:
    assert parse_analysis(f"```json\n{VALID}\n```").recommendation == "apply"


@pytest.mark.parametrize("value", ["not json", "{}", VALID.replace("78", "101")])
def test_invalid_output(value: str) -> None:
    with pytest.raises(ValueError):
        parse_analysis(value)


@pytest.mark.parametrize(
    "letter",
    [
        "Здравствуйте! Слишком коротко.",
        VALID_LETTER.replace("такая связка", "мой уникальный набор навыков"),
        VALID_LETTER.replace(
            "Предлагаю короткий созвон: обсудим, какой пользовательский сценарий "
            "команда считает главной точкой роста "
            "и как проверяет его влияние на экономику продукта.",
            "У меня пока нет опыта в этой сфере. ",
        ),
        VALID_LETTER.replace("Предлагаю короткий созвон: обсудим", "Буду рад обсудить"),
        VALID_LETTER.replace("Для продукта", "Рассматриваю позицию Product Manager. Для продукта"),
        VALID_LETTER.replace("Предлагаю короткий созвон: обсудим", "Предлагаю обсудить"),
    ],
)
def test_cover_letter_quality_is_validated(letter: str) -> None:
    payload = {**VALID_PAYLOAD, "cover_letter": letter}
    with pytest.raises(ValueError):
        parse_analysis(json.dumps(payload, ensure_ascii=False))


@pytest.mark.parametrize(
    "addition, expected_issue",
    [
        (" [Ваше имя]", "placeholder"),
        (" 你好", "CJK"),
        ("\nС уважением", "sign-off"),
        (" Приглашаем вас на интервью.", "recruiter"),
    ],
)
def test_mechanical_defects_are_reported(addition: str, expected_issue: str) -> None:
    issues = cover_letter_issues(VALID_LETTER + addition)
    assert any(expected_issue in issue for issue in issues)
