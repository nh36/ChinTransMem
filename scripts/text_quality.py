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


def detect_probable_ocr_corruption(text: str) -> list[str]:
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
    return issues


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
