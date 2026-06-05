from __future__ import annotations

import html
import re
from typing import Any

from chinesenotes_alignment import merge_logical_lines
from ingest_chinesenotes_work import PUBLIC_DOMAIN_RE, TRANSLATOR_ATTRIBUTION_RE
from text_quality import find_suspicious_ocr_tokens

HTML_TAG_RE = re.compile(r"<[^>]+>")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
ASCII_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'’-]{1,}\b")
SHORT_HEADING_RE = re.compile(r"^[A-Z][A-Za-z0-9 .,'’()/-]{1,48}:$")
FOOTNOTE_RE = re.compile(r"^\d+\.\s+.*(?:Originally read|Corrected to|Original text)", re.IGNORECASE)
NOTICE_MARKERS = (
    "source: chinese text project",
    "english translation",
    "sacred books of the east",
)
COMMENTARY_MARKERS = (
    "originally read:",
    "corrected to:",
)


def strip_html_markup(text: str) -> str:
    return html.unescape(HTML_TAG_RE.sub("", text)).strip()


def contains_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text))


def contains_english(text: str) -> bool:
    return len(ASCII_WORD_RE.findall(text)) >= 2


def parse_liji_bilingual_text(raw_text: str, displayed_title: str) -> dict[str, Any]:
    chinese_lines: list[str] = []
    english_lines: list[str] = []
    translator_notes: list[str] = []
    rights_notes: list[str] = []
    excluded_title_lines: list[str] = []
    excluded_heading_lines: list[str] = []
    excluded_notice_lines: list[str] = []
    excluded_footnote_lines: list[str] = []
    uncategorized_lines: list[str] = []

    for line_index, raw_line in enumerate(raw_text.splitlines()):
        line = strip_html_markup(raw_line)
        if not line:
            continue
        if line_index == 0 and contains_cjk(line) and contains_english(line):
            excluded_title_lines.append(line)
            continue
        if line_index == 0 and line == displayed_title.strip():
            excluded_title_lines.append(line)
            continue
        if TRANSLATOR_ATTRIBUTION_RE.search(line):
            translator_notes.append(line)
            excluded_notice_lines.append(line)
            continue
        if PUBLIC_DOMAIN_RE.search(line):
            rights_notes.append(line)
            excluded_notice_lines.append(line)
            continue
        if FOOTNOTE_RE.match(line):
            excluded_footnote_lines.append(line)
            continue
        if SHORT_HEADING_RE.match(line):
            excluded_heading_lines.append(line)
            continue
        has_cjk = contains_cjk(line)
        has_english = contains_english(line)
        if has_cjk and not has_english:
            chinese_lines.append(line)
            continue
        if has_english and not has_cjk:
            english_lines.append(line)
            continue
        uncategorized_lines.append(line)

    chinese_blocks = merge_logical_lines(chinese_lines, "zh")
    english_blocks = merge_logical_lines(english_lines, "en")
    return {
        "chinese_blocks": chinese_blocks,
        "english_blocks": english_blocks,
        "translator_notes": sorted(dict.fromkeys(translator_notes)),
        "rights_notes": sorted(dict.fromkeys(rights_notes)),
        "excluded_title_lines": excluded_title_lines,
        "excluded_heading_lines": excluded_heading_lines,
        "excluded_notice_lines": excluded_notice_lines,
        "excluded_footnote_lines": excluded_footnote_lines,
        "uncategorized_lines": uncategorized_lines,
    }


def detect_liji_leakage_issues(text: str) -> list[dict[str, str]]:
    stripped = " ".join(text.split())
    lowered = stripped.casefold()
    issues: list[dict[str, str]] = []
    if SHORT_HEADING_RE.fullmatch(stripped):
        issues.append({"token": stripped, "issue_type": "heading_residue"})
    for marker in NOTICE_MARKERS:
        if marker in lowered:
            issues.append({"token": marker, "issue_type": "notice_residue"})
    for marker in COMMENTARY_MARKERS:
        if marker in lowered:
            issues.append({"token": marker, "issue_type": "footnote_residue"})
    if FOOTNOTE_RE.match(stripped):
        issues.append({"token": stripped, "issue_type": "footnote_residue"})
    return issues


def detect_liji_ocr_issues(text: str) -> list[dict[str, str]]:
    return find_suspicious_ocr_tokens(text)
