from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Any

from common import (
    DOCUMENTATION_DIR,
    QC_REPORTS_DIR,
    REPO_ROOT,
    corpus_export_paths,
    load_json_compatible_yaml,
    load_work_manifest,
    read_jsonl,
)
from shijing_verification import (
    VERIFIED_EXPORT_STATUSES,
    build_verification_index,
    load_shijing_verification_ledger,
    verification_entry_is_exportable,
    verification_entry_is_verified,
)

WORK_ID = "shijing"
QUALITY_JSON_PATH = QC_REPORTS_DIR / "shijing__completion_quality.json"
QUALITY_MARKDOWN_PATH = DOCUMENTATION_DIR / "shijing_completion_quality.md"
SPOTCHECK_PACKET_PATH = DOCUMENTATION_DIR / "shijing_spotcheck_packet.md"
UNRESOLVED_WITNESS_REPORT_PATH = DOCUMENTATION_DIR / "shijing_unresolved_witness_report.md"
QUALITY_OVERRIDES_PATH = REPO_ROOT / "metadata" / "shijing_quality_overrides.yml"
DETAILED_QUEUE_SUBDIVISIONS: tuple[tuple[str, str], ...] = (
    ("國風", "召南"),
    ("國風", "邶風"),
    ("國風", "鄘風"),
    ("國風", "衛風"),
    ("國風", "王風"),
    ("國風", "鄭風"),
    ("國風", "齊風"),
    ("國風", "魏風"),
    ("國風", "唐風"),
    ("國風", "陳風"),
    ("國風", "秦風"),
    ("國風", "豳風"),
    ("國風", "曹風"),
    ("國風", "檜風"),
)
GENERIC_UNVERIFIED_NOTE = "Public-domain witness located, but the English text is not yet verified clean enough for export."

ENGLISH_WORD_RE = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)?")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
QUALITY_MARKER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("wikisource_css", re.compile(r"\.mw-parser-output|wst-anchor:target", re.I)),
    ("heading_marker", re.compile(r"\b(?:ODES OF|THE SHE KING|SHE KING|Ode \d+|St(?:anza)?\.?\s*\d+|Book \d+)\b", re.I)),
    ("page_furniture", re.compile(r"\b(?:PART\s+[IVXLC]+|Page\s+\d+|Vol\.?\s+[IVXLC]+)\b", re.I)),
    ("footnote_marker", re.compile(r"\b(?:footnote|footnotes|note\s+\d+)\b|\[\d+\]|\(\d+\)")),
    ("bracketed_editorial_note", re.compile(r"\[(?:[^\]]+\s+){2,}[^\]]+\]")),
    ("commentary_marker", re.compile(r"\b(?:commentary|preface|appendix|Mao|Ying-ta|Choo He|Zhu Xi)\b", re.I)),
    ("ocr_noise", re.compile(r"[〇^]|T4ANG|SI1AOU|PAIIT|thcde|tliere|K!ang|mu\.'-t|wiih|Tliere", re.I)),
)

OCR_SANITY_PATTERNS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "digit_letter_confusion",
        "digit/letter confusion inside an English token",
        re.compile(r"(?i)\b(?:[A-Za-z]+\d+[A-Za-z]*|\d+[A-Za-z][A-Za-z]*)\b"),
    ),
    (
        "zero_vocative_confusion",
        "zero used where an alphabetic O is expected",
        re.compile(r"\b0\s+[A-Z][a-z]+"),
    ),
    (
        "brace_artifact",
        "brace artifact embedded in English text",
        re.compile(r"[{}]"),
    ),
    (
        "backslash_artifact",
        "backslash artifact embedded in English text",
        re.compile(r"\\"),
    ),
    (
        "caret_artifact",
        "caret artifact embedded in English text",
        re.compile(r"\^"),
    ),
    (
        "bullet_artifact",
        "bullet or middle-dot artifact embedded in English text",
        re.compile(r"[•·◦▪●]"),
    ),
    (
        "paren_digit_intraword_artifact",
        "closing parenthesis/digit OCR damage inside an English word",
        re.compile(r"(?i)\b[A-Za-z]+\)[0-9A-Za-z]+\b"),
    ),
    (
        "trailing_j_artifact",
        "improbable trailing j left on an English word",
        re.compile(r"(?i)\b[a-z]{3,}j\b"),
    ),
    (
        "apostrophe_vw_artifact",
        "apostrophe-v/w OCR damage in an English word",
        re.compile(r"(?i)\b[A-Za-z]+['’][vw]\b"),
    ),
    (
        "tli_wli_artifact",
        "broken th/wh OCR fragment inside an English word",
        re.compile(r"(?i)\b(?:tli[a-z]+|wli[a-z]+)\b"),
    ),
    (
        "double_i_artifact",
        "improbable double-i OCR fragment inside an English word",
        re.compile(r"(?i)\b[a-z]+ii[a-z]+\b"),
    ),
    (
        "av_prefix_artifact",
        "broken AV-prefixed OCR fragment inside an English word",
        re.compile(r"\bAV[a-z]+\b"),
    ),
)

OCR_SANITY_REGRESSION_EXAMPLES: tuple[tuple[str, str], ...] = (
    ("0 Chung", "zero_vocative_confusion"),
    ("m}r", "brace_artifact"),
    (r"\vill", "backslash_artifact"),
    ("Ts4ing", "digit_letter_confusion"),
    ("Cho'v", "apostrophe_vw_artifact"),
    ("Ho'v", "apostrophe_vw_artifact"),
    ("Wliere", "tli_wli_artifact"),
    ("tliey", "tli_wli_artifact"),
    ("coiifure", "double_i_artifact"),
    ("silk7", "digit_letter_confusion"),
    ("Ae^-stone", "caret_artifact"),
    ("greatl)7", "paren_digit_intraword_artifact"),
    ("greyj", "trailing_j_artifact"),
    ("I have here admirable guests,", "terminal_truncation_punctuation"),
)

OCR_SANITY_CORRECTED_PREFIX = "OCR sanity sweep corrected:"
OCR_SANITY_DEMOTED_PREFIX = "OCR sanity sweep demoted:"
TRUNCATION_TERMINATORS = (",", ";", ":")

GUOFENG_LEFTOVER_CLASSIFICATIONS: dict[str, str] = {
    "guofeng-zhaonan-006": "needs_better_witness",
    "guofeng-beifeng-001": "needs_better_witness",
    "guofeng-beifeng-010": "needs_better_witness",
    "guofeng-beifeng-017": "likely_repairable_now",
    "guofeng-beifeng-019": "unrecoverable_with_current_witness",
    "guofeng-yongfeng-008": "needs_better_witness",
    "guofeng-weifeng-006": "needs_better_witness",
    "guofeng-weifeng-010": "likely_repairable_now",
    "guofeng-wangfeng-005": "needs_better_witness",
    "guofeng-wangfeng-010": "needs_better_witness",
    "guofeng-zhengfeng-001": "needs_better_witness",
    "guofeng-zhengfeng-008": "needs_better_witness",
    "guofeng-zhengfeng-009": "needs_better_witness",
    "guofeng-zhengfeng-010": "needs_better_witness",
    "guofeng-zhengfeng-021": "needs_better_witness",
    "guofeng-qifeng-002": "likely_repairable_now",
    "guofeng-qifeng-003": "needs_better_witness",
    "guofeng-weifeng-state-002": "needs_better_witness",
    "guofeng-weifeng-state-003": "needs_better_witness",
    "guofeng-weifeng-state-006": "needs_better_witness",
    "guofeng-tangfeng-002": "likely_repairable_now",
    "guofeng-tangfeng-006": "needs_better_witness",
    "guofeng-chenfeng-009": "unrecoverable_with_current_witness",
    "guofeng-binfeng-003": "needs_better_witness",
}

QUEUE_CATEGORY_LABELS: dict[str, str] = {
    "likely_repairable_now": "Likely repairable now",
    "not_yet_investigated_in_detail": "Not yet investigated in detail",
    "unrecoverable_with_current_witness": "Known unrecoverable with current witness",
    "needs_better_witness": "Needs better witness",
}

QUEUE_CATEGORY_ORDER: tuple[str, ...] = (
    "likely_repairable_now",
    "not_yet_investigated_in_detail",
    "unrecoverable_with_current_witness",
    "needs_better_witness",
)


def shijing_witness_metadata(english_witness: str | None) -> dict[str, Any]:
    if english_witness == "standalone_sheking":
        return {
            "english_witness_type": "standalone_wikisource",
            "english_witness_status": "verified_transcribed_text",
            "source_witness_type": "standalone Wikisource",
            "needs_human_text_review": False,
            "ocr_or_fulltext_derived": False,
        }
    if english_witness == "sbe_shih":
        return {
            "english_witness_type": "sbe_transcluded_page",
            "english_witness_status": "sbe_transcluded_verified",
            "source_witness_type": "SBE transcluded page",
            "needs_human_text_review": False,
            "ocr_or_fulltext_derived": False,
        }
    if english_witness == "legge_fulltext":
        return {
            "english_witness_type": "fulltext_derived_witness",
            "english_witness_status": "fulltext_extracted_needs_review",
            "source_witness_type": "full-text derived witness",
            "needs_human_text_review": True,
            "ocr_or_fulltext_derived": True,
        }
    if english_witness == "legge_hocr":
        return {
            "english_witness_type": "fulltext_ocr_derived_witness",
            "english_witness_status": "ocr_extracted_needs_review",
            "source_witness_type": "OCR-derived witness",
            "needs_human_text_review": True,
            "ocr_or_fulltext_derived": True,
        }
    if english_witness == "legge_ocr_reviewed":
        return {
            "english_witness_type": "fulltext_ocr_derived_witness",
            "english_witness_status": "human_reviewed_ocr",
            "source_witness_type": "OCR-derived witness",
            "needs_human_text_review": False,
            "ocr_or_fulltext_derived": True,
        }
    if english_witness == "legge_ocr_failed":
        return {
            "english_witness_type": "fulltext_ocr_derived_witness",
            "english_witness_status": "extraction_failed_metadata_only",
            "source_witness_type": "OCR-derived witness",
            "needs_human_text_review": True,
            "ocr_or_fulltext_derived": True,
        }
    return {
        "english_witness_type": "not_applicable",
        "english_witness_status": "not_applicable",
        "source_witness_type": "not_applicable",
        "needs_human_text_review": False,
        "ocr_or_fulltext_derived": False,
    }


def split_text_blocks(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]


def english_word_count(text: str) -> int:
    return len(ENGLISH_WORD_RE.findall(text))


def chinese_character_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def english_character_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * q))
    return ordered[index]


def detect_quality_markers(text: str, *, title: str | None = None) -> list[str]:
    markers = [name for name, pattern in QUALITY_MARKER_PATTERNS if pattern.search(text)]
    if CJK_RE.search(text):
        markers.append("embedded_chinese")
    if title and title in text:
        markers.append("untranslated_chinese_title")
    return sorted(set(markers))


def load_shijing_quality_overrides() -> list[dict[str, Any]]:
    if not QUALITY_OVERRIDES_PATH.exists():
        return []
    payload = load_json_compatible_yaml(QUALITY_OVERRIDES_PATH)
    overrides = payload.get("overrides", []) if isinstance(payload, dict) else payload
    return list(overrides or [])


def build_override_map(overrides: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    override_map: dict[tuple[str, str], dict[str, Any]] = {}
    for override in overrides:
        section_id = str(override.get("section_id", "")).strip()
        warning_code = str(override.get("warning_code", "")).strip()
        if section_id and warning_code:
            override_map[(section_id, warning_code)] = override
    return override_map


def is_quality_override(override_map: dict[tuple[str, str], dict[str, Any]], section_id: str, warning_code: str) -> bool:
    return (section_id, warning_code) in override_map


def build_ocr_sanity_override_index(
    verification_index: dict[str, dict[str, Any]],
) -> dict[str, dict[str, set[str]]]:
    override_index: dict[str, dict[str, set[str]]] = {}
    for section_id, entry in verification_index.items():
        raw_overrides = entry.get("ocr_sanity_overrides") or []
        if not raw_overrides:
            continue
        section_overrides: dict[str, set[str]] = {}
        for raw_override in raw_overrides:
            if isinstance(raw_override, str):
                match_text = raw_override.strip()
                warning_code = "*"
            elif isinstance(raw_override, dict):
                match_text = str(raw_override.get("match_text") or raw_override.get("text") or "").strip()
                warning_code = str(raw_override.get("code") or raw_override.get("warning_code") or "*").strip() or "*"
            else:
                continue
            if not match_text:
                continue
            section_overrides.setdefault(warning_code, set()).add(match_text)
        if section_overrides:
            override_index[section_id] = section_overrides
    return override_index


def detect_suspicious_ocr_artifacts(
    text: str,
    allowed_matches: dict[str, set[str]] | None = None,
    *,
    chinese_blocks: list[str] | None = None,
    english_blocks: list[str] | None = None,
) -> list[dict[str, Any]]:
    allowed_matches = allowed_matches or {}
    wildcard_matches = allowed_matches.get("*", set())
    issues: list[dict[str, Any]] = []

    def append_issue(code: str, description: str, matches: list[str]) -> None:
        allowed_for_code = wildcard_matches | allowed_matches.get(code, set())
        unresolved_matches = [match for match in sorted(set(matches)) if match not in allowed_for_code]
        if unresolved_matches:
            issues.append(
                {
                    "code": code,
                    "description": description,
                    "matches": unresolved_matches,
                }
            )

    def terminal_line(block_text: str) -> str:
        lines = [line.strip() for line in block_text.strip().splitlines() if line.strip()]
        return lines[-1] if lines else block_text.strip()

    for warning_code, description, pattern in OCR_SANITY_PATTERNS:
        matches = sorted({match.group(0) for match in pattern.finditer(text)})
        if not matches:
            continue
        append_issue(warning_code, description, matches)
    stripped_text = text.rstrip()
    if stripped_text.endswith(TRUNCATION_TERMINATORS):
        append_issue(
            "terminal_truncation_punctuation",
            "section ends with punctuation that strongly suggests truncated extraction",
            [terminal_line(stripped_text)],
        )
    if chinese_blocks and english_blocks and len(chinese_blocks) == len(english_blocks) and len(english_blocks) >= 2:
        comparison_counts = [english_word_count(block) for block in english_blocks[:-1] if english_word_count(block)]
        final_block = english_blocks[-1].strip()
        final_word_count = english_word_count(final_block)
        if comparison_counts and final_block.rstrip().endswith(TRUNCATION_TERMINATORS):
            reference_word_count = statistics.median(comparison_counts)
            final_chinese_size = chinese_character_count(chinese_blocks[-1])
            if (
                final_word_count <= max(12, int(reference_word_count * 0.55))
                and final_chinese_size >= 12
            ):
                append_issue(
                    "truncated_final_stanza",
                    "final stanza looks substantially shorter than the matching Chinese stanza",
                    [terminal_line(final_block)],
                )
    return issues


def classify_remaining_section(section_id: str, major_division: str, review_note: str) -> str:
    if major_division == "國風" and section_id in GUOFENG_LEFTOVER_CLASSIFICATIONS:
        return GUOFENG_LEFTOVER_CLASSIFICATIONS[section_id]
    if not review_note or review_note == GENERIC_UNVERIFIED_NOTE:
        return "not_yet_investigated_in_detail"
    return "needs_better_witness"


def build_remaining_section_record(
    section: dict[str, Any],
    verification: dict[str, Any] | None,
) -> dict[str, Any]:
    review_note = ""
    if verification:
        review_note = str(verification.get("reviewer_note") or "").strip()
    queue_category = classify_remaining_section(
        str(section.get("section_id") or ""),
        str(section.get("major_division") or ""),
        review_note,
    )
    return {
        "section_id": section.get("section_id"),
        "canonical_ref": section.get("canonical_ref"),
        "title": section.get("title_zh") or section.get("label") or section.get("title"),
        "major_division": section.get("major_division"),
        "subdivision": section.get("subdivision"),
        "source_page_or_anchor": (
            verification.get("source_page_or_anchor") if verification else None
        ),
        "queue_category": queue_category,
        "queue_category_label": QUEUE_CATEGORY_LABELS[queue_category],
        "review_note": review_note or "No source-specific note recorded yet.",
    }


def substantial_chinese_in_english(section: dict[str, Any]) -> bool:
    english_text = section["_english_text"]
    cjk_count = len(CJK_RE.findall(english_text))
    return cjk_count >= 3 or bool(section["contains_untranslated_chinese_title"])


def looks_like_heading_or_furniture(section: dict[str, Any]) -> bool:
    markers = set(section["possible_commentary_leakage_markers"])
    if {"heading_marker", "page_furniture"} & markers and section["english_word_count"] < 20:
        return True
    return bool(markers & {"heading_marker", "page_furniture"}) and section["english_word_count"] < 25


def source_urls_for_section(section: dict[str, Any], source_map: dict[str, dict[str, Any]]) -> list[str]:
    urls: list[str] = []
    for key in ("zh_page_url", "en_page_url", "candidate_en_page_url", "candidate_en_text_url", "candidate_en_ocr_url"):
        value = section.get(key)
        if value and value not in urls:
            urls.append(value)
    source_ids = section.get("source_ids") or {}
    for key in ("source_id", "target_source_id"):
        source = source_map.get(str(source_ids.get(key)))
        if not source:
            continue
        source_url = source.get("source_url")
        if source_url and source_url not in urls:
            urls.append(source_url)
    return urls


def build_shijing_quality_context(
    manifest: dict[str, Any] | None = None,
    export_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    manifest = manifest or load_work_manifest(WORK_ID)
    export_rows = export_rows if export_rows is not None else read_jsonl(corpus_export_paths(WORK_ID)["jsonl"])
    overrides = load_shijing_quality_overrides()
    override_map = build_override_map(overrides)
    verification_index = build_verification_index(load_shijing_verification_ledger())
    ocr_sanity_override_index = build_ocr_sanity_override_index(verification_index)
    export_rows_by_section: dict[str, list[dict[str, Any]]] = {}
    for row in export_rows:
        export_rows_by_section.setdefault(row["section_id"], []).append(row)
    for rows in export_rows_by_section.values():
        rows.sort(key=lambda row: row.get("order", 0))

    source_map = {source["source_id"]: source for source in manifest.get("sources", [])}
    complete_sections = [section for section in manifest["sections"] if section.get("tmx_status") == "complete"]
    metadata_only_sections = [section for section in manifest["sections"] if section.get("tmx_status") != "complete"]
    non_exportable_extant_sections = [
        section
        for section in metadata_only_sections
        if section.get("verification_decision") == "do_not_export_until_repaired"
    ]

    section_records: list[dict[str, Any]] = []
    hard_failures: list[str] = []
    row_warning_records: list[dict[str, Any]] = []

    for row in export_rows:
        markers = detect_quality_markers(row["translation_text"])
        if markers:
            row_warning_records.append(
                {
                    "alignment_id": row["alignment_id"],
                    "section_id": row["section_id"],
                    "order": row["order"],
                    "markers": markers,
                    "alignment_granularity": row["alignment_granularity"],
                    "is_coarse_alignment": bool(row.get("is_coarse_alignment")),
                }
            )

    for section in complete_sections:
        section_id = section["section_id"]
        rows = export_rows_by_section.get(section_id, [])
        verification = verification_index.get(section_id)
        source_meta = shijing_witness_metadata(section.get("english_witness"))
        source_urls = source_urls_for_section(section, source_map)
        if not rows:
            hard_failures.append(f"{section_id}: complete section has no exact export rows.")
            continue
        if verification is None:
            hard_failures.append(f"{section_id}: complete section has no verification ledger entry.")
            continue
        if not source_urls:
            hard_failures.append(f"{section_id}: complete section has no source URLs.")
        if source_meta["source_witness_type"] == "not_applicable":
            hard_failures.append(f"{section_id}: complete section has no classified English witness.")

        chinese_text = "\n\n".join(row["chinese_text"] for row in rows)
        english_text = "\n\n".join(row["translation_text"] for row in rows)
        chinese_blocks = split_text_blocks(chinese_text)
        english_blocks = split_text_blocks(english_text)
        markers = detect_quality_markers(english_text, title=section["label"])
        has_coarse = any(bool(row.get("is_coarse_alignment")) for row in rows)
        granularity_values = sorted({row["alignment_granularity"] for row in rows})
        english_status = str(section.get("english_witness_status") or source_meta["english_witness_status"])
        needs_review = bool(section.get("needs_human_text_review", source_meta["needs_human_text_review"]))
        section_records.append(
            {
                "section_id": section_id,
                "title": section["label"],
                "canonical_ref": section["canonical_ref"],
                "major_division": section["major_division"],
                "subdivision": section["subdivision"],
                "source_witness_type": section.get("source_witness_type", source_meta["source_witness_type"]),
                "english_witness_type": section.get("english_witness_type", source_meta["english_witness_type"]),
                "english_witness_status": english_status,
                "needs_human_text_review": needs_review,
                "ocr_or_fulltext_derived": bool(section.get("ocr_or_fulltext_derived", source_meta["ocr_or_fulltext_derived"])),
                "verification_status": verification["verification_status"],
                "verification_decision": verification["decision"],
                "chinese_source_status": verification["chinese_source_status"],
                "english_source_status": verification["english_source_status"],
                "source_volume": verification["source_volume"],
                "source_page_or_anchor": verification["source_page_or_anchor"],
                "raw_source_path": verification["raw_source_path"],
                "processed_translation_path": verification["processed_translation_path"],
                "extraction_method": verification["extraction_method"],
                "review_date": verification.get("review_date"),
                "repair_batch": verification.get("repair_batch"),
                "ocr_sanity_overrides": verification.get("ocr_sanity_overrides") or [],
                "remaining_warnings": verification["remaining_warnings"],
                "exact_alignment_count": len(rows),
                "alignment_granularity_values": granularity_values,
                "has_coarse_alignment": has_coarse,
                "is_single_poem_alignment": len(rows) == 1 and granularity_values == ["poem"],
                "chinese_character_count": chinese_character_count(chinese_text),
                "english_character_count": english_character_count(english_text),
                "english_word_count": english_word_count(english_text),
                "chinese_stanza_count": len(chinese_blocks),
                "english_stanza_block_count": len(english_blocks),
                "english_to_chinese_length_ratio": (
                    english_character_count(english_text) / max(chinese_character_count(chinese_text), 1)
                ),
                "possible_commentary_leakage_markers": markers,
                "contains_chinese_in_english_segment": any(marker == "embedded_chinese" for marker in markers),
                "contains_untranslated_chinese_title": any(marker == "untranslated_chinese_title" for marker in markers),
                "complete_but_needs_human_text_review": section.get("status") == "complete" and needs_review,
                "notes": section.get("notes"),
                "review_note": section.get("review_note") or verification.get("reviewer_note"),
                "source_urls": source_urls,
                "_chinese_text": chinese_text,
                "_english_text": english_text,
                "_rows": rows,
            }
        )

    word_counts = [section["english_word_count"] for section in section_records]
    ratios = [section["english_to_chinese_length_ratio"] for section in section_records]
    word_short_threshold = max(12, int(percentile(word_counts, 0.05)))
    word_long_threshold = max(int(percentile(word_counts, 0.95)), int(statistics.median(word_counts) * 2.0))
    ratio_low_threshold = max(0.75, percentile(ratios, 0.05))
    ratio_high_threshold = max(8.0, percentile(ratios, 0.95))
    hard_word_threshold = 10
    very_high_ratio_threshold = max(20.0, ratio_high_threshold * 2.0)

    warning_count = 0
    for section in section_records:
        short_english = section["english_word_count"] <= word_short_threshold or section["english_character_count"] <= 20
        long_english = section["english_word_count"] >= word_long_threshold
        ratio_low = section["english_to_chinese_length_ratio"] < ratio_low_threshold
        ratio_high = section["english_to_chinese_length_ratio"] > ratio_high_threshold
        verified_without_remaining_issues = (
            section["verification_status"] in VERIFIED_EXPORT_STATUSES and not section["remaining_warnings"]
        )
        marker_set = set(section["possible_commentary_leakage_markers"])
        blocking_marker_codes = {
            "heading_marker",
            "page_furniture",
            "footnote_marker",
            "commentary_marker",
            "ocr_noise",
        }
        possible_stanza_split = (
            section["is_single_poem_alignment"]
            and section["chinese_stanza_count"] > 1
            and section["english_stanza_block_count"] > 1
        )
        ocr_sanity_issues = (
            detect_suspicious_ocr_artifacts(
                section["_english_text"],
                ocr_sanity_override_index.get(section["section_id"]),
                chinese_blocks=chinese_blocks,
                english_blocks=english_blocks,
            )
            if section["ocr_or_fulltext_derived"]
            else []
        )
        warnings: list[str] = []
        warning_codes: list[str] = []
        overridden_warning_codes: list[str] = []
        hard_failure_codes: list[str] = []

        def add_warning(code: str, message: str) -> None:
            if is_quality_override(override_map, section["section_id"], code):
                overridden_warning_codes.append(code)
                return
            warning_codes.append(code)
            warnings.append(message)

        def add_hard_failure(code: str, message: str) -> None:
            if is_quality_override(override_map, section["section_id"], code):
                overridden_warning_codes.append(code)
                return
            hard_failure_codes.append(code)
            hard_failures.append(f"{section['section_id']}: {message}")

        if short_english and not verified_without_remaining_issues:
            add_warning("suspiciously_short_english_text", "suspiciously short English text")
        if long_english:
            add_warning("suspiciously_long_english_text", "suspiciously long English text")
        if ratio_low and not verified_without_remaining_issues:
            add_warning("suspiciously_low_length_ratio", "suspiciously low English/Chinese length ratio")
        if ratio_high and not verified_without_remaining_issues:
            add_warning("suspiciously_high_length_ratio", "suspiciously high English/Chinese length ratio")
        if section["possible_commentary_leakage_markers"]:
            add_warning("possible_commentary_leakage", "possible commentary, page furniture, or OCR junk")
        if section["contains_chinese_in_english_segment"] or section["contains_untranslated_chinese_title"]:
            add_warning("chinese_in_english_segment", "Chinese text appears inside the English segment")
        if section["complete_but_needs_human_text_review"]:
            add_warning("complete_needs_human_text_review", "complete section still needs human text review")
        if possible_stanza_split:
            add_warning("possible_stanza_split", "poem-level alignment may hide recoverable stanza segmentation")
        if ocr_sanity_issues:
            add_warning("suspicious_ocr_artifact", "suspicious OCR artifacts remain in the English text")

        if section["verification_decision"] != "export":
            add_hard_failure("complete_not_authorized_for_export", "complete section is not authorized for export in the verification ledger.")
        if section["verification_status"] not in VERIFIED_EXPORT_STATUSES:
            add_hard_failure(
                "complete_unverified_english_source",
                f"complete section has non-exportable verification status {section['verification_status']!r}.",
            )
        if not verification_entry_is_exportable({"decision": section["verification_decision"]}) or not verification_entry_is_verified(
            {"decision": section["verification_decision"], "verification_status": section["verification_status"]}
        ):
            add_hard_failure("complete_unverified_ledger_state", "complete section lacks a verified ledger state.")
        if section["needs_human_text_review"]:
            add_hard_failure("complete_needs_human_text_review", "complete section still needs human text review.")
        if section["english_witness_status"] in {"ocr_extracted_needs_review", "fulltext_extracted_needs_review"}:
            add_hard_failure(
                "complete_exporting_unreviewed_ocr_or_fulltext",
                f"complete section still uses unresolved witness status {section['english_witness_status']!r}.",
            )
        if section["ocr_or_fulltext_derived"] and not section["source_page_or_anchor"]:
            add_hard_failure(
                "complete_missing_source_anchor",
                "complete OCR/full-text-derived section lacks source page or anchor evidence in the verification ledger.",
            )
        if section["ocr_or_fulltext_derived"] and not section["raw_source_path"]:
            add_hard_failure(
                "complete_missing_raw_source_path",
                "complete OCR/full-text-derived section lacks a raw source path in the verification ledger.",
            )
        if section["english_word_count"] == 0:
            add_hard_failure("complete_empty_english", "complete section has empty English text.")
        elif section["english_word_count"] < hard_word_threshold:
            add_hard_failure(
                "complete_under_minimum_english_words",
                f"complete section has only {section['english_word_count']} English words.",
            )
        if substantial_chinese_in_english(section):
            add_hard_failure("complete_contains_chinese_text", "complete section still contains substantial Chinese text.")
        if looks_like_heading_or_furniture(section):
            add_hard_failure(
                "complete_looks_like_heading_or_furniture",
                "complete section still looks like heading, page furniture, or paratext rather than translation.",
            )
        if marker_set & blocking_marker_codes:
            add_hard_failure(
                "complete_contains_commentary_or_page_furniture",
                "complete section still contains commentary markers, page furniture, footnotes, or OCR debris.",
            )
        if ocr_sanity_issues:
            add_hard_failure(
                "complete_contains_suspicious_ocr_artifact",
                "complete section still contains suspicious OCR artifacts.",
            )
        if section["english_to_chinese_length_ratio"] > very_high_ratio_threshold:
            if section["review_note"]:
                add_warning(
                    "reviewed_extreme_high_ratio",
                    (
                        "extreme English/Chinese length ratio retained only because the verification ledger records a "
                        "manual review note"
                    ),
                )
            else:
                add_hard_failure(
                    "complete_extreme_high_ratio",
                    (
                        "complete section has an implausibly high English/Chinese length ratio "
                        f"({section['english_to_chinese_length_ratio']:.3f})."
                    ),
                )
        if set(section["remaining_warnings"]) & {
            "suspiciously_short_english_text",
            "suspiciously_high_length_ratio",
            "possible_commentary_leakage",
            "chinese_in_english_segment",
            "complete_needs_human_text_review",
        }:
            add_hard_failure(
                "complete_has_unresolved_ledger_warning",
                "complete section still has unresolved blocking warnings recorded in the verification ledger.",
            )
        section["suspiciously_short_english_text"] = short_english
        section["suspiciously_long_english_text"] = long_english
        section["suspiciously_extreme_length_ratio"] = bool(
            {"suspiciously_low_length_ratio", "suspiciously_high_length_ratio"} & set(warning_codes)
        )
        section["possible_stanza_split"] = possible_stanza_split
        section["ocr_sanity_issue_records"] = ocr_sanity_issues
        section["suspicious_ocr_artifact_markers"] = [issue["code"] for issue in ocr_sanity_issues]
        section["warning_codes"] = warning_codes
        section["overridden_warning_codes"] = sorted(set(overridden_warning_codes))
        section["hard_failure_codes"] = hard_failure_codes
        section["has_hard_failure"] = bool(hard_failure_codes)
        section["warnings"] = warnings
        warning_count += len(warnings)

    witness_counts: dict[str, int] = {}
    verification_status_counts: dict[str, int] = {}
    for section in section_records:
        witness_counts[section["source_witness_type"]] = witness_counts.get(section["source_witness_type"], 0) + 1
        verification_status_counts[section["verification_status"]] = verification_status_counts.get(
            section["verification_status"], 0
        ) + 1

    remaining_by_subdivision: dict[str, int] = {}
    for section in non_exportable_extant_sections:
        subdivision_key = f"{section['major_division']} / {section['subdivision']}"
        remaining_by_subdivision[subdivision_key] = remaining_by_subdivision.get(subdivision_key, 0) + 1
    remaining_section_records = [
        build_remaining_section_record(
            section,
            verification_index.get(section["section_id"]),
        )
        for section in sorted(non_exportable_extant_sections, key=lambda item: item["canonical_ref"])
    ]
    remaining_priority_subdivisions: dict[str, list[dict[str, str]]] = {}
    for major_division, subdivision in DETAILED_QUEUE_SUBDIVISIONS:
        subdivision_key = f"{major_division} / {subdivision}"
        remaining_priority_subdivisions[subdivision_key] = [
            record
            for record in remaining_section_records
            if record["major_division"] == major_division and record["subdivision"] == subdivision
        ]
    remaining_guofeng_sections = [
        record for record in remaining_section_records if record["major_division"] == "國風"
    ]
    remaining_xiaoya_sections = [
        record for record in remaining_section_records if record["major_division"] == "小雅"
    ]
    remaining_daya_song_sections = [
        record
        for record in remaining_section_records
        if record["major_division"] in {"大雅", "頌"}
    ]
    guofeng_queue_categories = {
        category: [
            record
            for record in remaining_guofeng_sections
            if record["queue_category"] == category
        ]
        for category in QUEUE_CATEGORY_ORDER
    }
    remaining_guofeng_by_subdivision: dict[str, int] = {}
    remaining_xiaoya_by_subdivision: dict[str, int] = {}
    remaining_daya_song_by_subdivision: dict[str, int] = {}
    for record in remaining_section_records:
        subdivision_key = f"{record['major_division']} / {record['subdivision']}"
        if record["major_division"] == "國風":
            remaining_guofeng_by_subdivision[subdivision_key] = (
                remaining_guofeng_by_subdivision.get(subdivision_key, 0) + 1
            )
        elif record["major_division"] == "小雅":
            remaining_xiaoya_by_subdivision[subdivision_key] = (
                remaining_xiaoya_by_subdivision.get(subdivision_key, 0) + 1
            )
        elif record["major_division"] in {"大雅", "頌"}:
            remaining_daya_song_by_subdivision[subdivision_key] = (
                remaining_daya_song_by_subdivision.get(subdivision_key, 0) + 1
            )
    human_verified_sections = [
        section
        for section in section_records
        if section["verification_status"] in {"human_verified_ocr", "human_verified_fulltext"}
    ]
    human_verified_ocr_sections = [
        section for section in section_records if section["verification_status"] == "human_verified_ocr"
    ]
    human_verified_batches: dict[str, dict[str, Any]] = {}
    for section in human_verified_sections:
        batch_key = section.get("repair_batch") or "pre-batch verified"
        batch_record = human_verified_batches.setdefault(
            batch_key,
            {
                "repair_batch": batch_key,
                "section_count": 0,
                "human_verified_ocr_count": 0,
                "human_verified_fulltext_count": 0,
            },
        )
        batch_record["section_count"] += 1
        if section["verification_status"] == "human_verified_ocr":
            batch_record["human_verified_ocr_count"] += 1
        elif section["verification_status"] == "human_verified_fulltext":
            batch_record["human_verified_fulltext_count"] += 1
    latest_repair_batch = max(
        (section["repair_batch"] for section in human_verified_sections if section.get("repair_batch")),
        default=None,
    )
    latest_repaired_sections = [
        {
            "section_id": section["section_id"],
            "title": section["title"],
            "canonical_ref": section["canonical_ref"],
            "verification_status": section["verification_status"],
            "review_date": section["review_date"],
            "repair_batch": section.get("repair_batch"),
        }
        for section in sorted(section_records, key=lambda section: section["canonical_ref"])
        if latest_repair_batch and section.get("repair_batch") == latest_repair_batch
    ]
    latest_review_date = max(
        (section["review_date"] for section in latest_repaired_sections if section.get("review_date")),
        default=None,
    )
    if not latest_repaired_sections:
        latest_review_date = max(
            (
                section["review_date"]
                for section in human_verified_sections
                if section.get("review_date")
            ),
            default=None,
        )
        latest_repaired_sections = [
            {
                "section_id": section["section_id"],
                "title": section["title"],
                "canonical_ref": section["canonical_ref"],
                "verification_status": section["verification_status"],
                "review_date": section["review_date"],
                "repair_batch": section.get("repair_batch"),
            }
            for section in sorted(section_records, key=lambda section: section["canonical_ref"])
            if latest_review_date and section.get("review_date") == latest_review_date
        ]
    previous_human_verified_batches = [
        batch
        for batch in sorted(
            human_verified_batches.values(),
            key=lambda batch: batch["repair_batch"],
        )
        if batch["repair_batch"] != latest_repair_batch
    ]
    current_batch_summary = {
        "repair_batch": latest_repair_batch,
        "latest_review_date": latest_review_date,
        "newly_repaired_in_current_batch": len(latest_repaired_sections),
        "human_verified_ocr_sections_in_current_batch": sum(
            1
            for section in latest_repaired_sections
            if section["verification_status"] == "human_verified_ocr"
        ),
        "human_verified_fulltext_sections_in_current_batch": sum(
            1
            for section in latest_repaired_sections
            if section["verification_status"] == "human_verified_fulltext"
        ),
    }
    suspicious_ocr_sections = [
        {
            "section_id": section["section_id"],
            "title": section["title"],
            "canonical_ref": section["canonical_ref"],
            "ocr_sanity_issue_records": section["ocr_sanity_issue_records"],
        }
        for section in section_records
        if section["suspicious_ocr_artifact_markers"]
    ]
    ocr_sanity_sweep = {
        "checked_exportable_ocr_sections": len(human_verified_ocr_sections),
        "flagged_sections": len(suspicious_ocr_sections),
        "flagged_section_records": suspicious_ocr_sections,
        "regression_examples": [
            {"sample": sample, "detector": detector}
            for sample, detector in OCR_SANITY_REGRESSION_EXAMPLES
        ],
        "corrected_sections": [
            {
                "section_id": section["section_id"],
                "title": section["title"],
                "canonical_ref": section["canonical_ref"],
                "source_page_or_anchor": section["source_page_or_anchor"],
                "review_note": (
                    verification_index.get(section["section_id"], {}).get("reviewer_note") or section["review_note"]
                ),
            }
            for section in sorted(section_records, key=lambda section: section["canonical_ref"])
            if str(
                verification_index.get(section["section_id"], {}).get("reviewer_note") or section.get("review_note") or ""
            ).startswith(OCR_SANITY_CORRECTED_PREFIX)
        ],
        "demoted_sections": [
            {
                "section_id": section["section_id"],
                "title": section["label"],
                "canonical_ref": section["canonical_ref"],
                "source_page_or_anchor": verification_index.get(section["section_id"], {}).get("source_page_or_anchor"),
                "review_note": verification_index.get(section["section_id"], {}).get("reviewer_note"),
            }
            for section in sorted(metadata_only_sections, key=lambda section: section["canonical_ref"])
            if str(verification_index.get(section["section_id"], {}).get("reviewer_note") or "").startswith(
                OCR_SANITY_DEMOTED_PREFIX
            )
        ],
        "ledger_backed_overrides": [
            {
                "section_id": section["section_id"],
                "title": section["title"],
                "canonical_ref": section["canonical_ref"],
                "source_page_or_anchor": section["source_page_or_anchor"],
                "ocr_sanity_overrides": section["ocr_sanity_overrides"],
                "review_note": section["review_note"],
            }
            for section in sorted(section_records, key=lambda section: section["canonical_ref"])
            if section["ocr_sanity_overrides"]
        ],
    }
    skipped_current_witness_sections = [
        {
            "section_id": record["section_id"],
            "title": record["title"],
            "canonical_ref": record["canonical_ref"],
            "subdivision": f"{record['major_division']} / {record['subdivision']}",
            "queue_category": record["queue_category"],
            "queue_category_label": record["queue_category_label"],
            "review_note": record["review_note"],
        }
        for record in remaining_section_records
        if (record["major_division"], record["subdivision"]) in DETAILED_QUEUE_SUBDIVISIONS
        and record["review_note"] != "No source-specific note recorded yet."
        and record["review_note"] != GENERIC_UNVERIFIED_NOTE
    ]
    title_only_lost_text_sections = [
        {
            "section_id": section["section_id"],
            "title": section["label"],
            "canonical_ref": section["canonical_ref"],
            "status": section.get("status"),
            "verification_status": section.get("verification_status"),
            "verification_decision": section.get("verification_decision"),
            "notes": section.get("notes"),
            "review_note": verification_index.get(section["section_id"], {}).get("reviewer_note"),
            "source_urls": source_urls_for_section(section, source_map),
        }
        for section in metadata_only_sections
        if section.get("verification_decision") != "do_not_export_until_repaired"
    ]
    current_batch_investigated_non_exportable_sections = [
        {
            "section_id": record["section_id"],
            "title": record["title"],
            "canonical_ref": record["canonical_ref"],
            "queue_category_label": record["queue_category_label"],
            "source_volume": record["source_volume"],
            "source_page_or_anchor": record["source_page_or_anchor"],
            "review_note": record["review_note"],
            "review_date": record.get("review_date"),
        }
        for record in remaining_section_records
        if latest_review_date and record.get("review_date") == latest_review_date
    ]

    return {
        "work_id": WORK_ID,
        "summary": {
            "section_count": manifest.get("summary", {}).get("section_count", len(manifest["sections"])),
            "extant_poem_count": manifest.get("summary", {}).get(
                "extant_poem_count",
                len(section_records) + len(non_exportable_extant_sections),
            ),
            "exportable_extant_poems": len(section_records),
            "complete_sections": len(section_records),
            "metadata_only_sections": len(metadata_only_sections),
            "title_only_lost_text_entries": len(title_only_lost_text_sections),
            "non_exportable_extant_sections": len(non_exportable_extant_sections),
            "exact_alignment_count": len(export_rows),
            "complete_sections_by_witness_type": witness_counts,
            "complete_sections_by_verification_status": verification_status_counts,
            "ocr_or_fulltext_derived_sections": sum(1 for section in section_records if section["ocr_or_fulltext_derived"]),
            "sections_needing_human_text_review": sum(
                1 for section in section_records if section["complete_but_needs_human_text_review"]
            ),
            "sections_with_coarse_alignment": sum(1 for section in section_records if section["has_coarse_alignment"]),
            "sections_with_single_poem_alignment": sum(
                1 for section in section_records if section["is_single_poem_alignment"]
            ),
            "sections_with_extreme_length_ratio": sum(
                1 for section in section_records if section["suspiciously_extreme_length_ratio"]
            ),
            "sections_with_possible_commentary_leakage": sum(
                1 for section in section_records if section["possible_commentary_leakage_markers"]
            ),
            "sections_with_suspicious_ocr_artifacts": sum(
                1 for section in section_records if section["suspicious_ocr_artifact_markers"]
            ),
            "hard_failure_count": len(hard_failures),
            "warning_count": warning_count,
            "sections_with_hard_failures": sum(1 for section in section_records if section["has_hard_failure"]),
        },
        "progress": {
            "total_extant_poems": manifest.get("summary", {}).get(
                "extant_poem_count",
                len(section_records) + len(non_exportable_extant_sections),
            ),
            "verified_exportable_poems": len(section_records),
            "exportable_extant_poems": len(section_records),
            "non_exportable_extant_poems": len(non_exportable_extant_sections),
            "title_only_lost_text_entries": len(title_only_lost_text_sections),
            "all_human_verified_ocr_sections": len(human_verified_ocr_sections),
            "non_exportable_repair_queue_remaining": len(non_exportable_extant_sections),
            "current_repair_batch": latest_repair_batch,
            "latest_repair_batch": latest_repair_batch,
            "latest_review_date": latest_review_date,
            "newly_repaired_in_current_batch": len(latest_repaired_sections),
            "newly_repaired_in_latest_tranche": len(latest_repaired_sections),
            "remaining_likely_repairable_cases": sum(
                1 for record in remaining_section_records if record["queue_category"] == "likely_repairable_now"
            ),
            "remaining_needs_better_witness_cases": sum(
                1 for record in remaining_section_records if record["queue_category"] == "needs_better_witness"
            ),
            "remaining_known_unrecoverable_cases": sum(
                1
                for record in remaining_section_records
                if record["queue_category"] == "unrecoverable_with_current_witness"
            ),
            "current_batch_summary": current_batch_summary,
            "latest_repaired_sections": latest_repaired_sections,
            "current_batch_investigated_non_exportable_sections": current_batch_investigated_non_exportable_sections,
            "human_verified_batches": sorted(
                human_verified_batches.values(),
                key=lambda batch: batch["repair_batch"],
            ),
            "previous_human_verified_batches": previous_human_verified_batches,
            "remaining_by_subdivision": remaining_by_subdivision,
            "remaining_priority_subdivisions": remaining_priority_subdivisions,
            "remaining_guofeng_by_subdivision": remaining_guofeng_by_subdivision,
            "remaining_xiaoya_by_subdivision": remaining_xiaoya_by_subdivision,
            "remaining_daya_song_by_subdivision": remaining_daya_song_by_subdivision,
            "remaining_guofeng_sections": remaining_guofeng_sections,
            "remaining_xiaoya_sections": remaining_xiaoya_sections,
            "remaining_daya_song_sections": remaining_daya_song_sections,
            "remaining_queue_category_counts": {
                QUEUE_CATEGORY_LABELS[category]: sum(
                    1 for record in remaining_section_records if record["queue_category"] == category
                )
                for category in QUEUE_CATEGORY_ORDER
            },
            "guofeng_queue_categories": guofeng_queue_categories,
            "known_unrecoverable_cases": guofeng_queue_categories["unrecoverable_with_current_witness"],
            "cases_needing_better_witness": [
                record
                for record in remaining_section_records
                if record["queue_category"] == "needs_better_witness"
            ],
            "remaining_non_exportable_extant_sections": remaining_section_records,
            "title_only_lost_text_sections": title_only_lost_text_sections,
            "ocr_sanity_sweep": ocr_sanity_sweep,
            "skipped_current_witness_sections": skipped_current_witness_sections,
        },
        "thresholds": {
            "english_word_short_threshold": word_short_threshold,
            "english_word_long_threshold": word_long_threshold,
            "english_to_chinese_ratio_low_threshold": ratio_low_threshold,
            "english_to_chinese_ratio_high_threshold": ratio_high_threshold,
            "hard_english_word_minimum": hard_word_threshold,
            "hard_english_to_chinese_ratio_high_threshold": very_high_ratio_threshold,
        },
        "hard_failures": hard_failures,
        "row_warnings": row_warning_records,
        "sections": section_records,
        "quality_overrides": overrides,
        "metadata_only_sections": [
            {
                "section_id": section["section_id"],
                "title": section["label"],
                "canonical_ref": section["canonical_ref"],
                "status": section.get("status"),
                "verification_status": section.get("verification_status"),
                "verification_decision": section.get("verification_decision"),
                "english_witness_status": section.get("english_witness_status"),
                "notes": section.get("notes"),
                "review_note": verification_index.get(section["section_id"], {}).get("reviewer_note"),
                "source_urls": source_urls_for_section(section, source_map),
            }
            for section in metadata_only_sections
        ],
    }


def serializable_quality_report(context: dict[str, Any]) -> dict[str, Any]:
    sections = []
    for section in context["sections"]:
        sections.append(
            {
                key: value
                for key, value in section.items()
                if key not in {"_chinese_text", "_english_text", "_rows"}
            }
        )
    return {
        "work_id": context["work_id"],
        "summary": context["summary"],
        "progress": context["progress"],
        "thresholds": context["thresholds"],
        "hard_failure_count": context["summary"]["hard_failure_count"],
        "warning_count": context["summary"]["warning_count"],
        "hard_failures": context["hard_failures"],
        "row_warnings": context["row_warnings"],
        "metadata_only_sections": context["metadata_only_sections"],
        "sections": sections,
    }


def quality_markdown(context: dict[str, Any]) -> str:
    summary = context["summary"]
    progress = context["progress"]
    sections = context["sections"]
    worst_ratio_sections = sorted(
        sections,
        key=lambda section: max(
            section["english_to_chinese_length_ratio"],
            1 / max(section["english_to_chinese_length_ratio"], 1e-9),
        ),
        reverse=True,
    )[:10]
    most_flagged_sections = sorted(sections, key=lambda section: len(section["warnings"]), reverse=True)[:15]
    def append_count_table(rows: list[tuple[str, object]]) -> None:
        lines.extend(["| Metric | Count |", "| --- | ---: |"])
        for label, value in rows:
            lines.append(f"| {label} | {value} |")
        if not rows:
            lines.append("| — | 0 |")
        lines.append("")

    def append_queue_table(records: list[dict[str, Any]], *, include_category: bool = False) -> None:
        if include_category:
            lines.extend(
                [
                    "| Section | Title | Canonical ref | Queue category | Reason |",
                    "| --- | --- | --- | --- | --- |",
                ]
            )
        else:
            lines.extend(
                [
                    "| Section | Title | Canonical ref | Reason |",
                    "| --- | --- | --- | --- |",
                ]
            )
        if records:
            for record in records:
                review_note = str(record["review_note"]).replace("\n", " ")
                if include_category:
                    lines.append(
                        "| {section_id} | {title} | {canonical_ref} | {queue_category_label} | {review_note} |".format(
                            section_id=record["section_id"],
                            title=record["title"],
                            canonical_ref=record["canonical_ref"],
                            queue_category_label=record["queue_category_label"],
                            review_note=review_note,
                        )
                    )
                else:
                    lines.append(
                        "| {section_id} | {title} | {canonical_ref} | {review_note} |".format(
                            section_id=record["section_id"],
                            title=record["title"],
                            canonical_ref=record["canonical_ref"],
                            review_note=review_note,
                        )
                    )
        else:
            lines.append("| — | — | — | — |" + (" — |" if include_category else ""))
        lines.append("")

    lines = [
        "# Shijing completion quality audit",
        "",
        "This report complements the structural preflight checks with verification-ledger enforcement for exportable *Shijing* poems.",
        "",
        "## Summary",
        "",
    ]
    append_count_table(
        [
            ("section_count", summary["section_count"]),
            ("extant_poem_count", summary["extant_poem_count"]),
            ("exportable_extant_poems", summary["exportable_extant_poems"]),
            ("non_exportable_extant_poems", summary["non_exportable_extant_sections"]),
            ("title_only_lost_text_entries", summary["title_only_lost_text_entries"]),
            ("remaining_likely_repairable_cases", progress["remaining_likely_repairable_cases"]),
            ("remaining_needs_better_witness_cases", progress["remaining_needs_better_witness_cases"]),
            ("remaining_known_unrecoverable_cases", progress["remaining_known_unrecoverable_cases"]),
            ("complete_sections", summary["complete_sections"]),
            ("metadata_only_sections", summary["metadata_only_sections"]),
            ("non_exportable_extant_sections", summary["non_exportable_extant_sections"]),
            ("exact_alignment_count", summary["exact_alignment_count"]),
            ("ocr_or_fulltext_derived_sections", summary["ocr_or_fulltext_derived_sections"]),
            ("sections_needing_human_text_review", summary["sections_needing_human_text_review"]),
            ("sections_with_coarse_alignment", summary["sections_with_coarse_alignment"]),
            ("sections_with_single_poem_alignment", summary["sections_with_single_poem_alignment"]),
            ("sections_with_extreme_length_ratio", summary["sections_with_extreme_length_ratio"]),
            ("sections_with_possible_commentary_leakage", summary["sections_with_possible_commentary_leakage"]),
            ("sections_with_suspicious_ocr_artifacts", summary["sections_with_suspicious_ocr_artifacts"]),
            ("sections_with_hard_failures", summary["sections_with_hard_failures"]),
            ("hard_failure_count", summary["hard_failure_count"]),
            ("warning_count", summary["warning_count"]),
        ]
    )
    lines.extend(["## Progress", ""])
    append_count_table(
        [
            ("total_extant_poems", progress["total_extant_poems"]),
            ("verified_exportable_poems", progress["verified_exportable_poems"]),
            ("non_exportable_extant_poems", progress["non_exportable_extant_poems"]),
            ("title_only_lost_text_entries", progress["title_only_lost_text_entries"]),
            ("all_human_verified_ocr_sections", progress["all_human_verified_ocr_sections"]),
            ("non_exportable_repair_queue_remaining", progress["non_exportable_repair_queue_remaining"]),
            ("current_repair_batch", progress["current_repair_batch"] or "—"),
            ("newly_repaired_in_current_batch", progress["newly_repaired_in_current_batch"]),
        ]
    )

    current_batch_summary = progress["current_batch_summary"]
    lines.extend(["## Current batch summary", ""])
    append_count_table(
        [
            ("repair_batch", current_batch_summary["repair_batch"] or "—"),
            ("latest_review_date", current_batch_summary["latest_review_date"] or "—"),
            (
                "newly_repaired_in_current_batch",
                current_batch_summary["newly_repaired_in_current_batch"],
            ),
            (
                "human_verified_ocr_sections_in_current_batch",
                current_batch_summary["human_verified_ocr_sections_in_current_batch"],
            ),
            (
                "human_verified_fulltext_sections_in_current_batch",
                current_batch_summary["human_verified_fulltext_sections_in_current_batch"],
            ),
        ]
    )

    lines.extend(
        [
            "## Newly repaired in current batch",
            "",
            "| Section | Title | Canonical ref | Verification status |",
            "| --- | --- | --- | --- |",
        ]
    )
    for section in progress["latest_repaired_sections"]:
        lines.append(
            "| {section_id} | {title} | {canonical_ref} | {verification_status} |".format(
                section_id=section["section_id"],
                title=section["title"],
                canonical_ref=section["canonical_ref"],
                verification_status=section["verification_status"],
            )
        )
    if not progress["latest_repaired_sections"]:
        lines.append("| — | — | — | — |")
    lines.append("")

    lines.extend(
        [
            "## Sections investigated but left non-exportable in this pass",
            "",
            "| Section | Title | Canonical ref | Category | Source anchor | Note |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for section in progress["current_batch_investigated_non_exportable_sections"]:
        lines.append(
            "| {section_id} | {title} | {canonical_ref} | {queue_category_label} | {source_page_or_anchor} | {review_note} |".format(
                section_id=section["section_id"],
                title=section["title"],
                canonical_ref=section["canonical_ref"],
                queue_category_label=section["queue_category_label"],
                source_page_or_anchor=section["source_page_or_anchor"] or section["source_volume"] or "—",
                review_note=str(section["review_note"] or "—").replace("\n", " "),
            )
        )
    if not progress["current_batch_investigated_non_exportable_sections"]:
        lines.append("| — | — | — | — | — | — |")
    lines.append("")

    lines.extend(
        [
            "## Previous OCR repair batches",
            "",
            "| Repair batch | Section count | human_verified_ocr | human_verified_fulltext |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for batch in progress["previous_human_verified_batches"]:
        lines.append(
            "| {repair_batch} | {section_count} | {human_verified_ocr_count} | {human_verified_fulltext_count} |".format(
                repair_batch=batch["repair_batch"],
                section_count=batch["section_count"],
                human_verified_ocr_count=batch["human_verified_ocr_count"],
                human_verified_fulltext_count=batch["human_verified_fulltext_count"],
            )
        )
    if not progress["previous_human_verified_batches"]:
        lines.append("| — | 0 | 0 | 0 |")
    lines.append("")

    lines.extend(["## OCR sanity tests added", ""])
    lines.extend(["| Sample pattern | Detector |", "| --- | --- |"])
    for example in progress["ocr_sanity_sweep"]["regression_examples"]:
        lines.append(f"| {example['sample']} | {example['detector']} |")
    lines.append("")

    lines.extend(["## Current OCR sweep result", ""])
    append_count_table(
        [
            (
                "checked_exportable_ocr_sections",
                progress["ocr_sanity_sweep"]["checked_exportable_ocr_sections"],
            ),
            ("flagged_sections", progress["ocr_sanity_sweep"]["flagged_sections"]),
        ]
    )
    lines.extend(
        [
            "| Section | Title | Canonical ref | Artifact markers | Matches |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    suspicious_ocr_sections = progress["ocr_sanity_sweep"]["flagged_section_records"]
    if suspicious_ocr_sections:
        for section in suspicious_ocr_sections:
            matches = ", ".join(
                match for issue in section["ocr_sanity_issue_records"] for match in issue["matches"]
            )
            lines.append(
                "| {section_id} | {title} | {canonical_ref} | {markers} | {matches} |".format(
                    section_id=section["section_id"],
                    title=section["title"],
                    canonical_ref=section["canonical_ref"],
                    markers=", ".join(issue["code"] for issue in section["ocr_sanity_issue_records"]),
                    matches=matches,
                )
            )
    else:
        lines.append("| — | — | — | — | — |")
    lines.append("")

    lines.extend(
        [
            "## Sections corrected in this pass",
            "",
            "| Section | Title | Canonical ref | Source anchor | Note |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    corrected_sections = progress["ocr_sanity_sweep"]["corrected_sections"]
    if corrected_sections:
        for section in corrected_sections:
            lines.append(
                "| {section_id} | {title} | {canonical_ref} | {source_page_or_anchor} | {review_note} |".format(
                    section_id=section["section_id"],
                    title=section["title"],
                    canonical_ref=section["canonical_ref"],
                    source_page_or_anchor=section["source_page_or_anchor"] or "—",
                    review_note=str(section["review_note"]).replace("\n", " "),
                )
            )
    else:
        lines.append("| — | — | — | — | — |")
    lines.append("")

    lines.extend(
        [
            "## Sections moved back to non-exportable in this pass",
            "",
            "| Section | Title | Canonical ref | Source anchor | Note |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    demoted_sections = progress["ocr_sanity_sweep"]["demoted_sections"]
    if demoted_sections:
        for section in demoted_sections:
            lines.append(
                "| {section_id} | {title} | {canonical_ref} | {source_page_or_anchor} | {review_note} |".format(
                    section_id=section["section_id"],
                    title=section["title"],
                    canonical_ref=section["canonical_ref"],
                    source_page_or_anchor=section["source_page_or_anchor"] or "—",
                    review_note=str(section["review_note"]).replace("\n", " "),
                )
            )
    else:
        lines.append("| — | — | — | — | — |")
    lines.append("")

    lines.extend(
        [
            "## Ledger-backed OCR overrides",
            "",
            "| Section | Title | Canonical ref | Source anchor | Override matches |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    ledger_backed_overrides = progress["ocr_sanity_sweep"]["ledger_backed_overrides"]
    if ledger_backed_overrides:
        for section in ledger_backed_overrides:
            override_values: list[str] = []
            for override in section["ocr_sanity_overrides"]:
                if isinstance(override, str):
                    override_values.append(override)
                elif isinstance(override, dict):
                    override_values.append(str(override.get("match_text") or override.get("text") or override))
                else:
                    override_values.append(str(override))
            lines.append(
                "| {section_id} | {title} | {canonical_ref} | {source_page_or_anchor} | {override_values} |".format(
                    section_id=section["section_id"],
                    title=section["title"],
                    canonical_ref=section["canonical_ref"],
                    source_page_or_anchor=section["source_page_or_anchor"] or "—",
                    override_values=", ".join(override_values) or "—",
                )
            )
    else:
        lines.append("| — | — | — | — | — |")
    lines.append("")

    lines.extend(["## Remaining unresolved sections by category", ""])
    append_count_table(
        sorted(
            progress["remaining_queue_category_counts"].items(),
            key=lambda item: (-item[1], item[0]),
        )
    )

    lines.extend(["## Remaining repair queue by subdivision", ""])
    append_count_table(
        sorted(
            progress["remaining_by_subdivision"].items(),
            key=lambda item: (-item[1], item[0]),
        )
    )

    lines.extend(["## Remaining Guofeng items", ""])
    append_count_table(
        sorted(
            progress["remaining_guofeng_by_subdivision"].items(),
            key=lambda item: (-item[1], item[0]),
        )
    )
    for category in QUEUE_CATEGORY_ORDER:
        lines.extend([f"### {QUEUE_CATEGORY_LABELS[category]}", ""])
        append_queue_table(progress["guofeng_queue_categories"][category])

    lines.extend(["## Remaining Xiaoya items", ""])
    append_count_table(
        sorted(
            progress["remaining_xiaoya_by_subdivision"].items(),
            key=lambda item: (-item[1], item[0]),
        )
    )
    append_queue_table(progress["remaining_xiaoya_sections"], include_category=True)

    lines.extend(["## Remaining Daya/Song items", ""])
    append_count_table(
        sorted(
            progress["remaining_daya_song_by_subdivision"].items(),
            key=lambda item: (-item[1], item[0]),
        )
    )
    append_queue_table(progress["remaining_daya_song_sections"], include_category=True)

    lines.extend(["## Known unrecoverable cases", ""])
    append_queue_table(progress["known_unrecoverable_cases"])

    lines.extend(["## Cases needing a better witness", ""])
    append_queue_table(progress["cases_needing_better_witness"], include_category=True)

    lines.extend(
        [
            "",
        "## Witness mix",
        "",
        "| Witness type | Complete sections |",
        "| --- | ---: |",
        ]
    )
    for witness_type, count in sorted(summary["complete_sections_by_witness_type"].items()):
        lines.append(f"| {witness_type} | {count} |")
    lines.extend(
        [
            "",
            "## Verification status mix",
            "",
            "| Status | Complete sections |",
            "| --- | ---: |",
        ]
    )
    for status, count in sorted(summary["complete_sections_by_verification_status"].items()):
        lines.append(f"| {status} | {count} |")

    lines.extend(
        [
            "",
            "## Thresholds",
            "",
            "| Heuristic | Value |",
            "| --- | ---: |",
            f"| english_word_short_threshold | {context['thresholds']['english_word_short_threshold']} |",
            f"| english_word_long_threshold | {context['thresholds']['english_word_long_threshold']} |",
            f"| english_to_chinese_ratio_low_threshold | {context['thresholds']['english_to_chinese_ratio_low_threshold']:.3f} |",
            f"| english_to_chinese_ratio_high_threshold | {context['thresholds']['english_to_chinese_ratio_high_threshold']:.3f} |",
            "",
            "## Non-exportable repair queue",
            "",
            "| Section | Title | Verification status | Decision | Notes |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for section in [
        section
        for section in context["metadata_only_sections"]
        if section.get("verification_decision") == "do_not_export_until_repaired"
    ][:25]:
        lines.append(
            "| {section_id} | {title} | {verification_status} | {decision} | {notes} |".format(
                section_id=section["section_id"],
                title=section["title"],
                verification_status=section.get("verification_status", "—"),
                decision=section.get("verification_decision", "—"),
                notes=(section.get("review_note") or section.get("notes") or "—").replace("\n", " "),
            )
        )

    lines.extend(
        [
            "",
            "## Most flagged sections",
            "",
            "| Section | Title | Witness | Words | Ratio | Flags |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for section in most_flagged_sections:
        lines.append(
            "| {section_id} | {title} | {witness} | {words} | {ratio:.3f} | {flags} |".format(
                section_id=section["section_id"],
                title=section["title"],
                witness=section["source_witness_type"],
                words=section["english_word_count"],
                ratio=section["english_to_chinese_length_ratio"],
                flags=", ".join(section["warnings"]) or "—",
            )
        )

    lines.extend(
        [
            "",
            "## Extreme English/Chinese ratios",
            "",
            "| Section | Title | Ratio | Witness | Notes |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for section in worst_ratio_sections:
        lines.append(
            "| {section_id} | {title} | {ratio:.3f} | {witness} | {notes} |".format(
                section_id=section["section_id"],
                title=section["title"],
                ratio=section["english_to_chinese_length_ratio"],
                witness=section["source_witness_type"],
                notes="; ".join(section["warnings"]) or "—",
            )
        )

    if context["hard_failures"]:
        lines.extend(["", "## Hard failures", ""])
        for failure in context["hard_failures"]:
            lines.append(f"- {failure}")
    else:
        lines.extend(["", "## Hard failures", "", "- None."])

    return "\n".join(lines) + "\n"


def _section_packet_entry(section: dict[str, Any], category: str) -> dict[str, Any]:
    notes_parts = []
    if section.get("review_note"):
        notes_parts.append(section["review_note"])
    if section["warnings"]:
        notes_parts.append("; ".join(section["warnings"]))
    elif section.get("notes"):
        notes_parts.append(section["notes"])
    return {
        "entry_key": f"section:{section['section_id']}",
        "entry_type": "section",
        "category": category,
        "section_id": section["section_id"],
        "title": section["title"],
        "canonical_ref": section["canonical_ref"],
        "alignment_granularity": ", ".join(section["alignment_granularity_values"]),
        "is_coarse_alignment": section["has_coarse_alignment"],
        "notes": " ".join(notes_parts) or "—",
        "chinese_text": section["_chinese_text"],
        "english_text": section["_english_text"],
        "source_urls": section["source_urls"],
    }


def _alignment_packet_entry(
    row: dict[str, Any],
    section_map: dict[str, dict[str, Any]],
    *,
    category: str,
) -> dict[str, Any]:
    section = section_map[row["section_id"]]
    return {
        "entry_key": f"alignment:{row['alignment_id']}",
        "entry_type": "alignment",
        "category": category,
        "section_id": row["section_id"],
        "title": section["title"],
        "canonical_ref": section["canonical_ref"],
        "alignment_granularity": row["alignment_granularity"],
        "is_coarse_alignment": bool(row.get("is_coarse_alignment")),
        "notes": section.get("notes") or "—",
        "chinese_text": row["chinese_text"],
        "english_text": row["translation_text"],
        "source_urls": section["source_urls"],
    }


def build_spotcheck_packet_markdown(context: dict[str, Any]) -> str:
    section_map = {section["section_id"]: section for section in context["sections"]}
    metadata_only_map = {section["section_id"]: section for section in context["metadata_only_sections"]}
    title_only_lost_text_map = {
        section["section_id"]: section for section in context["progress"]["title_only_lost_text_sections"]
    }
    export_rows = [row for section in context["sections"] for row in section["_rows"]]
    section_items: dict[str, dict[str, Any]] = {}
    categories: dict[str, list[str]] = {}

    def add_item(item: dict[str, Any]) -> None:
        key = item["entry_key"]
        categories.setdefault(item["category"], [])
        if key not in section_items:
            section_items[key] = {**item, "categories": [item["category"]]}
        elif item["category"] not in section_items[key]["categories"]:
            section_items[key]["categories"].append(item["category"])
        if key not in categories[item["category"]]:
            categories[item["category"]].append(key)

    for section in sorted(
        (section for section in context["sections"] if section["subdivision"] == "周南"),
        key=lambda section: section["canonical_ref"],
    ):
        add_item(_section_packet_entry(section, "All Zhou Nan poems"))

    for section in sorted(
        (section for section in context["sections"] if section["has_hard_failure"]),
        key=lambda section: section["canonical_ref"],
    ):
        add_item(_section_packet_entry(section, "Every hard failure"))

    for section in sorted(
        (
            section
            for section in context["sections"]
            if section["verification_status"] in {"human_verified_ocr", "human_verified_fulltext"}
        ),
        key=lambda section: section["canonical_ref"],
    ):
        add_item(_section_packet_entry(section, "Every repaired section"))

    for section_id in sorted(title_only_lost_text_map):
        section = title_only_lost_text_map[section_id]
        add_item(
            {
                "entry_key": f"metadata:{section_id}",
                "entry_type": "metadata_only",
                "category": "All title-only lost-text metadata entries",
                "section_id": section["section_id"],
                "title": section["title"],
                "canonical_ref": section["canonical_ref"],
                "alignment_granularity": "metadata_only",
                "is_coarse_alignment": False,
                "notes": section.get("notes") or "Non-exportable metadata-only title.",
                "chinese_text": "_No extant Chinese poem text; title-only canonical entry._",
                "english_text": "_No exportable English text; entry remains metadata-only._",
                "source_urls": section.get("source_urls", []),
                "categories": [],
            }
        )

    for section_id in sorted(metadata_only_map):
        section = metadata_only_map[section_id]
        if section.get("verification_decision") == "do_not_export_until_repaired":
            add_item(
                {
                    "entry_key": f"metadata-reverted:{section_id}",
                    "entry_type": "metadata_only",
                    "category": "Every section moved back to metadata-only",
                    "section_id": section["section_id"],
                    "title": section["title"],
                    "canonical_ref": section["canonical_ref"],
                    "alignment_granularity": "metadata_only",
                    "is_coarse_alignment": False,
                    "notes": section.get("notes") or "Export withdrawn after review.",
                    "chinese_text": "_No exportable Chinese/English alignment after review._",
                    "english_text": "_Export withdrawn; section remains metadata-only pending better witness recovery._",
                    "source_urls": section["source_urls"],
                    "categories": [],
                }
            )

    shortest_rows = sorted(export_rows, key=lambda row: english_word_count(row["translation_text"]))[:10]
    longest_rows = sorted(export_rows, key=lambda row: english_word_count(row["translation_text"]), reverse=True)[:10]
    for row in shortest_rows:
        add_item(_alignment_packet_entry(row, section_map, category="Ten shortest exported English segments"))
    for row in longest_rows:
        add_item(_alignment_packet_entry(row, section_map, category="Ten longest exported English segments"))

    for section in sorted(
        (
            section
            for section in context["sections"]
            if section["has_coarse_alignment"] or "poem" in section["alignment_granularity_values"]
        ),
        key=lambda section: section["canonical_ref"],
    ):
        add_item(_section_packet_entry(section, "All poem-level/coarse alignments"))

    seen_subdivisions: set[tuple[str, str]] = set()
    for section in sorted(context["sections"], key=lambda section: section["canonical_ref"]):
        key = (section["major_division"], section["subdivision"])
        if key in seen_subdivisions:
            continue
        seen_subdivisions.add(key)
        add_item(_section_packet_entry(section, f"Subdivision example: {section['major_division']} / {section['subdivision']}"))

    for section in sorted(
        (section for section in context["sections"] if section["suspiciously_extreme_length_ratio"]),
        key=lambda section: section["english_to_chinese_length_ratio"],
    ):
        add_item(_section_packet_entry(section, "Sections with extreme English/Chinese length ratios"))

    for section in sorted(
        (section for section in context["sections"] if section["warnings"]),
        key=lambda section: (len(section["warnings"]), section["english_word_count"]),
        reverse=True,
    )[:20]:
        add_item(_section_packet_entry(section, "Top 20 remaining warnings"))

    ordered_items = sorted(
        section_items.values(),
        key=lambda item: (
            item["entry_type"] != "metadata_only",
            item["section_id"],
            item["alignment_granularity"],
            item["entry_key"],
        ),
    )
    lines = [
        "# Shijing spot-check packet",
        "",
        "This packet is a human-review sample built from the current Shijing corpus state, including repaired and withdrawn sections.",
        "",
        "## Category coverage",
        "",
        "| Category | Entries |",
        "| --- | ---: |",
    ]
    for category, keys in sorted(categories.items()):
        lines.append(f"| {category} | {len(keys)} |")

    lines.extend(["", "## Detailed entries", ""])
    for item in ordered_items:
        lines.extend(
            [
                f"### {item['section_id']} — {item['title']}",
                "",
                f"- Categories: {', '.join(sorted(item['categories']))}",
                f"- section_id: `{item['section_id']}`",
                f"- canonical_ref: `{item['canonical_ref']}`",
                f"- alignment_granularity: `{item['alignment_granularity']}`",
                f"- is_coarse_alignment: `{str(item['is_coarse_alignment']).lower()}`",
                f"- notes: {item['notes']}",
                "- source URLs:",
            ]
        )
        if item["source_urls"]:
            for url in item["source_urls"]:
                lines.append(f"  - {url}")
        else:
            lines.append("  - _No source URL recorded._")
        lines.extend(
            [
                "",
                "#### Chinese text",
                "",
                "```text",
                item["chinese_text"],
                "```",
                "",
                "#### English text",
                "",
                "```text",
                item["english_text"],
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def build_unresolved_witness_report_markdown(context: dict[str, Any]) -> str:
    progress = context["progress"]
    remaining_sections = progress["remaining_non_exportable_extant_sections"]
    title_only_sections = progress["title_only_lost_text_sections"]

    lines = [
        "# Shijing unresolved witness report",
        "",
        "This report documents the remaining non-exportable *Shijing* gaps after the current verification pass.",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| non_exportable_extant_poems | {progress['non_exportable_extant_poems']} |",
        f"| title_only_lost_text_entries | {progress['title_only_lost_text_entries']} |",
        f"| remaining_likely_repairable_cases | {progress['remaining_likely_repairable_cases']} |",
        f"| remaining_needs_better_witness_cases | {progress['remaining_needs_better_witness_cases']} |",
        f"| remaining_known_unrecoverable_cases | {progress['remaining_known_unrecoverable_cases']} |",
        "",
        "## Remaining non-exportable extant poems",
        "",
        "| Section | Title | Canonical ref | Category | Source checked | Page/anchor | Reason not exportable | Better witness needed |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for section in remaining_sections:
        note = str(section.get("review_note") or "—").replace("\n", " ")
        if section["queue_category"] == "needs_better_witness":
            better_witness = "Cleaner OCR, transcription, or alternate public-domain witness for the blocked poem body."
        elif section["queue_category"] == "unrecoverable_with_current_witness":
            better_witness = "Different public-domain witness; current source is not safely recoverable."
        else:
            better_witness = "Further source investigation or cleaner public-domain witness."
        lines.append(
            "| {section_id} | {title} | {canonical_ref} | {queue_category_label} | {source_volume} | {source_page_or_anchor} | {review_note} | {better_witness} |".format(
                section_id=section["section_id"],
                title=section["title"],
                canonical_ref=section["canonical_ref"],
                queue_category_label=section["queue_category_label"],
                source_volume=section.get("source_volume") or "—",
                source_page_or_anchor=section.get("source_page_or_anchor") or "—",
                review_note=note,
                better_witness=better_witness,
            )
        )
    if not remaining_sections:
        lines.append("| — | — | — | — | — | — | — | — |")

    lines.extend(
        [
            "",
            "## Title-only / lost-text canonical entries",
            "",
            "| Section | Title | Canonical ref | Status | Notes |",
            "| --- | --- | --- | --- | --- |",
        ]
    )
    for section in title_only_sections:
        lines.append(
            "| {section_id} | {title} | {canonical_ref} | {status} | {notes} |".format(
                section_id=section["section_id"],
                title=section["title"],
                canonical_ref=section["canonical_ref"],
                status=section.get("status") or "—",
                notes=str(section.get("notes") or "—").replace("\n", " "),
            )
        )
    if not title_only_sections:
        lines.append("| — | — | — | — | — |")

    return "\n".join(lines)


def write_shijing_quality_outputs(
    context: dict[str, Any],
    *,
    json_output_path: Path = QUALITY_JSON_PATH,
    markdown_output_path: Path = QUALITY_MARKDOWN_PATH,
    spotcheck_output_path: Path = SPOTCHECK_PACKET_PATH,
    unresolved_witness_output_path: Path = UNRESOLVED_WITNESS_REPORT_PATH,
) -> dict[str, Any]:
    report = serializable_quality_report(context)
    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    json_output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_output_path.write_text(quality_markdown(context), encoding="utf-8")
    spotcheck_output_path.parent.mkdir(parents=True, exist_ok=True)
    spotcheck_output_path.write_text(build_spotcheck_packet_markdown(context), encoding="utf-8")
    unresolved_witness_output_path.parent.mkdir(parents=True, exist_ok=True)
    unresolved_witness_output_path.write_text(
        build_unresolved_witness_report_markdown(context),
        encoding="utf-8",
    )
    return report
