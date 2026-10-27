from __future__ import annotations

import re

MIN_LENGTH = 400
MAX_LENGTH = 950

SALUTATION_PATTERN = re.compile(
    r"^(?:здравствуйте|добрый день|hello|dear hiring manager)\s*[!,.]",
    re.IGNORECASE,
)
NEXT_STEP_PATTERN = re.compile(
    r"(?:созвон|встреч|интервью|call|meeting|interview|conversation)",
    re.IGNORECASE,
)
BULLET_PATTERN = re.compile(r"(?m)^\s*(?:[-*•]|\d+[.)])\s+")
PLACEHOLDER_PATTERN = re.compile(r"\[[^\]\n]{1,80}\]")
CJK_PATTERN = re.compile(r"[\u3400-\u9fff]")
SIGN_OFF_PATTERN = re.compile(
    r"(?im)^\s*(?:с\s+уважением|best regards|kind regards|sincerely)[,!]?\s*$"
)
WEAK_OPENING_PATTERN = re.compile(
    r"^(?:"
    r"я\s+(?:хочу|хотел(?:\w*)|пишу|откликаюсь|рассматриваю)|"
    r"меня\s+(?:заинтересовал|привлек)|"
    r"мне\s+(?:интерес|близк)|"
    r"i\s+(?:am writing|would like|want to apply)|"
    r"i(?:'m| am)\s+(?:interested|excited)"
    r")",
    re.IGNORECASE,
)
RECRUITER_VOICE_PATTERNS = (
    re.compile(r"мы\s+рассмотрели\s+ваш", re.IGNORECASE),
    re.compile(r"приглашаем\s+вас", re.IGNORECASE),
    re.compile(r"we\s+(?:have\s+)?reviewed\s+your", re.IGNORECASE),
    re.compile(r"we(?:'d|\s+would)\s+like\s+to\s+invite\s+you", re.IGNORECASE),
)
FORBIDDEN_PATTERNS = (
    re.compile(r"идеально\s+(?:подхожу|соответств)", re.IGNORECASE),
    re.compile(r"уникальн\w*\s+набор\w*\s+навык", re.IGNORECASE),
    re.compile(r"динамично\s+развивающ", re.IGNORECASE),
    re.compile(r"чрезвычайно\s+впечатл", re.IGNORECASE),
    re.compile(r"богат\w*\s+опыт", re.IGNORECASE),
    re.compile(r"стремлюсь\s+к\s+развитию", re.IGNORECASE),
    re.compile(r"(?:рассматриваю|интересует)\s+(?:вашу\s+)?позици", re.IGNORECASE),
    re.compile(r"меня\s+заинтересовала\s+позици", re.IGNORECASE),
    re.compile(r"(?:интересна|привлекает)\s+задача", re.IGNORECASE),
    re.compile(r"этот\s+опыт\s+(?:поможет|пригодится|применим)", re.IGNORECASE),
    re.compile(r"могу\s+взять\s+на\s+себя", re.IGNORECASE),
    re.compile(r"буду\s+рад\w*\s+обсудить", re.IGNORECASE),
    re.compile(r"сво(?:й|его|ём)\s+вклад", re.IGNORECASE),
    re.compile(r"у\s+меня\s+(?:пока\s+)?нет\s+опыта", re.IGNORECASE),
    re.compile(r"не\s+имею\s+опыта", re.IGNORECASE),
    re.compile(r"i am writing to express my interest", re.IGNORECASE),
    re.compile(r"unique blend of skills", re.IGNORECASE),
    re.compile(r"perfect(?:ly)?\s+(?:fit|match)", re.IGNORECASE),
    re.compile(r"dynamic(?:ally)?\s+(?:growing|developing)\s+company", re.IGNORECASE),
    re.compile(r"i (?:do not|don't) have experience", re.IGNORECASE),
    re.compile(r"i lack experience", re.IGNORECASE),
    re.compile(r"this experience will help", re.IGNORECASE),
)


def cover_letter_issues(value: str) -> list[str]:
    text = value.strip()
    issues: list[str] = []
    length = len(text)
    if length < MIN_LENGTH or length > MAX_LENGTH:
        issues.append(f"length must be {MIN_LENGTH}-{MAX_LENGTH} characters; got {length}")
    if not SALUTATION_PATTERN.search(text):
        issues.append("must start with a neutral greeting")

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not 2 <= len(paragraphs) <= 3:
        issues.append("must contain 2-3 short paragraphs")
    if BULLET_PATTERN.search(text):
        issues.append("must use prose paragraphs, not a list")
    if not paragraphs or not NEXT_STEP_PATTERN.search(paragraphs[-1]):
        issues.append("last paragraph must propose a concrete call, meeting, or interview")
    if PLACEHOLDER_PATTERN.search(text):
        issues.append("contains an unfilled placeholder")
    if CJK_PATTERN.search(text):
        issues.append("contains unexpected CJK characters")
    if SIGN_OFF_PATTERN.search(text):
        issues.append("contains an unnecessary sign-off")

    content = SALUTATION_PATTERN.sub("", text, count=1).lstrip()
    first_sentence = re.split(r"(?<=[.!?])\s+", content, maxsplit=1)[0]
    if WEAK_OPENING_PATTERN.search(first_sentence):
        issues.append("first sentence announces interest instead of leading with evidence")

    for pattern in RECRUITER_VOICE_PATTERNS:
        if pattern.search(text):
            issues.append("is written from the recruiter's perspective")
            break

    for pattern in FORBIDDEN_PATTERNS:
        if pattern.search(text):
            issues.append("contains a generic or unsafe stock phrase")
            break

    return issues


def validate_cover_letter(value: str) -> None:
    issues = cover_letter_issues(value)
    if issues:
        raise ValueError(f"Cover letter quality check failed: {'; '.join(issues)}")
