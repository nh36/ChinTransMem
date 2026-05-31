from __future__ import annotations

import argparse
import json
import re
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from common import REPO_ROOT, load_json_compatible_yaml, sha256_file, write_json, write_jsonl
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
BOOTSTRAP_TIMESTAMP = "2026-05-31T00:00:00+00:00"
RAW_INTRO_PATH = REPO_ROOT / "corpus" / "raw" / "chinesenotes" / "laozi__daodejing__intro__chinesenotes-1f6b1d3__raw.txt"
RAW_MAIN_PATH = REPO_ROOT / "corpus" / "raw" / "chinesenotes" / "laozi__daodejing__main__chinesenotes-1f6b1d3__raw.txt"
STAGING_ROOT = REPO_ROOT / "corpus" / "staging" / "chinesenotes" / "laozi"
CHINESE_SEGMENT_DIR = REPO_ROOT / "corpus" / "processed" / "chinese_base_texts"
TRANSLATION_SEGMENT_DIR = REPO_ROOT / "corpus" / "processed" / "translations"
ALIGNMENT_DIR = REPO_ROOT / "corpus" / "processed" / "alignments"
MANIFEST_PATH = REPO_ROOT / "metadata" / "manifests" / "laozi.yml"
INVENTORY_PATH = REPO_ROOT / "metadata" / "laozi_inventory.yml"
LEDGER_PATH = REPO_ROOT / "metadata" / "laozi_verification_ledger.yml"
OVERRIDES_PATH = REPO_ROOT / "metadata" / "laozi_alignment_overrides.yml"
ALIGNMENT_QC_PATH = REPO_ROOT / "logs" / "qc_reports" / "laozi__alignment_qc.json"
COMPLETION_DOC_PATH = REPO_ROOT / "documentation" / "laozi_completion_quality.md"
CHAPTER_HEADING_RE = re.compile(r"^([一二三四五六七八九十百]+)章$")
ENGLISH_SPLIT_RE = re.compile(r"(?<=[.;?!:])\s+")
CHINESE_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。；！？])")
CHINESE_FINE_SPLIT_RE = re.compile(r"(?<=[，、；。！？])")
SHORT_ENGLISH_CONTINUATION_RE = re.compile(r"^[\"'“”‘’()\\-–—]*?(and|or|nor)\b", re.IGNORECASE)
ENGLISH_WORD_RE = re.compile(r"[A-Za-z']+")
CHINESE_PUNCTUATION_RE = re.compile(r"[，、；。！？「」『』（）()—-]")
DISPLAYED_TITLE = "Daode Jing 《道德經》"
MAX_ALIGNMENT_GROUP_SIZE = 4
AUTO_GROUPING_PENALTY = 0.2
QUESTION_MISMATCH_PENALTY = 0.7
SHORT_ENGLISH_CONTINUATION_WORD_LIMIT = 6

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


def _english_word_count(text: str) -> int:
    return len(ENGLISH_WORD_RE.findall(text))


def _chinese_char_count(text: str) -> int:
    return len(CHINESE_PUNCTUATION_RE.sub("", text))


def _major_clause_count(text: str, *, language: str) -> int:
    if not text.strip():
        return 0
    if language == "zh":
        return sum(text.count(marker) for marker in ("。", "；", "？", "！")) or 1
    return sum(text.count(marker) for marker in (".", ";", "?", "!", ":")) or 1


def _ends_with_question(text: str) -> bool:
    return text.strip().endswith(("?", "？"))


def _split_english_units(text: str) -> list[str]:
    raw_units = [piece.strip() for piece in ENGLISH_SPLIT_RE.split(text.strip()) if piece.strip()]
    merged_units: list[str] = []
    for unit in raw_units:
        if (
            merged_units
            and _english_word_count(unit) <= SHORT_ENGLISH_CONTINUATION_WORD_LIMIT
            and SHORT_ENGLISH_CONTINUATION_RE.match(unit)
        ):
            merged_units[-1] = f"{merged_units[-1]} {unit}"
            continue
        merged_units.append(unit)
    return merged_units


def _split_chinese_sentence_units(text: str) -> list[str]:
    return [piece.strip() for piece in CHINESE_SENTENCE_SPLIT_RE.split(text.strip()) if piece.strip()]


def _split_chinese_units(text: str) -> list[str]:
    return [piece.strip() for piece in CHINESE_FINE_SPLIT_RE.split(text.strip()) if piece.strip()]


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


def _merge_units_text(units: list[str], *, language: str) -> str:
    if language == "zh":
        return "".join(units)
    return " ".join(units)


def _build_unit_records(blocks: list[str], *, language: str) -> list[dict[str, Any]]:
    splitter = _split_chinese_units if language == "zh" else _split_english_units
    records: list[dict[str, Any]] = []
    unit_index = 1
    for block_index, block in enumerate(blocks, start=1):
        for text in splitter(block):
            records.append(
                {
                    "unit_id": unit_index,
                    "block_index": block_index,
                    "text": text,
                }
            )
            unit_index += 1
    return records


def _group_cost(source_group: list[dict[str, Any]], target_group: list[dict[str, Any]], scale: float) -> float:
    import math

    source_length = sum(_chinese_char_count(unit["text"]) for unit in source_group)
    target_length = sum(_english_word_count(unit["text"]) for unit in target_group)
    ratio_cost = abs(math.log((target_length + 1) / (source_length * scale + 1)))
    grouping_cost = AUTO_GROUPING_PENALTY * ((len(source_group) - 1) + (len(target_group) - 1))
    question_penalty = (
        QUESTION_MISMATCH_PENALTY
        if _ends_with_question(source_group[-1]["text"]) != _ends_with_question(target_group[-1]["text"])
        else 0.0
    )
    return ratio_cost + grouping_cost + question_penalty


def _group_monotonic_units(
    source_units: list[dict[str, Any]],
    target_units: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    import math

    source_total = sum(_chinese_char_count(unit["text"]) for unit in source_units)
    target_total = sum(_english_word_count(unit["text"]) for unit in target_units)
    scale = target_total / max(1, source_total)
    source_count = len(source_units)
    target_count = len(target_units)
    infinity = float("inf")
    dp = [[infinity] * (target_count + 1) for _ in range(source_count + 1)]
    previous: list[list[tuple[int, int, int, int] | None]] = [
        [None] * (target_count + 1) for _ in range(source_count + 1)
    ]
    dp[0][0] = 0.0
    for source_index in range(source_count + 1):
        for target_index in range(target_count + 1):
            current_cost = dp[source_index][target_index]
            if math.isinf(current_cost):
                continue
            for source_group_size in range(1, min(MAX_ALIGNMENT_GROUP_SIZE, source_count - source_index) + 1):
                for target_group_size in range(1, min(MAX_ALIGNMENT_GROUP_SIZE, target_count - target_index) + 1):
                    next_source = source_index + source_group_size
                    next_target = target_index + target_group_size
                    candidate_cost = current_cost + _group_cost(
                        source_units[source_index:next_source],
                        target_units[target_index:next_target],
                        scale,
                    )
                    if candidate_cost < dp[next_source][next_target]:
                        dp[next_source][next_target] = candidate_cost
                        previous[next_source][next_target] = (
                            source_index,
                            target_index,
                            source_group_size,
                            target_group_size,
                        )
    groups: list[dict[str, Any]] = []
    source_index = source_count
    target_index = target_count
    while (source_index, target_index) != (0, 0):
        cursor = previous[source_index][target_index]
        if cursor is None:
            raise ValueError("Unable to reconstruct Laozi grouped alignment path.")
        previous_source, previous_target, source_group_size, target_group_size = cursor
        groups.append(
            {
                "source_indexes": list(range(previous_source + 1, source_index + 1)),
                "target_indexes": list(range(previous_target + 1, target_index + 1)),
            }
        )
        source_index = previous_source
        target_index = previous_target
    groups.reverse()
    return groups


def _load_alignment_overrides() -> dict[str, dict[str, Any]]:
    if not OVERRIDES_PATH.exists():
        return {}
    payload = load_json_compatible_yaml(OVERRIDES_PATH)
    sections = payload.get("sections", [])
    return {section["section_id"]: section for section in sections}


def _validate_override_groups(
    section_id: str,
    source_units: list[dict[str, Any]],
    target_units: list[dict[str, Any]],
    groups: list[dict[str, Any]],
) -> None:
    expected_source = list(range(1, len(source_units) + 1))
    expected_target = list(range(1, len(target_units) + 1))
    seen_source = [index for group in groups for index in group["source_indexes"]]
    seen_target = [index for group in groups for index in group["target_indexes"]]
    if seen_source != expected_source:
        raise ValueError(f"{section_id}: curated Laozi override does not consume source units contiguously.")
    if seen_target != expected_target:
        raise ValueError(f"{section_id}: curated Laozi override does not consume target units contiguously.")


def _build_override_alignment(
    section_record: dict[str, Any],
    chinese_blocks: list[str],
    english_blocks: list[str],
    override: dict[str, Any],
) -> dict[str, Any]:
    source_units = _build_unit_records(chinese_blocks, language="zh")
    target_units = _build_unit_records(english_blocks, language="en")
    groups = [
        {
            "alignment_id": item["alignment_id"],
            "source_indexes": item["source_unit_ids"],
            "target_indexes": item["target_unit_ids"],
        }
        for item in override["alignments"]
    ]
    _validate_override_groups(section_record["section_id"], source_units, target_units, groups)
    return {
        "granularity": "grouped",
        "segment_granularity": "sentence",
        "source_units": [unit["text"] for unit in source_units],
        "target_units": [unit["text"] for unit in target_units],
        "groups": groups,
        "fallback_used": False,
        "coarse_alignment_reason": None,
        "strategy": "curated_override",
        "curated_override_used": True,
        "curated_override_reason": override["reason_automatic_alignment_failed"],
        "curator_note": override["curator_note"],
        "review_status": override["review_status"],
        "commentary_present": bool(section_record["commentary_present"]),
        "english_heading_present": bool(section_record["english_headings"]),
        "chinese_block_count": len(chinese_blocks),
        "english_block_count": len(english_blocks),
    }


def _has_false_precision_pattern(source_text: str, target_text: str) -> bool:
    return (
        _major_clause_count(target_text, language="en") >= 2
        and _major_clause_count(source_text, language="zh") <= 1
        and _english_word_count(target_text) >= 16
        and _chinese_char_count(source_text) <= 12
    )


def _alignment_quality_issues(alignment: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    source_units = alignment["source_units"]
    target_units = alignment["target_units"]
    for group in alignment["groups"]:
        source_group = [source_units[index - 1] for index in group["source_indexes"]]
        target_group = [target_units[index - 1] for index in group["target_indexes"]]
        source_text = _merge_units_text(source_group, language="zh")
        target_text = _merge_units_text(target_group, language="en")
        if (
            len(group["source_indexes"]) == 1
            and len(group["target_indexes"]) == 1
            and _has_false_precision_pattern(source_text, target_text)
        ):
            issues.append(f"{group['alignment_id']}: false_precision_multi_clause_target")
        if len(group["source_indexes"]) == 1 and len(group["target_indexes"]) == 1 and (
            _ends_with_question(source_text) != _ends_with_question(target_text)
        ):
            issues.append(f"{group['alignment_id']}: question_punctuation_mismatch")
    return issues


def _can_use_block_alignment(chinese_blocks: list[str], english_blocks: list[str]) -> bool:
    if len(chinese_blocks) != len(english_blocks):
        return False
    for chinese_block, english_block in zip(chinese_blocks, english_blocks, strict=True):
        if len(_split_chinese_units(chinese_block)) != 1:
            return False
        if len(_split_english_units(english_block)) != 1:
            return False
        if _has_false_precision_pattern(chinese_block, english_block):
            return False
    return True


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


def _refine_alignment(
    section_record: dict[str, Any],
    chinese_blocks: list[str],
    english_blocks: list[str],
    *,
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if override is not None:
        alignment = _build_override_alignment(section_record, chinese_blocks, english_blocks, override)
        alignment["quality_issues"] = _alignment_quality_issues(alignment)
        if alignment["quality_issues"]:
            raise ValueError(
                f"{section_record['section_id']}: curated Laozi override still fails alignment QC: "
                f"{alignment['quality_issues']}"
            )
        return alignment

    commentary_present = bool(section_record["commentary_present"])
    heading_present = bool(section_record["english_headings"])
    if _can_use_block_alignment(chinese_blocks, english_blocks):
        alignment = {
            "granularity": "block",
            "segment_granularity": "block",
            "source_units": chinese_blocks,
            "target_units": english_blocks,
            "groups": [
                {
                    "alignment_id": f"{section_record['section_id']}__align-{index:03d}",
                    "source_indexes": [index],
                    "target_indexes": [index],
                }
                for index in range(1, len(chinese_blocks) + 1)
            ],
            "fallback_used": False,
            "coarse_alignment_reason": None,
            "strategy": "block_boundaries_already_correspond",
            "curated_override_used": False,
            "commentary_present": commentary_present,
            "english_heading_present": heading_present,
            "chinese_block_count": len(chinese_blocks),
            "english_block_count": len(english_blocks),
        }
        alignment["quality_issues"] = _alignment_quality_issues(alignment)
        if alignment["quality_issues"]:
            raise ValueError(
                f"{section_record['section_id']}: Laozi block alignment failed QC and needs a curated override: "
                f"{alignment['quality_issues']}"
            )
        return alignment

    source_units = _build_unit_records(chinese_blocks, language="zh")
    target_units = _build_unit_records(english_blocks, language="en")
    groups = _group_monotonic_units(source_units, target_units)
    grouped_alignment = {
        "granularity": (
            "sentence"
            if all(len(group["source_indexes"]) == 1 and len(group["target_indexes"]) == 1 for group in groups)
            else "grouped"
        ),
        "segment_granularity": "sentence",
        "source_units": [unit["text"] for unit in source_units],
        "target_units": [unit["text"] for unit in target_units],
        "groups": [
            {
                "alignment_id": f"{section_record['section_id']}__align-{index:03d}",
                "source_indexes": group["source_indexes"],
                "target_indexes": group["target_indexes"],
            }
            for index, group in enumerate(groups, start=1)
        ],
        "fallback_used": False,
        "coarse_alignment_reason": None,
        "strategy": "monotonic_grouped_auto_alignment",
        "curated_override_used": False,
        "commentary_present": commentary_present,
        "english_heading_present": heading_present,
        "chinese_block_count": len(chinese_blocks),
        "english_block_count": len(english_blocks),
    }
    grouped_alignment["quality_issues"] = _alignment_quality_issues(grouped_alignment)
    if grouped_alignment["quality_issues"]:
        raise ValueError(
            f"{section_record['section_id']}: Laozi automatic alignment failed QC and needs a curated override: "
            f"{grouped_alignment['quality_issues']}"
        )
    return grouped_alignment


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
    if alignment.get("curated_override_used"):
        notes.append("Curated grouped override applied after automatic alignment failed section-level QC.")
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
        "expected_exact_alignment_count": len(alignment["groups"]),
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
    curated_rows = "\n".join(
        f"| {item['section_id']} | {item['reason_automatic_alignment_failed']} | {item['curator_note']} |"
        for item in report["curated_override_sections"]
    )
    if not curated_rows:
        curated_rows = "| None | None | None |"
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
            f"- Automatic fine-grained alignments: **{report['automatic_fine_grained_alignment_count']}**",
            f"- Curated override alignments: **{report['curated_override_alignment_count']}**",
            f"- Curated override chapters: **{report['curated_override_chapter_count']}**",
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
            "## Curated override chapters",
            "",
            "| Section | Why automatic alignment failed | Curator note |",
            "| --- | --- | --- |",
            curated_rows,
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
    overrides = _load_alignment_overrides()
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
    curated_override_sections: list[dict[str, str]] = []
    automatic_fine_grained_alignment_count = 0
    curated_override_alignment_count = 0

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
        alignment = _refine_alignment(
            section_record,
            chinese_blocks,
            english_blocks,
            override=overrides.get(section_record["section_id"]),
        )
        counts_by_granularity[alignment["granularity"]] += len(alignment["groups"])
        if alignment["fallback_used"]:
            chapter_fallbacks.append(
                {
                    "section_id": section_record["section_id"],
                    "coarse_alignment_reason": str(alignment["coarse_alignment_reason"]),
                }
            )
        if alignment.get("curated_override_used"):
            curated_override_sections.append(
                {
                    "section_id": section_record["section_id"],
                    "reason_automatic_alignment_failed": str(alignment["curated_override_reason"]),
                    "curator_note": str(alignment["curator_note"]),
                }
            )
            curated_override_alignment_count += len(alignment["groups"])
        else:
            automatic_fine_grained_alignment_count += len(alignment["groups"])
        if alignment["commentary_present"]:
            commentary_exclusion_count += 1
        if alignment["english_heading_present"]:
            heading_exclusion_count += 1

        chinese_segments: list[dict[str, Any]] = []
        english_segments: list[dict[str, Any]] = []
        exact_alignments: list[dict[str, Any]] = []
        for unit_index, source_unit in enumerate(alignment["source_units"], start=1):
            chinese_segment = _segment_record(
                section_id=section_record["section_id"],
                source_id=source_id,
                chapter_number=chapter_number,
                unit_index=unit_index,
                unit_total=len(alignment["source_units"]),
                text=source_unit,
                language="zh-Hant",
                granularity=alignment["segment_granularity"],
            )
            chinese_segments.append(chinese_segment)
        for unit_index, target_unit in enumerate(alignment["target_units"], start=1):
            english_segment = _segment_record(
                section_id=section_record["section_id"],
                source_id=target_source_id,
                chapter_number=chapter_number,
                unit_index=unit_index,
                unit_total=len(alignment["target_units"]),
                text=target_unit,
                language="en",
                granularity=alignment["segment_granularity"],
            )
            english_segments.append(english_segment)
        for group in alignment["groups"]:
            exact_alignments.append(
                _alignment_record(
                    section_id=section_record["section_id"],
                    alignment_id=group["alignment_id"],
                    chinese_segment_ids=[chinese_segments[index - 1]["segment_id"] for index in group["source_indexes"]],
                    translation_segment_ids=[
                        english_segments[index - 1]["segment_id"] for index in group["target_indexes"]
                    ],
                    granularity=alignment["granularity"],
                    fallback_used=alignment["fallback_used"],
                    coarse_alignment_reason=alignment["coarse_alignment_reason"],
                    segment_type=alignment["segment_granularity"],
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
                "alignment_strategy": alignment["strategy"],
                "segment_granularity": alignment["segment_granularity"],
                "exact_alignment_count": len(alignment["groups"]),
                "commentary_present_and_excluded": bool(section_record["commentary_present"]),
                "english_heading_present_and_excluded": bool(heading_notes),
                "excluded_english_headings": heading_notes,
                "curated_override_used": bool(alignment.get("curated_override_used")),
                "reason_automatic_alignment_failed": alignment.get("curated_override_reason"),
                "curator_note": alignment.get("curator_note"),
                "review_status": alignment.get("review_status"),
                "alignment_quality_issues": alignment["quality_issues"],
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
            "preferred_segment_unit": "sentence",
            "minimum_required_alignment_scope": "chapter",
            "maximum_exact_alignment_scope": "chapter",
            "allowed_segment_units": ["line", "sentence", "grouped", "block", "chapter"],
            "coarse_alignment_units": ["chapter"],
            "granularity_order": ["line", "sentence", "grouped", "block", "chapter"],
            "metadata_only_allowed": False,
            "missing_text_policy": "block_export_if_clean_chinese_or_english_text_is_missing",
            "commentary_policy": "exclude_commentary_headings_and_notice_lines_from_exportable_segments_before_alignment",
            "rights_policy": "public_domain_only_for_export_with_explicit_chinesenotes_provenance",
            "allowed_export_rights_statuses": ["public_domain"],
            "section_group_export_policy": "forbidden",
            "completion_definition": (
                "A Laozi chapter is complete only when the ChineseNotes bilingual source is parsed into clean "
                "Chinese and English segment text, commentary/headings/notices are excluded, deterministic "
                "fine-grained grouping is attempted, curated overrides are applied where automatic alignment "
                "fails section-level QC, and any remaining chapter-level fallback is exported with an explicit "
                "coarse_alignment_reason."
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
                "timestamp": BOOTSTRAP_TIMESTAMP,
                "method": "bootstrap_laozi_corpus",
                "status": "complete",
                "notes": (
                    "Improved Laozi fine-grained alignment using grouped monotonic auto-alignment plus curated "
                    "overrides for chapters that failed the automatic QC heuristics."
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
        "generated_at": BOOTSTRAP_TIMESTAMP,
        "upstream_repository": UPSTREAM_REPOSITORY_URL,
        "upstream_commit_sha": UPSTREAM_COMMIT_SHA,
        "raw_capture_path": _display_path(RAW_MAIN_PATH),
        "active_chapter_count": len(manifest_sections),
        "exact_alignment_count": exact_alignment_count,
        "counts_by_granularity": dict(sorted(counts_by_granularity.items())),
        "automatic_fine_grained_alignment_count": automatic_fine_grained_alignment_count,
        "curated_override_alignment_count": curated_override_alignment_count,
        "curated_override_chapter_count": len(curated_override_sections),
        "curated_override_sections": curated_override_sections,
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
                "alignment_strategy": entry["alignment_strategy"],
                "segment_granularity": entry["segment_granularity"],
                "curated_override_used": entry["curated_override_used"],
                "reason_automatic_alignment_failed": entry["reason_automatic_alignment_failed"],
                "curator_note": entry["curator_note"],
                "alignment_quality_issues": entry["alignment_quality_issues"],
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
        "curated_override_chapter_count": len(curated_override_sections),
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
