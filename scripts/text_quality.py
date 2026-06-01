from __future__ import annotations

import re

INTERNAL_CAPITAL_SUBSTITUTION_RE = re.compile(r"\b[a-z]{2,}[A-Z][a-z]{2,}\b")
BROKEN_HYPHENATION_RE = re.compile(r"\b[a-z]{2,}-\s+[A-Za-z]{2,}\b")
INTERNAL_PUNCTUATION_RE = re.compile(r"\b[A-Za-z]{2,}[,;:_^][A-Za-z]{2,}\b")
DIGIT_FOR_LETTER_RE = re.compile(r"\b1\s+[a-z]{2,}\b|\b[A-Za-z]+\d[A-Za-z]+\b")
BROKEN_QUOTE_FRAGMENT_RE = re.compile(r"(^|[\s(])[\"“][^\"”]{0,40}$|^[^\"“]{0,40}[\"”]([)\s]|$)")
OCR_RESIDUE_RE = re.compile(r"[_^]| {2,}| \u00ad ")
TRAILING_FRAGMENT_RE = re.compile(r"[A-Za-z][,:;]?$")
LEADING_FRAGMENT_RE = re.compile(r"^[a-z].+")
SENTENCE_END_RE = re.compile(r"[.!?'\"]$")
OCR_TOKEN_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9'/<>\-:.’]*[A-Za-z0-9]\b")
MIXED_CAPITAL_TOKEN_RE = re.compile(r"\b(?:[A-Z][a-z]+[A-Z][a-z]+|[a-z]+[A-Z][a-z]+)\b")


def find_suspicious_ocr_tokens(
    text: str,
    *,
    allowed_tokens: set[str] | frozenset[str] | None = None,
    suspicious_exact_tokens: set[str] | frozenset[str] | None = None,
    suspicious_hyphenated_tokens: set[str] | frozenset[str] | None = None,
) -> list[dict[str, str]]:
    allowed = frozenset(token.casefold() for token in (allowed_tokens or set()))
    exact = frozenset(token.casefold() for token in (suspicious_exact_tokens or set()))
    suspicious_hyphenated = frozenset(token.casefold() for token in (suspicious_hyphenated_tokens or set()))
    issues: list[dict[str, str]] = []
    for match in OCR_TOKEN_RE.finditer(text):
        token = match.group(0)
        lowered = token.casefold()
        if lowered in allowed:
            continue
        issue_type: str | None = None
        if lowered in exact:
            issue_type = "known_bad_form"
        elif lowered in suspicious_hyphenated:
            issue_type = "broken_hyphenation"
        elif "/" in token or ">" in token or "<" in token:
            issue_type = "internal_punctuation"
        elif "oflfl" in lowered:
            issue_type = "ligature_confusion"
        elif DIGIT_FOR_LETTER_RE.fullmatch(token):
            issue_type = "digit_for_letter_substitution"
        elif MIXED_CAPITAL_TOKEN_RE.fullmatch(token) or INTERNAL_CAPITAL_SUBSTITUTION_RE.fullmatch(token):
            issue_type = "internal_capital_substitution"
        if issue_type is not None:
            issues.append({"token": token, "issue_type": issue_type})
    return issues


def detect_probable_ocr_corruption(
    text: str,
    *,
    allowed_tokens: set[str] | frozenset[str] | None = None,
    suspicious_exact_tokens: set[str] | frozenset[str] | None = None,
    suspicious_hyphenated_tokens: set[str] | frozenset[str] | None = None,
) -> list[str]:
    issues: list[str] = []
    if INTERNAL_CAPITAL_SUBSTITUTION_RE.search(text):
        issues.append("internal_capital_substitution")
    if BROKEN_HYPHENATION_RE.search(text):
        issues.append("broken_hyphenation")
    if INTERNAL_PUNCTUATION_RE.search(text):
        issues.append("internal_punctuation")
    if DIGIT_FOR_LETTER_RE.search(text):
        issues.append("digit_for_letter_substitution")
    if BROKEN_QUOTE_FRAGMENT_RE.search(text):
        issues.append("broken_quote_fragment")
    if OCR_RESIDUE_RE.search(text):
        issues.append("ocr_residue")
    issues.extend(
        issue["issue_type"]
        for issue in find_suspicious_ocr_tokens(
            text,
            allowed_tokens=allowed_tokens,
            suspicious_exact_tokens=suspicious_exact_tokens,
            suspicious_hyphenated_tokens=suspicious_hyphenated_tokens,
        )
    )
    return sorted(set(issues))


def has_probable_trailing_fragment(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if SENTENCE_END_RE.search(stripped):
        return False
    return bool(TRAILING_FRAGMENT_RE.search(stripped))


def has_probable_leading_fragment(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    return bool(LEADING_FRAGMENT_RE.match(stripped))
