from __future__ import annotations

import argparse
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from common import REPO_ROOT, sha256_file, utc_now_iso, write_json, write_jsonl
from ingest_chinesenotes_work import (
    PUBLIC_DOMAIN_RE,
    TRANSLATOR_ATTRIBUTION_RE,
    _extract_notice_lines,
    _parse_section_body,
    _split_chapter_sections,
)

WORK_ID = "laozi"
UPSTREAM_REPOSITORY_URL = "https://github.com/alexamies/chinesenotes.com"
UPSTREAM_COMMIT_SHA = "1f6b1d3e7a40b6886a4b943c898125639e993544"
UPSTREAM_INTRO_RELATIVE_PATH = "corpus/daodejing/daodejing000.txt"
UPSTREAM_MAIN_RELATIVE_PATH = "corpus/daodejing/daodejing001.txt"
UPSTREAM_INTRO_RAW_URL = (
    "https://raw.githubusercontent.com/alexamies/chinesenotes.com/"
    f"{UPSTREAM_COMMIT_SHA}/corpus/daodejing/daodejing000.txt"
)
UPSTREAM_MAIN_RAW_URL = (
    "https://raw.githubusercontent.com/alexamies/chinesenotes.com/"
    f"{UPSTREAM_COMMIT_SHA}/corpus/daodejing/daodejing001.txt"
)
UPSTREAM_INTRO_BLOB_URL = (
    "https://github.com/alexamies/chinesenotes.com/blob/"
    f"{UPSTREAM_COMMIT_SHA}/corpus/daodejing/daodejing000.txt"
)
UPSTREAM_MAIN_BLOB_URL = (
    "https://github.com/alexamies/chinesenotes.com/blob/"
    f"{UPSTREAM_COMMIT_SHA}/corpus/daodejing/daodejing001.txt"
)
SOURCE_REVIEW_DATE = "2026-05-31"
RAW_INTRO_PATH = REPO_ROOT / "corpus" / "raw" / "chinesenotes" / "laozi__daodejing__intro__chinesenotes-1f6b1d3__raw.txt"
RAW_MAIN_PATH = REPO_ROOT / "corpus" / "raw" / "chinesenotes" / "laozi__daodejing__main__chinesenotes-1f6b1d3__raw.txt"
STAGING_ROOT = REPO_ROOT / "corpus" / "staging" / "chinesenotes" / "laozi"
CHINESE_SEGMENT_DIR = REPO_ROOT / "corpus" / "processed" / "chinese_base_texts"
TRANSLATION_SEGMENT_DIR = REPO_ROOT / "corpus" / "processed" / "translations"
ALIGNMENT_DIR = REPO_ROOT / "corpus" / "processed" / "alignments"
MANIFEST_PATH = REPO_ROOT / "metadata" / "manifests" / "laozi.yml"
INVENTORY_PATH = REPO_ROOT / "metadata" / "laozi_inventory.yml"
LEDGER_PATH = REPO_ROOT / "metadata" / "laozi_verification_ledger.yml"
ALIGNMENT_QC_PATH = REPO_ROOT / "logs" / "qc_reports" / "laozi__alignment_qc.json"
COMPLETION_DOC_PATH = REPO_ROOT / "documentation" / "laozi_completion_quality.md"
CHAPTER_HEADING_RE = re.compile(r"^([一二三四五六七八九十百]+)章$")
ENGLISH_SPLIT_RE = re.compile(r"(?<=[.;?!])\s+(?=[\"'(A-Z])")
ENGLISH_SEMICOLON_SPLIT_RE = re.compile(r"(?<=;)\s+(?=[\"'(A-Z])")
CHINESE_SPLIT_RE = re.compile(r"(?<=[。；！？])")
DISPLAYED_TITLE = "Daode Jing 《道德經》"

CHINESE_NUMERAL_DIGITS = {
    "零": 0,
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def _display_path(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def _write_yaml_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _chinese_numeral_to_int(value: str) -> int:
    if value == "十":
        return 10
    if "十" not in value:
        total = 0
        for character in value:
            total = total * 10 + CHINESE_NUMERAL_DIGITS[character]
        return total
    tens, _, ones = value.partition("十")
    tens_value = CHINESE_NUMERAL_DIGITS.get(tens, 1) if tens else 1
    ones_value = CHINESE_NUMERAL_DIGITS.get(ones, 0) if ones else 0
    return tens_value * 10 + ones_value


def _ensure_raw_capture(path: Path, url: str, *, skip_fetch: bool) -> None:
    if path.exists():
        return
    if skip_fetch:
        raise FileNotFoundError(f"Required raw Laozi source is missing: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response:
        path.write_bytes(response.read())


def _split_english_units(text: str) -> list[str]:
    first_pass = ENGLISH_SPLIT_RE.split(text.strip())
    units: list[str] = []
    for piece in first_pass:
        units.extend(part.strip() for part in ENGLISH_SEMICOLON_SPLIT_RE.split(piece) if part.strip())
    return [unit for unit in units if unit]


def _split_chinese_units(text: str) -> list[str]:
    return [piece.strip() for piece in CHINESE_SPLIT_RE.split(text.strip()) if piece.strip()]


def _flatten(units: list[list[str]]) -> list[str]:
    flattened: list[str] = []
    for row in units:
        flattened.extend(row)
    return flattened


def _heading_notes(english_headings: list[str]) -> list[str]:
    cleaned: list[str] = []
    for heading in english_headings:
        note = heading.strip()
        if note.startswith("(") and note.endswith(")"):
            note = note[1:-1].strip()
        if note:
            cleaned.append(note)
    return cleaned


def _parse_laozi_sections() -> list[dict[str, Any]]:
    intro_text = RAW_INTRO_PATH.read_text(encoding="utf-8")
    main_text = RAW_MAIN_PATH.read_text(encoding="utf-8")
    inherited_translator_notes = sorted(
        dict.fromkeys(
            _extract_notice_lines(intro_text, TRANSLATOR_ATTRIBUTION_RE)
            + _extract_notice_lines(main_text, TRANSLATOR_ATTRIBUTION_RE)
        )
    )
    inherited_rights_notes = sorted(
        dict.fromkeys(
            _extract_notice_lines(intro_text, PUBLIC_DOMAIN_RE)
            + _extract_notice_lines(main_text, PUBLIC_DOMAIN_RE)
        )
    )
    source_record = {
        "row_index": 1,
        "source_relative_path": UPSTREAM_MAIN_RELATIVE_PATH,
        "displayed_title": DISPLAYED_TITLE,
        "local_checkout_root": _display_path(REPO_ROOT),
        "local_raw_capture_path": _display_path(RAW_MAIN_PATH),
        "upstream_commit_sha": UPSTREAM_COMMIT_SHA,
        "sha256": sha256_file(RAW_MAIN_PATH),
    }
    parsed_sections: list[dict[str, Any]] = []
    for heading, body in _split_chapter_sections(main_text):
        match = CHAPTER_HEADING_RE.match(heading)
        if match is None:
            continue
        chapter_number = _chinese_numeral_to_int(match.group(1))
        section_record, chinese_blocks, english_blocks, _ = _parse_section_body(
            work_id=WORK_ID,
            section_number=chapter_number,
            heading=heading,
            body=body,
            inherited_translator_notes=inherited_translator_notes,
            inherited_rights_notes=inherited_rights_notes,
            source_record=source_record,
        )
        if section_record["status"] != "exportable_candidate":
            raise ValueError(
                f"Chapter {chapter_number} is not exportable from the Laozi raw capture: "
                f"{section_record['status']} ({section_record['blocking_reason']})"
            )
        parsed_sections.append(
            {
                "section": section_record,
                "chinese_blocks": [record["text_original"] for record in chinese_blocks],
                "english_blocks": [record["text_original"] for record in english_blocks],
            }
        )
    if len(parsed_sections) != 81:
        raise ValueError(f"Expected 81 Laozi chapters, found {len(parsed_sections)}")
    return parsed_sections


def _refine_alignment(section_record: dict[str, Any], chinese_blocks: list[str], english_blocks: list[str]) -> dict[str, Any]:
    chinese_atomic = _flatten([_split_chinese_units(block) for block in chinese_blocks])
    english_atomic = _flatten([_split_english_units(block) for block in english_blocks])
    commentary_present = bool(section_record["commentary_present"])
    heading_present = bool(section_record["english_headings"])
    if len(chinese_blocks) == len(english_blocks):
        return {
            "granularity": "block",
            "source_units": chinese_blocks,
            "target_units": english_blocks,
            "fallback_used": False,
            "coarse_alignment_reason": None,
            "strategy": "block_counts_match",
            "commentary_present": commentary_present,
            "english_heading_present": heading_present,
            "chinese_block_count": len(chinese_blocks),
            "english_block_count": len(english_blocks),
        }
    if len(chinese_blocks) == len(english_atomic):
        return {
            "granularity": "sentence",
            "source_units": chinese_blocks,
            "target_units": english_atomic,
            "fallback_used": False,
            "coarse_alignment_reason": None,
            "strategy": "english_split_to_match_chinese_blocks",
            "commentary_present": commentary_present,
            "english_heading_present": heading_present,
            "chinese_block_count": len(chinese_blocks),
            "english_block_count": len(english_blocks),
        }
    if len(chinese_atomic) == len(english_blocks):
        return {
            "granularity": "sentence",
            "source_units": chinese_atomic,
            "target_units": english_blocks,
            "fallback_used": False,
            "coarse_alignment_reason": None,
            "strategy": "chinese_split_to_match_english_blocks",
            "commentary_present": commentary_present,
            "english_heading_present": heading_present,
            "chinese_block_count": len(chinese_blocks),
            "english_block_count": len(english_blocks),
        }
    if len(chinese_atomic) == len(english_atomic):
        return {
            "granularity": "sentence",
            "source_units": chinese_atomic,
            "target_units": english_atomic,
            "fallback_used": False,
            "coarse_alignment_reason": None,
            "strategy": "both_sides_split_by_punctuation",
            "commentary_present": commentary_present,
            "english_heading_present": heading_present,
            "chinese_block_count": len(chinese_blocks),
            "english_block_count": len(english_blocks),
        }
    reason = (
        "Chinese and English units remained irreconcilable after deterministic block and punctuation splitting "
        f"({len(chinese_blocks)} Chinese blocks, {len(english_blocks)} English blocks, "
        f"{len(chinese_atomic)} Chinese clause units, {len(english_atomic)} English clause units)."
    )
    return {
        "granularity": "chapter",
        "source_units": ["\n\n".join(chinese_blocks)],
        "target_units": ["\n\n".join(english_blocks)],
        "fallback_used": True,
        "coarse_alignment_reason": reason,
        "strategy": "chapter_fallback_after_failed_refinement",
        "commentary_present": commentary_present,
        "english_heading_present": heading_present,
        "chinese_block_count": len(chinese_blocks),
        "english_block_count": len(english_blocks),
    }


def _build_section_manifest_entry(section_record: dict[str, Any], alignment: dict[str, Any], source_id: str, target_source_id: str) -> dict[str, Any]:
    chapter_number = int(section_record["section_number"])
    notes: list[str] = []
    heading_notes = _heading_notes(section_record["english_headings"])
    if heading_notes:
        notes.append("Excluded English headings: " + "; ".join(heading_notes) + ".")
    if section_record["commentary_present"]:
        notes.append("Chinese commentary lines were present in the raw source and excluded from exported segment text.")
    if alignment["fallback_used"]:
        notes.append("Chapter-level fallback used: " + str(alignment["coarse_alignment_reason"]))
    return {
        "section_id": section_record["section_id"],
        "title": section_record["section_label"],
        "label": section_record["section_label"],
        "canonical_ref": f"老子 {chapter_number}",
        "sort_key": f"{chapter_number:03d}",
        "source_ids": {
            "source_id": source_id,
            "target_source_id": target_source_id,
        },
        "alignment_status": "complete",
        "tmx_status": "complete",
        "expected_exact_alignment_count": len(alignment["source_units"]),
        "notes": " ".join(notes) if notes else "",
    }


def _segment_record(
    *,
    section_id: str,
    source_id: str,
    chapter_number: int,
    unit_index: int,
    unit_total: int,
    text: str,
    language: str,
    granularity: str,
) -> dict[str, Any]:
    segment_id = f"{source_id}__seg-{unit_index:03d}"
    canonical_ref = f"老子 {chapter_number}" if granularity == "chapter" else f"老子 {chapter_number}.{unit_index}"
    return {
        "segment_id": segment_id,
        "work_id": WORK_ID,
        "section_id": section_id,
        "source_id": source_id,
        "language": language,
        "segment_type": granularity,
        "segment_order": unit_index,
        "canonical_ref": canonical_ref,
        "sort_key": f"{chapter_number:03d}.{unit_index:03d}" if granularity != "chapter" else f"{chapter_number:03d}.000",
        "text_original": text,
        "text_normalized": text,
        "notes": "",
    }


def _alignment_record(
    *,
    section_id: str,
    alignment_id: str,
    chinese_segment_ids: list[str],
    translation_segment_ids: list[str],
    granularity: str,
    fallback_used: bool,
    coarse_alignment_reason: str | None,
    segment_type: str,
) -> dict[str, Any]:
    return {
        "alignment_id": alignment_id,
        "work_id": WORK_ID,
        "section_id": section_id,
        "alignment_type": "exact_or_near_exact",
        "source_id": chinese_segment_ids[0].split("__seg-", 1)[0],
        "target_source_id": translation_segment_ids[0].split("__seg-", 1)[0],
        "confidence": 1.0,
        "chinese_segment_ids": chinese_segment_ids,
        "translation_segment_ids": translation_segment_ids,
        "alignment_granularity": granularity,
        "section_unit": "chapter",
        "segment_type": segment_type,
        "is_coarse_alignment": fallback_used,
        "coarse_alignment_reason": coarse_alignment_reason,
        "source_segment_count": len(chinese_segment_ids),
        "target_segment_count": len(translation_segment_ids),
        "notes": "",
    }


def _section_group_record(
    *,
    section_id: str,
    chinese_segment_ids: list[str],
    translation_segment_ids: list[str],
    fallback_used: bool,
    coarse_alignment_reason: str | None,
) -> dict[str, Any]:
    return {
        "alignment_id": f"{section_id}__group-001",
        "work_id": WORK_ID,
        "section_id": section_id,
        "source_id": chinese_segment_ids[0].split("__seg-", 1)[0],
        "target_source_id": translation_segment_ids[0].split("__seg-", 1)[0],
        "alignment_type": "section_group",
        "confidence": 1.0,
        "chinese_segment_ids": chinese_segment_ids,
        "translation_segment_ids": translation_segment_ids,
        "alignment_granularity": "chapter",
        "section_unit": "chapter",
        "segment_type": "chapter",
        "is_coarse_alignment": fallback_used,
        "coarse_alignment_reason": coarse_alignment_reason,
        "source_segment_count": len(chinese_segment_ids),
        "target_segment_count": len(translation_segment_ids),
        "notes": "",
    }


def _completion_markdown(report: dict[str, Any]) -> str:
    granularity_rows = "\n".join(
        f"| {granularity} | {count} |" for granularity, count in sorted(report["counts_by_granularity"].items())
    )
    fallback_rows = "\n".join(
        f"| {item['section_id']} | {item['coarse_alignment_reason']} |" for item in report["chapter_fallbacks"]
    )
    if not fallback_rows:
        fallback_rows = "| None | None |"
    blocked_rows = "\n".join(
        f"| {item['section_id']} | {item['reason']} |" for item in report["blocked_chapters"]
    )
    if not blocked_rows:
        blocked_rows = "| None | None |"
    return "\n".join(
        [
            "# Laozi completion quality",
            "",
            "_Generated from `logs/qc_reports/laozi__alignment_qc.json` by `scripts/bootstrap_laozi_corpus.py`._",
            "",
            f"- Generated at: `{report['generated_at']}`",
            f"- Active chapters: **{report['active_chapter_count']} / 81**",
            f"- Exact alignment count: **{report['exact_alignment_count']}**",
            f"- Chapter-level fallbacks: **{report['chapter_fallback_count']}**",
            f"- Blocked chapters: **{report['blocked_chapter_count']}**",
            f"- Commentary exclusions recorded: **{report['commentary_exclusion_count']}**",
            f"- English heading exclusions recorded: **{report['heading_exclusion_count']}**",
            f"- Hard failure count: **{report['hard_failure_count']}**",
            "",
            "## Alignment counts by granularity",
            "",
            "| Granularity | Exact alignments |",
            "| --- | ---: |",
            granularity_rows,
            "",
            "## Chapter-level fallbacks",
            "",
            "| Section | Reason |",
            "| --- | --- |",
            fallback_rows,
            "",
            "## Blocked chapters",
            "",
            "| Section | Reason |",
            "| --- | --- |",
            blocked_rows,
            "",
        ]
    ) + "\n"


def bootstrap_corpus(*, skip_fetch: bool = False) -> dict[str, Any]:
    _ensure_raw_capture(RAW_INTRO_PATH, UPSTREAM_INTRO_RAW_URL, skip_fetch=skip_fetch)
    _ensure_raw_capture(RAW_MAIN_PATH, UPSTREAM_MAIN_RAW_URL, skip_fetch=skip_fetch)
    parsed_sections = _parse_laozi_sections()
    intro_sha256 = sha256_file(RAW_INTRO_PATH)
    main_sha256 = sha256_file(RAW_MAIN_PATH)
    chinese_segments_by_section: dict[str, list[dict[str, Any]]] = {}
    english_segments_by_section: dict[str, list[dict[str, Any]]] = {}
    alignments_by_section: dict[str, list[dict[str, Any]]] = {}
    manifest_sections: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    ledger_entries: list[dict[str, Any]] = []
    inventory_units: list[dict[str, Any]] = []
    counts_by_granularity: Counter[str] = Counter()
    chapter_fallbacks: list[dict[str, str]] = []

    heading_exclusion_count = 0
    commentary_exclusion_count = 0

    for parsed in parsed_sections:
        section_record = parsed["section"]
        chinese_blocks = parsed["chinese_blocks"]
        english_blocks = parsed["english_blocks"]
        chapter_number = int(section_record["section_number"])
        source_suffix = "chinesenotes-daodejing-zh-20260531"
        target_suffix = "legge-chinesenotes-1891"
        source_id = f"{section_record['section_id']}__{source_suffix}"
        target_source_id = f"{section_record['section_id']}__{target_suffix}"
        alignment = _refine_alignment(section_record, chinese_blocks, english_blocks)
        counts_by_granularity[alignment["granularity"]] += len(alignment["source_units"])
        if alignment["fallback_used"]:
            chapter_fallbacks.append(
                {
                    "section_id": section_record["section_id"],
                    "coarse_alignment_reason": str(alignment["coarse_alignment_reason"]),
                }
            )
        if alignment["commentary_present"]:
            commentary_exclusion_count += 1
        if alignment["english_heading_present"]:
            heading_exclusion_count += 1

        chinese_segments: list[dict[str, Any]] = []
        english_segments: list[dict[str, Any]] = []
        exact_alignments: list[dict[str, Any]] = []
        for unit_index, (source_unit, target_unit) in enumerate(
            zip(alignment["source_units"], alignment["target_units"], strict=True), start=1
        ):
            chinese_segment = _segment_record(
                section_id=section_record["section_id"],
                source_id=source_id,
                chapter_number=chapter_number,
                unit_index=unit_index,
                unit_total=len(alignment["source_units"]),
                text=source_unit,
                language="zh-Hant",
                granularity=alignment["granularity"],
            )
            english_segment = _segment_record(
                section_id=section_record["section_id"],
                source_id=target_source_id,
                chapter_number=chapter_number,
                unit_index=unit_index,
                unit_total=len(alignment["target_units"]),
                text=target_unit,
                language="en",
                granularity=alignment["granularity"],
            )
            chinese_segments.append(chinese_segment)
            english_segments.append(english_segment)
            exact_alignments.append(
                _alignment_record(
                    section_id=section_record["section_id"],
                    alignment_id=f"{section_record['section_id']}__align-{unit_index:03d}",
                    chinese_segment_ids=[chinese_segment["segment_id"]],
                    translation_segment_ids=[english_segment["segment_id"]],
                    granularity=alignment["granularity"],
                    fallback_used=alignment["fallback_used"],
                    coarse_alignment_reason=alignment["coarse_alignment_reason"],
                    segment_type=alignment["granularity"],
                )
            )
        exact_alignments.append(
            _section_group_record(
                section_id=section_record["section_id"],
                chinese_segment_ids=[segment["segment_id"] for segment in chinese_segments],
                translation_segment_ids=[segment["segment_id"] for segment in english_segments],
                fallback_used=alignment["fallback_used"],
                coarse_alignment_reason=alignment["coarse_alignment_reason"],
            )
        )
        chinese_segments_by_section[section_record["section_id"]] = chinese_segments
        english_segments_by_section[section_record["section_id"]] = english_segments
        alignments_by_section[section_record["section_id"]] = exact_alignments
        manifest_sections.append(
            _build_section_manifest_entry(section_record, alignment, source_id, target_source_id)
        )

        zh_processed_path = _display_path(
            CHINESE_SEGMENT_DIR
            / f"{WORK_ID}__{section_record['section_id']}__{source_suffix}__segments.jsonl"
        )
        en_processed_path = _display_path(
            TRANSLATION_SEGMENT_DIR
            / f"{WORK_ID}__{section_record['section_id']}__{target_suffix}__segments.jsonl"
        )
        source_notes = (
            "ChineseNotes public-domain Laozi mirror. "
            f"Upstream repository: {UPSTREAM_REPOSITORY_URL} @ {UPSTREAM_COMMIT_SHA}. "
            f"Upstream relative path: {UPSTREAM_MAIN_RELATIVE_PATH}. "
            f"Source SHA256: {main_sha256}. Review date: {SOURCE_REVIEW_DATE}. "
            "Repository-level licence basis: ChineseNotes license.txt states CC BY-SA 3.0 for text files. "
            "Chinese text comes from the Wang Bi recension reflected in the raw ChineseNotes file. "
            f"Local raw capture: {_display_path(RAW_MAIN_PATH)}. "
            f"Local staging source: {_display_path(STAGING_ROOT / 'sections.jsonl')}."
        )
        translation_notes = (
            "ChineseNotes bilingual mirror of James Legge's 1891 translation. "
            f"Upstream repository: {UPSTREAM_REPOSITORY_URL} @ {UPSTREAM_COMMIT_SHA}. "
            f"Upstream relative path: {UPSTREAM_MAIN_RELATIVE_PATH}. "
            f"Source SHA256: {main_sha256}. Review date: {SOURCE_REVIEW_DATE}. "
            "Repository-level licence basis: ChineseNotes license.txt states CC BY-SA 3.0 for text files. "
            "Translator note: Legge 1891. "
            f"Rights/source notes detected by parser: {'; '.join(section_record['source_metadata']['rights_notes'])}. "
            f"Translator/source notes detected by parser: {'; '.join(section_record['source_metadata']['translator_notes'])}. "
            f"Local raw capture: {_display_path(RAW_MAIN_PATH)}. "
            f"Local staging source: {_display_path(STAGING_ROOT / 'sections.jsonl')}."
        )
        sources.extend(
            [
                {
                    "work_id": WORK_ID,
                    "section_id": section_record["section_id"],
                    "source_id": source_id,
                    "language_code": "zh-Hant",
                    "source_kind": "base_text",
                    "citation": (
                        f"老子 {chapter_number}, ChineseNotes daodejing001.txt, reviewed {SOURCE_REVIEW_DATE}, "
                        f"upstream commit {UPSTREAM_COMMIT_SHA}."
                    ),
                    "source_url": UPSTREAM_MAIN_BLOB_URL,
                    "rights_status": "public_domain",
                    "author_or_translator_ids": ["laozi-tradition"],
                    "raw_path": _display_path(RAW_MAIN_PATH),
                    "processed_path": zh_processed_path,
                    "notes": source_notes,
                },
                {
                    "work_id": WORK_ID,
                    "section_id": section_record["section_id"],
                    "source_id": target_source_id,
                    "language_code": "en",
                    "source_kind": "translation",
                    "citation": (
                        f"James Legge, 'The Tao Teh King' (1891), mirrored in ChineseNotes daodejing001.txt, "
                        f"reviewed {SOURCE_REVIEW_DATE}, upstream commit {UPSTREAM_COMMIT_SHA}."
                    ),
                    "source_url": UPSTREAM_MAIN_BLOB_URL,
                    "rights_status": "public_domain",
                    "author_or_translator_ids": ["james-legge"],
                    "raw_path": _display_path(RAW_MAIN_PATH),
                    "processed_path": en_processed_path,
                    "notes": translation_notes,
                },
            ]
        )
        heading_notes = _heading_notes(section_record["english_headings"])
        ledger_entries.append(
            {
                "section_id": section_record["section_id"],
                "title": section_record["section_label"],
                "canonical_ref": f"老子 {chapter_number}",
                "source_volume": "ChineseNotes / Daode Jing 《道德經》",
                "source_page_or_anchor": UPSTREAM_MAIN_BLOB_URL,
                "raw_source_path": _display_path(RAW_MAIN_PATH),
                "processed_source_path": zh_processed_path,
                "processed_translation_path": en_processed_path,
                "upstream_repository_url": UPSTREAM_REPOSITORY_URL,
                "upstream_commit_sha": UPSTREAM_COMMIT_SHA,
                "upstream_relative_path": UPSTREAM_MAIN_RELATIVE_PATH,
                "source_sha256": main_sha256,
                "intro_source_sha256": intro_sha256,
                "repository_level_licence_basis": "ChineseNotes license.txt states CC BY-SA 3.0 for text files.",
                "translator_note": "Legge 1891",
                "rights_or_source_notes": section_record["source_metadata"]["rights_notes"],
                "translator_or_source_notes": section_record["source_metadata"]["translator_notes"],
                "local_staging_path": _display_path(STAGING_ROOT / "sections.jsonl"),
                "local_raw_capture_path": _display_path(RAW_MAIN_PATH),
                "verification_status": "verified_transcribed_text",
                "reviewer_note": (
                    "ChineseNotes bilingual file parsed cleanly; commentary and English headings were excluded "
                    "from exportable segment text before alignment."
                ),
                "extraction_method": "chinesenotes_public_domain_mirror",
                "alignment_status": "complete",
                "alignment_granularity": alignment["granularity"],
                "exact_alignment_count": len(alignment["source_units"]),
                "commentary_present_and_excluded": bool(section_record["commentary_present"]),
                "english_heading_present_and_excluded": bool(heading_notes),
                "excluded_english_headings": heading_notes,
                "fallback_used": alignment["fallback_used"],
                "coarse_alignment_reason": alignment["coarse_alignment_reason"],
                "decision": "export",
            }
        )
        inventory_units.append(
            {
                "section_id": section_record["section_id"],
                "title": section_record["section_label"],
                "canonical_ref": f"老子 {chapter_number}",
                "sort_key": f"{chapter_number:03d}",
                "unit_type": "chapter",
                "text_status": "extant",
                "coverage_status": "complete",
                "zh_page_url": UPSTREAM_MAIN_BLOB_URL,
                "english_witness_status": "verified_transcribed_text",
                "verification_status": "verified_transcribed_text",
                "source_volume": "ChineseNotes / Daode Jing 《道德經》",
                "translator": "James Legge",
                "decision": "export",
            }
        )

    CHINESE_SEGMENT_DIR.mkdir(parents=True, exist_ok=True)
    TRANSLATION_SEGMENT_DIR.mkdir(parents=True, exist_ok=True)
    ALIGNMENT_DIR.mkdir(parents=True, exist_ok=True)
    for section in manifest_sections:
        source_suffix = section["source_ids"]["source_id"].split("__", 1)[1]
        target_suffix = section["source_ids"]["target_source_id"].split("__", 1)[1]
        section_id = section["section_id"]
        write_jsonl(
            CHINESE_SEGMENT_DIR / f"{WORK_ID}__{section_id}__{source_suffix}__segments.jsonl",
            chinese_segments_by_section[section_id],
        )
        write_jsonl(
            TRANSLATION_SEGMENT_DIR / f"{WORK_ID}__{section_id}__{target_suffix}__segments.jsonl",
            english_segments_by_section[section_id],
        )
        write_jsonl(
            ALIGNMENT_DIR / f"{WORK_ID}__{section_id}__{source_suffix}__{target_suffix}__alignments.jsonl",
            alignments_by_section[section_id],
        )

    exact_alignment_count = sum(section["expected_exact_alignment_count"] for section in manifest_sections)
    manifest = {
        "work_id": WORK_ID,
        "work_status": "complete",
        "source_pair_defaults": {
            "source_id": "chinesenotes-daodejing-zh-20260531",
            "target_source_id": "legge-chinesenotes-1891",
            "source_language": "zh-Hant",
            "target_language": "en",
        },
        "summary": {
            "section_count": len(manifest_sections),
            "complete_sections": len(manifest_sections),
            "metadata_only_sections": 0,
            "sections_needing_alignment": 0,
            "sections_needing_qc": 0,
            "exact_alignment_count": exact_alignment_count,
        },
        "ingestion_policy": {
            "inventory_required": True,
            "inventory_path": _display_path(INVENTORY_PATH),
            "inventory_unit_key": "units",
            "inventory_derivation": "generated_from_raw_chinesenotes_laozi_bootstrap",
            "ingestion_plan_required": True,
            "ingestion_plan_path": "documentation/laozi_ingestion_plan.md",
            "source_audit_required": True,
            "source_audit_path": "documentation/laozi_ingestion_plan.md",
            "granularity_policy_required": True,
            "granularity_policy_path": "documentation/alignment_granularity_policy.md",
            "section_unit": "chapter",
            "preferred_segment_unit": "block",
            "minimum_required_alignment_scope": "chapter",
            "maximum_exact_alignment_scope": "chapter",
            "allowed_segment_units": ["line", "sentence", "block", "chapter"],
            "coarse_alignment_units": ["chapter"],
            "granularity_order": ["line", "sentence", "block", "chapter"],
            "metadata_only_allowed": False,
            "missing_text_policy": "block_export_if_clean_chinese_or_english_text_is_missing",
            "commentary_policy": "exclude_commentary_headings_and_notice_lines_from_exportable_segments_before_alignment",
            "rights_policy": "public_domain_only_for_export_with_explicit_chinesenotes_provenance",
            "allowed_export_rights_statuses": ["public_domain"],
            "section_group_export_policy": "forbidden",
            "completion_definition": (
                "A Laozi chapter is complete only when the ChineseNotes bilingual source is parsed into clean "
                "Chinese and English segment text, commentary/headings/notices are excluded, deterministic "
                "fine-grained alignment is attempted, and any chapter-level fallback is exported with an "
                "explicit coarse_alignment_reason."
            ),
        },
        "romanization_aliases": [
            {
                "entity_type": "work",
                "entity_id": WORK_ID,
                "alias": "Laozi",
                "romanization_system": "pinyin",
            },
            {
                "entity_type": "work",
                "entity_id": WORK_ID,
                "alias": "Daodejing",
                "romanization_system": "pinyin",
            },
            {
                "entity_type": "work",
                "entity_id": WORK_ID,
                "alias": "Dao De Jing",
                "romanization_system": "english-title",
            },
            {
                "entity_type": "work",
                "entity_id": WORK_ID,
                "alias": "Tao Te Ching",
                "romanization_system": "Legge-Wade-Giles",
            },
        ]
        + [
            {
                "entity_type": "section",
                "entity_id": section["section_id"],
                "alias": f"Chapter {index}",
                "romanization_system": "english-reference",
            }
            for index, section in enumerate(manifest_sections, start=1)
        ],
        "sections": manifest_sections,
        "sources": sources,
        "ingestion_log": [
            {
                "run_id": f"bootstrap-{WORK_ID}-20260531",
                "work_id": WORK_ID,
                "timestamp": utc_now_iso(),
                "method": "bootstrap_laozi_corpus",
                "status": "complete",
                "notes": (
                    "Promoted Laozi into the active corpus from the ChineseNotes Daodejing bilingual witness with "
                    "deterministic refinement and explicit chapter-level fallback reasons."
                ),
            }
        ],
    }
    inventory = {
        "work_id": WORK_ID,
        "source": "ChineseNotes Laozi bootstrap",
        "units": inventory_units,
    }
    qc_report = {
        "work_id": WORK_ID,
        "generated_at": utc_now_iso(),
        "upstream_repository": UPSTREAM_REPOSITORY_URL,
        "upstream_commit_sha": UPSTREAM_COMMIT_SHA,
        "raw_capture_path": _display_path(RAW_MAIN_PATH),
        "active_chapter_count": len(manifest_sections),
        "exact_alignment_count": exact_alignment_count,
        "counts_by_granularity": dict(sorted(counts_by_granularity.items())),
        "chapter_fallback_count": len(chapter_fallbacks),
        "chapter_fallbacks": chapter_fallbacks,
        "blocked_chapter_count": 0,
        "blocked_chapters": [],
        "commentary_exclusion_count": commentary_exclusion_count,
        "heading_exclusion_count": heading_exclusion_count,
        "hard_failure_count": 0,
        "chapters": [
            {
                "section_id": entry["section_id"],
                "chapter_number": int(entry["section_id"].split("-")[-1]),
                "chinese_block_count": next(
                    parsed["section"]["chinese_block_count"]
                    for parsed in parsed_sections
                    if parsed["section"]["section_id"] == entry["section_id"]
                ),
                "english_block_count": next(
                    parsed["section"]["english_block_count"]
                    for parsed in parsed_sections
                    if parsed["section"]["section_id"] == entry["section_id"]
                ),
                "final_alignment_granularity": entry["alignment_granularity"],
                "exact_alignment_count": entry["exact_alignment_count"],
                "commentary_present_and_excluded": entry["commentary_present_and_excluded"],
                "english_heading_present_and_excluded": entry["english_heading_present_and_excluded"],
                "fallback_used": entry["fallback_used"],
                "coarse_alignment_reason": entry["coarse_alignment_reason"],
            }
            for entry in ledger_entries
        ],
    }
    _write_yaml_json(MANIFEST_PATH, manifest)
    _write_yaml_json(INVENTORY_PATH, inventory)
    _write_yaml_json(LEDGER_PATH, {"entries": ledger_entries})
    write_json(ALIGNMENT_QC_PATH, qc_report)
    COMPLETION_DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    COMPLETION_DOC_PATH.write_text(_completion_markdown(qc_report), encoding="utf-8")
    return {
        "section_count": len(manifest_sections),
        "exact_alignment_count": exact_alignment_count,
        "counts_by_granularity": dict(sorted(counts_by_granularity.items())),
        "chapter_fallback_count": len(chapter_fallbacks),
        "blocked_chapter_count": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap active Laozi corpus files from the ChineseNotes witness.")
    parser.add_argument("--skip-fetch", action="store_true", help="Require committed raw captures instead of fetching.")
    args = parser.parse_args()
    print(json.dumps(bootstrap_corpus(skip_fetch=args.skip_fetch), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
