from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from common import QC_REPORTS_DIR, REPO_ROOT, load_json_compatible_yaml, utc_now_iso, write_json, write_jsonl
from inventory_chinesenotes import (
    PUBLIC_DOMAIN_RE,
    REPOSITORY_LEVEL_LICENSE,
    TRANSLATOR_ATTRIBUTION_RE,
    UPSTREAM_REPOSITORY_URL,
    _git_value,
    _read_tabular_file,
    load_collections_index,
)

DEFAULT_MAPPING_PATH = REPO_ROOT / "metadata" / "chinesenotes_work_mapping.yml"
DEFAULT_STAGING_ROOT = REPO_ROOT / "corpus" / "staging" / "chinesenotes"
DEFAULT_REPORT_ROOT = QC_REPORTS_DIR
HTML_TAG_RE = re.compile(r"<[^>]+>")
CHAPTER_HEADING_RE = re.compile(r"^([一二三四五六七八九十百]+)章$")
ASCII_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'’-]{1,}\b")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
ASCII_LETTER_RE = re.compile(r"[A-Za-z]")
SOURCE_HEADER_RE = re.compile(r"(《道德經》[上下]篇|張氏原本|王弼注)")
APPENDIX_START_RE = re.compile(r"^(跋(?:\[\d+\])?|晁說之跋|熊克跋|經典釋文|老子道經音義|老子德經音義|注釋)")

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
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _strip_html(text: str) -> str:
    return html.unescape(HTML_TAG_RE.sub("", text)).strip()


def _contains_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text))


def _contains_english(text: str) -> bool:
    return len(ASCII_WORD_RE.findall(text)) >= 2


def _contains_ascii_letter(text: str) -> bool:
    return bool(ASCII_LETTER_RE.search(text))


def _extract_notice_lines(text: str, pattern: re.Pattern[str]) -> list[str]:
    notes: list[str] = []
    for raw_line in text.splitlines():
        line = _strip_html(raw_line)
        if line and pattern.search(line):
            notes.append(line)
    return sorted(dict.fromkeys(notes))


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


def _load_mapping_entry(mapping_path: Path, work_id: str) -> dict[str, Any]:
    mapping = load_json_compatible_yaml(mapping_path)
    for work in mapping["works"]:
        if work["chintransmem_work_id"] == work_id:
            return work
    raise KeyError(f"Unknown ChineseNotes mapping work_id: {work_id}")


def _resolve_paths(mapping_entry: dict[str, Any]) -> tuple[str, str]:
    csv_path = next((path for path in mapping_entry["chinesenotes_paths"] if path.startswith("data/corpus/")), None)
    corpus_path = next((path for path in mapping_entry["chinesenotes_paths"] if path.startswith("corpus/")), None)
    if csv_path is None or corpus_path is None:
        raise ValueError("ChineseNotes mapping entry must include both data/corpus and corpus paths.")
    return csv_path, corpus_path


def _source_rows(source_root: Path, csv_relative_path: str) -> list[dict[str, Any]]:
    _, rows = _read_tabular_file(source_root / csv_relative_path)
    records: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        padded = row + [None] * (3 - len(row))
        records.append(
            {
                "row_index": index,
                "source_relative_path": padded[0],
                "html_relative_path": padded[1],
                "displayed_title": padded[2],
            }
        )
    return records


def _split_chapter_sections(text: str) -> list[tuple[str, str]]:
    parts = re.split(r"(?m)^([一二三四五六七八九十百]+章)$", text)
    sections: list[tuple[str, str]] = []
    for index in range(1, len(parts), 2):
        sections.append((parts[index].strip(), parts[index + 1]))
    return sections


def _classify_line(line: str) -> str:
    if not line:
        return "blank"
    if PUBLIC_DOMAIN_RE.search(line):
        return "rights_notice"
    if TRANSLATOR_ATTRIBUTION_RE.search(line):
        return "translator_notice"
    if line.startswith("〈") or line.endswith("〉"):
        return "commentary"
    if line.startswith("(") and line.endswith(")") and _contains_ascii_letter(line):
        return "english_heading"
    has_cjk = _contains_cjk(line)
    has_english = _contains_english(line)
    if has_cjk and not has_english:
        return "chinese"
    if has_english and not has_cjk:
        return "english"
    if has_cjk and has_english:
        return "mixed"
    return "other"


def _normalize_block_text(lines: list[str], *, language: str) -> list[str]:
    normalized: list[str] = []
    for line in lines:
        cleaned = re.sub(r"\s+", " ", line).strip()
        if not cleaned:
            continue
        if language == "zh":
            cleaned = cleaned.replace(" ", "")
        normalized.append(cleaned)
    return normalized


def _parse_section_body(
    *,
    work_id: str,
    section_number: int,
    heading: str,
    body: str,
    inherited_translator_notes: list[str],
    inherited_rights_notes: list[str],
    source_record: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    chinese_lines: list[str] = []
    english_lines: list[str] = []
    english_headings: list[str] = []
    uncategorized_lines: list[str] = []
    commentary_present = False
    translator_notes = list(inherited_translator_notes)
    rights_notes = list(inherited_rights_notes)
    appendix_started = False

    for raw_line in body.splitlines():
        line = _strip_html(raw_line)
        if not line:
            continue
        if APPENDIX_START_RE.match(line):
            appendix_started = True
            continue
        if appendix_started:
            if PUBLIC_DOMAIN_RE.search(line):
                rights_notes.append(line)
            elif TRANSLATOR_ATTRIBUTION_RE.search(line):
                translator_notes.append(line)
            continue
        if SOURCE_HEADER_RE.search(line):
            continue
        kind = _classify_line(line)
        if kind == "commentary":
            commentary_present = True
            continue
        if kind == "rights_notice":
            rights_notes.append(line)
            continue
        if kind == "translator_notice":
            translator_notes.append(line)
            continue
        if kind == "english_heading":
            english_headings.append(line)
            continue
        if kind == "chinese":
            chinese_lines.append(line)
            continue
        if kind == "english":
            english_lines.append(line)
            continue
        uncategorized_lines.append(line)

    chinese_blocks = _normalize_block_text(chinese_lines, language="zh")
    english_blocks = _normalize_block_text(english_lines, language="en")
    translator_notes = sorted(dict.fromkeys(note for note in translator_notes if note))
    rights_notes = sorted(dict.fromkeys(note for note in rights_notes if note))

    if chinese_blocks and english_blocks and uncategorized_lines:
        status = "needs_boundary_review"
        blocking_reason = "uncategorized mixed-content lines remain after parsing"
    elif chinese_blocks and english_blocks and not translator_notes:
        status = "needs_rights_or_translator_review"
        blocking_reason = "translator attribution not detected"
    elif chinese_blocks and english_blocks and not rights_notes:
        status = "needs_rights_or_translator_review"
        blocking_reason = "public-domain or licence notice not detected"
    elif chinese_blocks and english_blocks:
        status = "exportable_candidate"
        blocking_reason = ""
    elif chinese_blocks:
        status = "chinese_only"
        blocking_reason = "Chinese text detected without English text"
    elif english_blocks:
        status = "english_only"
        blocking_reason = "English text detected without Chinese text"
    else:
        status = "parse_failed"
        blocking_reason = "No Chinese or English blocks detected after parsing"

    section_id = f"{work_id}-chapter-{section_number:03d}"
    chinese_block_records = [
        {
            "section_id": section_id,
            "block_id": f"{section_id}__zh-{index:03d}",
            "block_index": index,
            "text_original": text,
        }
        for index, text in enumerate(chinese_blocks, start=1)
    ]
    english_block_records = [
        {
            "section_id": section_id,
            "block_id": f"{section_id}__en-{index:03d}",
            "block_index": index,
            "text_original": text,
        }
        for index, text in enumerate(english_blocks, start=1)
    ]
    alignment_records = []
    if status == "exportable_candidate":
        alignment_records.append(
            {
                "section_id": section_id,
                "alignment_id": f"{section_id}__candidate-alignment-001",
                "alignment_scope": "chapter",
                "source_block_ids": [block["block_id"] for block in chinese_block_records],
                "target_block_ids": [block["block_id"] for block in english_block_records],
                "confidence": "safe_chapter_level_candidate",
                "note": "Whole-chapter candidate alignment generated from a clean bilingual parse.",
            }
        )

    section_record = {
        "section_id": section_id,
        "section_label": heading,
        "section_number": section_number,
        "source_row_index": source_record["row_index"],
        "source_relative_path": source_record["source_relative_path"],
        "displayed_title": source_record["displayed_title"],
        "status": status,
        "chinese_block_count": len(chinese_block_records),
        "english_block_count": len(english_block_records),
        "chinese_detected": bool(chinese_block_records),
        "english_detected": bool(english_block_records),
        "translator_attribution_detected": bool(translator_notes),
        "rights_or_public_domain_notice_detected": bool(rights_notes),
        "commentary_present": commentary_present,
        "english_headings": english_headings,
        "uncategorized_lines": uncategorized_lines,
        "needs_manual_boundary_review": status == "needs_boundary_review",
        "looks_immediately_exportable": status == "exportable_candidate",
        "blocking_reason": blocking_reason,
        "source_metadata": {
            "upstream_repository": UPSTREAM_REPOSITORY_URL,
            "upstream_relative_path": source_record["source_relative_path"],
            "local_checkout_root": source_record["local_checkout_root"],
            "local_raw_capture_path": source_record["local_raw_capture_path"],
            "source_sha256": source_record.get("sha256"),
            "upstream_commit_sha": source_record["upstream_commit_sha"],
            "license_basis": REPOSITORY_LEVEL_LICENSE,
            "translator_notes": translator_notes,
            "rights_notes": rights_notes,
            "title": source_record["displayed_title"],
        },
    }
    return section_record, chinese_block_records, english_block_records, alignment_records


def _synthetic_missing_section(work_id: str, source_record: dict[str, Any]) -> dict[str, Any]:
    return {
        "section_id": f"{work_id}-source-row-{source_record['row_index']:03d}",
        "section_label": source_record["displayed_title"] or source_record["source_relative_path"],
        "section_number": source_record["row_index"],
        "source_row_index": source_record["row_index"],
        "source_relative_path": source_record["source_relative_path"],
        "displayed_title": source_record["displayed_title"],
        "status": "missing_source_file",
        "chinese_block_count": 0,
        "english_block_count": 0,
        "chinese_detected": False,
        "english_detected": False,
        "translator_attribution_detected": False,
        "rights_or_public_domain_notice_detected": False,
        "commentary_present": False,
        "english_headings": [],
        "uncategorized_lines": [],
        "needs_manual_boundary_review": False,
        "looks_immediately_exportable": False,
        "blocking_reason": "Source file listed in ChineseNotes metadata was not found locally",
        "source_metadata": {
            "upstream_repository": UPSTREAM_REPOSITORY_URL,
            "upstream_relative_path": source_record["source_relative_path"],
            "local_checkout_root": source_record["local_checkout_root"],
            "local_raw_capture_path": source_record["local_raw_capture_path"],
            "source_sha256": source_record.get("sha256"),
            "upstream_commit_sha": source_record["upstream_commit_sha"],
            "license_basis": REPOSITORY_LEVEL_LICENSE,
            "translator_notes": [],
            "rights_notes": [],
            "title": source_record["displayed_title"],
        },
    }


def stage_chinesenotes_work(
    *,
    source_root: Path,
    work_id: str,
    mode: str,
    mapping_path: Path = DEFAULT_MAPPING_PATH,
    output_root: Path = DEFAULT_STAGING_ROOT,
    report_root: Path = DEFAULT_REPORT_ROOT,
) -> dict[str, Any]:
    if mode != "staging":
        raise ValueError("Only staging mode is currently supported.")

    mapping_entry = _load_mapping_entry(mapping_path, work_id)
    csv_relative_path, _ = _resolve_paths(mapping_entry)
    collection_index = load_collections_index(source_root)
    collection_meta = collection_index.get(Path(csv_relative_path).name, {})
    source_rows = _source_rows(source_root, csv_relative_path)
    work_output_root = output_root / work_id
    source_records: list[dict[str, Any]] = []
    section_records: list[dict[str, Any]] = []
    chinese_blocks: list[dict[str, Any]] = []
    english_blocks: list[dict[str, Any]] = []
    alignment_records: list[dict[str, Any]] = []

    intro_relative_path = collection_meta.get("introduction_file")
    intro_text = ""
    if intro_relative_path:
        intro_path = source_root / "corpus" / intro_relative_path
        if intro_path.exists():
            intro_text = intro_path.read_text(encoding="utf-8")
    inherited_translator_notes = _extract_notice_lines(intro_text, TRANSLATOR_ATTRIBUTION_RE)
    inherited_rights_notes = _extract_notice_lines(intro_text, PUBLIC_DOMAIN_RE)
    upstream_commit_sha = _git_value(source_root, ["rev-parse", "HEAD"])

    source_files_found = 0
    source_files_parsed_successfully = 0
    source_files_missing = 0

    for row in source_rows:
        source_relative_path = row["source_relative_path"]
        if not source_relative_path:
            continue
        source_path = source_root / "corpus" / source_relative_path
        source_record = {
            **row,
            "local_checkout_root": str(source_root),
            "local_raw_capture_path": str(Path("corpus") / source_relative_path),
            "upstream_commit_sha": upstream_commit_sha,
            "found": source_path.exists(),
        }
        source_records.append(source_record)
        if not source_path.exists():
            source_files_missing += 1
            section_records.append(_synthetic_missing_section(work_id, source_record))
            continue

        source_files_found += 1
        source_text = source_path.read_text(encoding="utf-8")
        source_record["sha256"] = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        translator_notes = sorted(
            dict.fromkeys(
                inherited_translator_notes + _extract_notice_lines(source_text, TRANSLATOR_ATTRIBUTION_RE)
            )
        )
        rights_notes = sorted(dict.fromkeys(inherited_rights_notes + _extract_notice_lines(source_text, PUBLIC_DOMAIN_RE)))
        section_pairs = _split_chapter_sections(source_text)
        if not section_pairs:
            source_files_parsed_successfully += 0
            section_records.append(
                {
                    **_synthetic_missing_section(work_id, source_record),
                    "status": "parse_failed",
                    "blocking_reason": "No chapter-like section boundaries detected in source file",
                }
            )
            continue

        source_files_parsed_successfully += 1
        for heading, section_body in section_pairs:
            match = CHAPTER_HEADING_RE.match(heading)
            if match is None:
                continue
            section_number = _chinese_numeral_to_int(match.group(1))
            section_record, zh_blocks, en_blocks, section_alignments = _parse_section_body(
                work_id=work_id,
                section_number=section_number,
                heading=heading,
                body=section_body,
                inherited_translator_notes=translator_notes,
                inherited_rights_notes=rights_notes,
                source_record=source_record,
            )
            section_records.append(section_record)
            chinese_blocks.extend(zh_blocks)
            english_blocks.extend(en_blocks)
            alignment_records.extend(section_alignments)

    status_counts = Counter(section["status"] for section in section_records)
    blocked_sections = [
        {
            "section_id": section["section_id"],
            "status": section["status"],
            "blocking_reason": section["blocking_reason"],
        }
        for section in section_records
        if section["status"] != "exportable_candidate"
    ]
    report = {
        "work_id": work_id,
        "mode": mode,
        "generated_at": utc_now_iso(),
        "source_root": str(source_root),
        "upstream_repository": UPSTREAM_REPOSITORY_URL,
        "upstream_commit_sha": upstream_commit_sha,
        "mapping_path": _display_path(mapping_path),
        "metadata_csv_path": csv_relative_path,
        "intro_relative_path": intro_relative_path,
        "summary": {
            "total_metadata_rows": len(source_rows),
            "source_files_found": source_files_found,
            "source_files_missing": source_files_missing,
            "source_files_parsed_successfully": source_files_parsed_successfully,
            "sections_detected": len(section_records),
            "sections_with_chinese": sum(1 for section in section_records if section["chinese_detected"]),
            "sections_with_english": sum(1 for section in section_records if section["english_detected"]),
            "sections_with_both": sum(
                1 for section in section_records if section["chinese_detected"] and section["english_detected"]
            ),
            "sections_with_translator_attribution": sum(
                1 for section in section_records if section["translator_attribution_detected"]
            ),
            "sections_with_public_domain_or_other_notice": sum(
                1 for section in section_records if section["rights_or_public_domain_notice_detected"]
            ),
            "sections_parsed_into_clean_candidate_segments": sum(
                1 for section in section_records if section["status"] == "exportable_candidate"
            ),
            "sections_requiring_manual_boundary_review": sum(
                1 for section in section_records if section["status"] == "needs_boundary_review"
            ),
            "sections_that_could_become_tm_exports_now": sum(
                1 for section in section_records if section["looks_immediately_exportable"]
            ),
            "sections_blocked": len(blocked_sections),
            "candidate_alignment_count": len(alignment_records),
        },
        "status_counts": dict(status_counts),
        "blocked_sections": blocked_sections,
        "source_records": [
            {
                "row_index": record["row_index"],
                "source_relative_path": record["source_relative_path"],
                "displayed_title": record["displayed_title"],
                "found": record["found"],
                "local_checkout_root": record["local_checkout_root"],
                "local_raw_capture_path": record["local_raw_capture_path"],
            }
            for record in source_records
        ],
    }

    work_output_root.mkdir(parents=True, exist_ok=True)
    source_records_path = work_output_root / "source_pointers.jsonl"
    sections_path = work_output_root / "sections.jsonl"
    chinese_blocks_path = work_output_root / "chinese_blocks.jsonl"
    english_blocks_path = work_output_root / "english_blocks.jsonl"
    alignments_path = work_output_root / "alignments.jsonl"
    manifest_path = work_output_root / "staging_manifest.yml"
    staging_report_path = work_output_root / "staging_coverage_report.json"
    qc_report_path = report_root / f"chinesenotes__{work_id}__staging_report.json"

    write_jsonl(source_records_path, source_records)
    write_jsonl(sections_path, section_records)
    write_jsonl(chinese_blocks_path, chinese_blocks)
    write_jsonl(english_blocks_path, english_blocks)
    write_jsonl(alignments_path, alignment_records)
    write_json(staging_report_path, report)
    write_json(qc_report_path, report)
    write_json(
        manifest_path,
        {
            "work_id": work_id,
            "mode": mode,
            "generated_at": report["generated_at"],
            "upstream_repository": UPSTREAM_REPOSITORY_URL,
            "upstream_commit_sha": upstream_commit_sha,
            "source_root": str(source_root),
            "metadata_csv_path": csv_relative_path,
            "collection_title": collection_meta.get("title"),
            "staging_files": {
                "source_pointers": _display_path(source_records_path),
                "sections": _display_path(sections_path),
                "chinese_blocks": _display_path(chinese_blocks_path),
                "english_blocks": _display_path(english_blocks_path),
                "alignments": _display_path(alignments_path),
                "staging_report": _display_path(staging_report_path),
                "qc_report": _display_path(qc_report_path),
            },
            "summary": report["summary"],
        },
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Stage one ChineseNotes work into ChinTransMem staging outputs.")
    parser.add_argument("--source-root", required=True, help="Path to the local ChineseNotes checkout.")
    parser.add_argument("--work-id", required=True, help="ChinTransMem work ID to stage.")
    parser.add_argument("--mode", default="staging", choices=["staging"], help="Ingestion mode.")
    parser.add_argument("--mapping-path", default=str(DEFAULT_MAPPING_PATH), help="Work mapping file path.")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_STAGING_ROOT),
        help="Root directory for staged corpus outputs.",
    )
    parser.add_argument(
        "--report-root",
        default=str(DEFAULT_REPORT_ROOT),
        help="Directory for staging QC reports.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = stage_chinesenotes_work(
        source_root=Path(args.source_root),
        work_id=args.work_id,
        mode=args.mode,
        mapping_path=Path(args.mapping_path),
        output_root=Path(args.output_root),
        report_root=Path(args.report_root),
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
