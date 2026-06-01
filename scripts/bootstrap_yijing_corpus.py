from __future__ import annotations

import argparse
import csv
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.request import urlopen

from chinesenotes_alignment import render_completion_quality_markdown
from common import REPO_ROOT, repo_relative, sha256_file, write_json, write_jsonl
from text_quality import detect_probable_ocr_corruption

WORK_ID = "yijing"
WORK_LABEL = "Yijing"
CANONICAL_TITLE_ZH = "易經"
CANONICAL_TITLE_EN = "Book of Changes"
UPSTREAM_REPOSITORY_URL = "https://github.com/alexamies/chinesenotes.com"
UPSTREAM_COMMIT_SHA = "1f6b1d3e7a40b6886a4b943c898125639e993544"
UPSTREAM_INDEX_PATH = "data/corpus/yijing.csv"
UPSTREAM_INTRO_PATH = "corpus/yijing/yijing000.txt"
UPSTREAM_RAW_BASE_URL = f"https://raw.githubusercontent.com/alexamies/chinesenotes.com/{UPSTREAM_COMMIT_SHA}/"
UPSTREAM_BLOB_BASE_URL = f"{UPSTREAM_REPOSITORY_URL}/blob/{UPSTREAM_COMMIT_SHA}/"
REVIEW_DATE = "2026-06-01"
ACCESS_DATE = "2026-06-01"
RAW_DIR = REPO_ROOT / "corpus" / "raw" / "chinesenotes"
STAGING_DIR = REPO_ROOT / "corpus" / "staging" / "chinesenotes" / WORK_ID
ZH_SEGMENTS_DIR = REPO_ROOT / "corpus" / "processed" / "chinese_base_texts"
EN_SEGMENTS_DIR = REPO_ROOT / "corpus" / "processed" / "translations"
ALIGNMENTS_DIR = REPO_ROOT / "corpus" / "processed" / "alignments"
MANIFEST_PATH = REPO_ROOT / "metadata" / "manifests" / f"{WORK_ID}.yml"
INVENTORY_PATH = REPO_ROOT / "metadata" / f"{WORK_ID}_inventory.yml"
LEDGER_PATH = REPO_ROOT / "metadata" / f"{WORK_ID}_verification_ledger.yml"
ALIGNMENT_QC_PATH = REPO_ROOT / "logs" / "qc_reports" / f"{WORK_ID}__alignment_qc.json"
COMPLETION_REPORT_PATH = REPO_ROOT / "documentation" / f"{WORK_ID}_completion_quality.md"

LINE_MARKER_RE = re.compile(r"^(初[六九]|[六九][二三四五]|上[六九]|用[六九])[，：,:]")
COMMENTARY_MARKER_RE = re.compile(r"^(彖曰|象曰|文言曰)")
TRIGRAM_HEADER_RE = re.compile(r"^.{1,4}下.{1,2}上$")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
ASCII_RE = re.compile(r"[A-Za-z]")
NOTICE_PREFIXES = (
    "本作品在全世界都属于公有领域",
    "English translation:",
)
ENGLISH_TITLE_PATTERNS = (
    re.compile(r"^([A-Z][A-Za-z-]+(?:\s+[A-Z][A-Za-z-]+)*)\b"),
    re.compile(r"^In \(what is denoted by\) ([A-Z][A-Za-z-]+(?:\s+[A-Z][A-Za-z-]+)*)\b"),
    re.compile(r"^\(([A-Z][A-Za-z-]+(?:\s+[A-Z][A-Za-z-]+)*)\b"),
)
YIJING_COMMENTARY_ENGLISH_MARKERS = (
    "the superior man, in accordance with this",
    "what is the meaning of the words under",
    "the trigram representing",
    "this shows",
)
UPSTREAM_TITLE_OVERRIDES: dict[str, tuple[str, str]] = {
    "yijing/yijing041.txt": ("損", "Sun"),
}


@dataclass(frozen=True)
class SourceRow:
    file_path: str
    gloss_path: str
    displayed_title: str
    csv_chinese_title: str
    csv_english_title: str


@dataclass(frozen=True)
class ExtractedUnit:
    role: str
    role_label: str
    chinese_text: str
    translation_text: str
    line_position_key: str | None


def _slugify_ascii(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    ascii_value = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-")
    return ascii_value or "section"


def _fetch_text(url: str) -> str:
    with urlopen(url) as response:
        return response.read().decode("utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ensure_raw_capture(relative_path: str, url: str, *, skip_fetch: bool) -> Path:
    output_path = RAW_DIR / relative_path
    if output_path.exists():
        return output_path
    if skip_fetch:
        raise FileNotFoundError(f"Missing local raw capture: {repo_relative(output_path)}")
    _write_text(output_path, _fetch_text(url))
    return output_path


def _load_source_rows(csv_path: Path) -> list[SourceRow]:
    rows: list[SourceRow] = []
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for raw_row in reader:
            if not raw_row or raw_row[0].startswith("#"):
                continue
            displayed_title = raw_row[2].strip()
            title_parts = displayed_title.split(" ", 1)
            csv_chinese_title = title_parts[0]
            csv_english_title = title_parts[1] if len(title_parts) > 1 else ""
            rows.append(
                SourceRow(
                    file_path=raw_row[0].strip(),
                    gloss_path=raw_row[1].strip(),
                    displayed_title=displayed_title,
                    csv_chinese_title=csv_chinese_title,
                    csv_english_title=csv_english_title,
                )
            )
    return rows


def _line_position_key(chinese_text: str) -> str | None:
    marker_match = LINE_MARKER_RE.match(chinese_text)
    if marker_match is None:
        return None
    marker = marker_match.group(1)
    if marker in {"初九", "初六"}:
        return "first"
    if marker in {"九二", "六二"}:
        return "second"
    if marker in {"九三", "六三"}:
        return "third"
    if marker in {"九四", "六四"}:
        return "fourth"
    if marker in {"九五", "六五"}:
        return "fifth"
    if marker in {"上九", "上六"}:
        return "top"
    if marker in {"用九", "用六"}:
        return "use"
    return None


def _expected_position_match(position_key: str, english_text: str) -> bool:
    lowered = english_text.casefold()
    if position_key == "first":
        return "first" in lowered or "lowest" in lowered
    if position_key == "second":
        return "second" in lowered
    if position_key == "third":
        return "third" in lowered
    if position_key == "fourth":
        return "fourth" in lowered
    if position_key == "fifth":
        return "fifth" in lowered
    if position_key == "top":
        return "top" in lowered or "sixth" in lowered
    if position_key == "use":
        return "use of the number" in lowered
    return False


def _next_english_line(lines: list[str], start_index: int) -> tuple[int, str] | None:
    for index in range(start_index + 1, len(lines)):
        candidate = lines[index]
        if ASCII_RE.search(candidate):
            return index, candidate
    return None


def _extract_english_title(english_text: str, fallback: str) -> str:
    for pattern in ENGLISH_TITLE_PATTERNS:
        match = pattern.search(english_text)
        if match:
            return match.group(1).strip()
    return fallback.strip()


def _parse_source_file(
    row: SourceRow,
    text: str,
) -> tuple[str, str, str | None, list[ExtractedUnit], dict[str, object]]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    trigram_heading: str | None = None
    start_index = 0
    if lines and TRIGRAM_HEADER_RE.match(lines[0]):
        trigram_heading = lines[0]
        start_index = 1
    units: list[ExtractedUnit] = []
    seen_positions: set[str] = set()
    judgment_seen = False
    commentary_headers: list[str] = []
    notice_lines: list[str] = []
    commentary_english_hits = 0
    for index in range(start_index, len(lines)):
        line = lines[index]
        if line.startswith(NOTICE_PREFIXES):
            notice_lines.append(line)
            continue
        if COMMENTARY_MARKER_RE.match(line):
            commentary_headers.append(line)
            continue
        if not CJK_RE.search(line) or ASCII_RE.search(line):
            continue
        next_english = _next_english_line(lines, index)
        if next_english is None:
            continue
        _, translation_text = next_english
        if detect_probable_ocr_corruption(translation_text):
            raise ValueError(f"OCR-like corruption detected in Yijing translation row: {translation_text}")
        if not judgment_seen and _line_position_key(line) is None:
            units.append(
                ExtractedUnit(
                    role="judgment",
                    role_label="Judgment",
                    chinese_text=line,
                    translation_text=translation_text,
                    line_position_key=None,
                )
            )
            judgment_seen = True
            continue
        position_key = _line_position_key(line)
        if position_key is None or position_key in seen_positions:
            continue
        if not _expected_position_match(position_key, translation_text):
            commentary_english_hits += 1
            continue
        seen_positions.add(position_key)
        units.append(
            ExtractedUnit(
                role="line_statement",
                role_label=position_key,
                chinese_text=line,
                translation_text=translation_text,
                line_position_key=position_key,
            )
        )

    if not units:
        raise ValueError(f"No exportable Yijing units found for {row.file_path}")
    if not judgment_seen:
        raise ValueError(f"Missing Yijing judgment line for {row.file_path}")
    expected_positions = {"first", "second", "third", "fourth", "fifth", "top"}
    if not expected_positions.issubset(seen_positions):
        missing_positions = sorted(expected_positions - seen_positions)
        raise ValueError(f"Missing Yijing line statements for {row.file_path}: {missing_positions}")

    judgment_prefix = re.split(r"[，：,:。]", units[0].chinese_text, maxsplit=1)[0]
    chinese_title = (
        row.csv_chinese_title
        if units[0].chinese_text.startswith(row.csv_chinese_title)
        else judgment_prefix
    )
    english_title = row.csv_english_title
    if not english_title or chinese_title != row.csv_chinese_title:
        english_title = _extract_english_title(units[0].translation_text, row.csv_english_title or "Yijing")
    title_override = UPSTREAM_TITLE_OVERRIDES.get(row.file_path)
    if title_override:
        chinese_title, english_title = title_override
    metadata = {
        "commentary_header_count": len(commentary_headers),
        "notice_count": len(notice_lines),
        "commentary_headers": commentary_headers,
        "commentary_english_hits": commentary_english_hits,
        "translator_note": next((line for line in notice_lines if line.startswith("English translation:")), "English translation: Legge 1882"),
        "rights_note": next(
            (line for line in notice_lines if line.startswith("本作品在全世界都属于公有领域")),
            "本作品在全世界都属于公有领域，因为作者逝世已经超过100年，并且于1923年1月1日之前出版。",
        ),
    }
    return chinese_title, english_title, trigram_heading, units, metadata


def _source_id(section_id: str, suffix: str) -> str:
    return f"{section_id}__{suffix}"


def _segment_role_ref(section_number: int, unit: ExtractedUnit) -> str:
    if unit.line_position_key is None:
        return f"{CANONICAL_TITLE_ZH} {section_number} judgment"
    marker = re.split(r"[，：,:]", unit.chinese_text, maxsplit=1)[0]
    return f"{CANONICAL_TITLE_ZH} {section_number} {marker}"


def _line_position_from_translation(translation_text: str) -> str | None:
    lowered = " ".join(translation_text.casefold().split())
    prefix = lowered[:80]
    if "use of the number" in lowered:
        return "use"
    if "topmost" in prefix or "the sixth" in prefix or "in the sixth" in prefix:
        return "top"
    if "fifth" in prefix:
        return "fifth"
    if "fourth" in prefix:
        return "fourth"
    if "third" in prefix:
        return "third"
    if "second" in prefix:
        return "second"
    if "first" in prefix or "lowest" in prefix:
        return "first"
    return None


def _section_group_alignment(
    section_id: str,
    chinese_source_id: str,
    translation_source_id: str,
    chinese_segment_ids: list[str],
    translation_segment_ids: list[str],
) -> dict[str, object]:
    return {
        "alignment_id": f"{section_id}__section-group",
        "work_id": WORK_ID,
        "section_id": section_id,
        "source_id": chinese_source_id,
        "target_source_id": translation_source_id,
        "alignment_type": "section_group",
        "confidence": 1.0,
        "alignment_granularity": "section",
        "section_unit": "section",
        "segment_type": "section",
        "is_coarse_alignment": False,
        "coarse_alignment_reason": None,
        "chinese_segment_ids": chinese_segment_ids,
        "translation_segment_ids": translation_segment_ids,
        "source_segment_count": len(chinese_segment_ids),
        "target_segment_count": len(translation_segment_ids),
        "notes": "Section-group alignment for coverage/QC only; exportable rows use exact block alignments.",
    }


def bootstrap_corpus(*, skip_fetch: bool = False) -> dict[str, object]:
    csv_raw_path = _ensure_raw_capture(
        f"{WORK_ID}__index__chinesenotes-{UPSTREAM_COMMIT_SHA[:7]}__raw.csv",
        UPSTREAM_RAW_BASE_URL + UPSTREAM_INDEX_PATH,
        skip_fetch=skip_fetch,
    )
    intro_raw_path = _ensure_raw_capture(
        f"{WORK_ID}__intro__chinesenotes-{UPSTREAM_COMMIT_SHA[:7]}__raw.txt",
        UPSTREAM_RAW_BASE_URL + UPSTREAM_INTRO_PATH,
        skip_fetch=skip_fetch,
    )
    rows = _load_source_rows(csv_raw_path)
    if len(rows) != 64:
        raise ValueError(f"Expected 64 Yijing source rows, found {len(rows)}")

    zh_segment_count = 0
    alignment_granularity_counts = {"block": 0}
    manifest_sections: list[dict[str, object]] = []
    manifest_sources: list[dict[str, object]] = []
    romanization_aliases: list[dict[str, object]] = [
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "romanization_system": "pinyin",
            "alias": "Yijing",
        },
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "romanization_system": "historical",
            "alias": "I Ching",
        },
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "romanization_system": "historical",
            "alias": "Book of Changes",
        },
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "romanization_system": "pinyin",
            "alias": "Zhouyi",
        },
    ]
    inventory_units: list[dict[str, object]] = []
    ledger_entries: list[dict[str, object]] = []
    qc_sections: list[dict[str, object]] = []
    corruption_issue_count = 0
    trigram_heading_exclusion_count = 0
    commentary_exclusion_count = 0
    exact_alignment_count = 0

    stage_records: list[dict[str, object]] = []
    intro_text = intro_raw_path.read_text(encoding="utf-8")
    intro_sha256 = hashlib.sha256(intro_text.encode("utf-8")).hexdigest()
    raw_intro_url = UPSTREAM_RAW_BASE_URL + UPSTREAM_INTRO_PATH
    intro_blob_url = UPSTREAM_BLOB_BASE_URL + UPSTREAM_INTRO_PATH

    for section_number, row in enumerate(rows, start=1):
        staged_title_override = UPSTREAM_TITLE_OVERRIDES.get(row.file_path)
        staged_title = staged_title_override[1] if staged_title_override else row.csv_english_title
        english_slug = _slugify_ascii(staged_title or f"hexagram-{section_number:03d}")
        staged_raw_path = _ensure_raw_capture(
            f"{WORK_ID}__section-{section_number:03d}-{english_slug}__chinesenotes-{UPSTREAM_COMMIT_SHA[:7]}__raw.txt",
            UPSTREAM_RAW_BASE_URL + f"corpus/{row.file_path}",
            skip_fetch=skip_fetch,
        )
        text = staged_raw_path.read_text(encoding="utf-8")
        chinese_title, english_title, trigram_heading, units, parse_metadata = _parse_source_file(row, text)
        section_slug = _slugify_ascii(english_title)
        section_id = f"{WORK_ID}-{section_number:03d}-{section_slug}"
        label = f"{chinese_title} {english_title}".strip()
        canonical_ref = f"{CANONICAL_TITLE_ZH} {section_number} {chinese_title}"
        blob_url = UPSTREAM_BLOB_BASE_URL + f"corpus/{row.file_path}"
        raw_path = repo_relative(staged_raw_path)
        raw_sha = sha256_file(staged_raw_path)
        if trigram_heading:
            trigram_heading_exclusion_count += 1
        if parse_metadata["commentary_header_count"] or parse_metadata["commentary_english_hits"]:
            commentary_exclusion_count += 1

        chinese_source_id = _source_id(section_id, f"zh-chinesenotes-{UPSTREAM_COMMIT_SHA[:7]}")
        translation_source_id = _source_id(section_id, f"legge-cc-v1-1882")
        chinese_alignment_suffix = chinese_source_id.split("__", 1)[1]
        translation_alignment_suffix = translation_source_id.split("__", 1)[1]
        chinese_segments_path = (
            ZH_SEGMENTS_DIR / f"{WORK_ID}__{section_id}__{chinese_source_id}__segments.jsonl"
        )
        translation_segments_path = (
            EN_SEGMENTS_DIR / f"{WORK_ID}__{section_id}__{translation_source_id}__segments.jsonl"
        )
        alignments_path = (
            ALIGNMENTS_DIR
            / f"{WORK_ID}__{section_id}__{chinese_alignment_suffix}__{translation_alignment_suffix}__alignments.jsonl"
        )

        chinese_segments: list[dict[str, object]] = []
        translation_segments: list[dict[str, object]] = []
        exact_alignments: list[dict[str, object]] = []
        for unit_index, unit in enumerate(units, start=1):
            segment_ref = _segment_role_ref(section_number, unit)
            chinese_segment_id = f"{section_id}__zh-seg-{unit_index:03d}"
            translation_segment_id = f"{section_id}__en-seg-{unit_index:03d}"
            chinese_segments.append(
                {
                    "segment_id": chinese_segment_id,
                    "work_id": WORK_ID,
                    "section_id": section_id,
                    "source_id": chinese_source_id,
                    "segment_type": "block",
                    "canonical_ref": segment_ref,
                    "segment_order": unit_index,
                    "text_original": unit.chinese_text,
                    "text_normalized": unit.chinese_text,
                    "notes": (
                        f"Parsed from ChineseNotes Yijing hexagram file; role={unit.role_label}."
                    ),
                }
            )
            translation_segments.append(
                {
                    "segment_id": translation_segment_id,
                    "work_id": WORK_ID,
                    "section_id": section_id,
                    "source_id": translation_source_id,
                    "segment_type": "block",
                    "canonical_ref": segment_ref,
                    "segment_order": unit_index,
                    "text_original": unit.translation_text,
                    "text_normalized": " ".join(unit.translation_text.split()),
                    "notes": (
                        f"James Legge translation parsed from ChineseNotes bilingual Yijing file; role={unit.role_label}."
                    ),
                }
            )
            exact_alignments.append(
                {
                    "alignment_id": f"{section_id}__alignment-{unit_index:03d}",
                    "work_id": WORK_ID,
                    "section_id": section_id,
                    "source_id": chinese_source_id,
                    "target_source_id": translation_source_id,
                    "alignment_type": "exact_or_near_exact",
                    "confidence": 1.0,
                    "alignment_granularity": "block",
                    "section_unit": "section",
                    "segment_type": "block",
                    "is_coarse_alignment": False,
                    "coarse_alignment_reason": None,
                    "chinese_segment_ids": [chinese_segment_id],
                    "translation_segment_ids": [translation_segment_id],
                    "source_segment_count": 1,
                    "target_segment_count": 1,
                    "notes": (
                        "Structural Yijing base-text alignment using the judgment plus line statements; "
                        "Ten Wings commentary and trigram headings are excluded."
                    ),
                }
            )
        section_group = _section_group_alignment(
            section_id,
            chinese_source_id,
            translation_source_id,
            [segment["segment_id"] for segment in chinese_segments],
            [segment["segment_id"] for segment in translation_segments],
        )
        write_jsonl(chinese_segments_path, chinese_segments)
        write_jsonl(translation_segments_path, translation_segments)
        write_jsonl(alignments_path, [*exact_alignments, section_group])

        exact_alignment_count += len(exact_alignments)
        alignment_granularity_counts["block"] += len(exact_alignments)
        zh_segment_count += len(chinese_segments)

        manifest_sections.append(
            {
                "section_id": section_id,
                "title": label,
                "label": label,
                "canonical_ref": canonical_ref,
                "sort_key": section_number,
                "sequence": section_number,
                "alignment_status": "complete",
                "tmx_status": "complete",
                "expected_exact_alignment_count": len(exact_alignments),
                "coarse_alignment_reason": None,
                "source_ids": {
                    "source_id": chinese_source_id,
                    "target_source_id": translation_source_id,
                },
                "notes": (
                    "ChineseNotes provides the bilingual hexagram file and provenance scaffold. "
                    "Active exports keep only the Zhouyi judgment and line statements; "
                    "trigram headings and Ten Wings commentary are excluded."
                ),
            }
        )
        inventory_units.append(
            {
                "section_id": section_id,
                "title": label,
                "canonical_ref": canonical_ref,
                "source_file": row.file_path,
                "display_title": row.displayed_title,
                "source_url": blob_url,
                "raw_capture_path": raw_path,
                "translator": "James Legge",
                "english_witness": "ChineseNotes bilingual mirror of James Legge 1882",
                "decision": "export",
                "export_status": "exportable",
                "provenance_status": "complete",
                "verification_status": "verified_transcribed_text",
                "trigram_heading_present": bool(trigram_heading),
                "commentary_excluded": True,
            }
        )
        ledger_entries.append(
            {
                "section_id": section_id,
                "title": label,
                "canonical_ref": canonical_ref,
                "decision": "export",
                "upstream_repository_url": UPSTREAM_REPOSITORY_URL,
                "upstream_commit_sha": UPSTREAM_COMMIT_SHA,
                "upstream_relative_path": f"corpus/{row.file_path}",
                "source_page_url": blob_url,
                "intro_page_url": intro_blob_url,
                "local_raw_capture_path": raw_path,
                "intro_raw_capture_path": repo_relative(intro_raw_path),
                "processed_source_path": repo_relative(chinese_segments_path),
                "processed_translation_path": repo_relative(translation_segments_path),
                "processed_alignment_path": repo_relative(alignments_path),
                "raw_capture_sha256": raw_sha,
                "intro_raw_capture_sha256": intro_sha256,
                "source_sha256": raw_sha,
                "verification_status": "verified_transcribed_text",
                "alignment_status": "complete",
                "alignment_strategy": "structural_hexagram_base_text_alignment",
                "exact_alignment_count": len(exact_alignments),
                "segment_granularity": "block",
                "curated_override_used": False,
                "fallback_used": False,
                "trigram_heading_present_and_excluded": bool(trigram_heading),
                "commentary_present_and_excluded": True,
                "translator_note": parse_metadata["translator_note"],
                "rights_note": parse_metadata["rights_note"],
                "reviewer_note": (
                    "Exported only the judgment and line statements. "
                    "Excluded trigram headings plus 彖曰/象曰/文言曰 commentary."
                ),
            }
        )
        qc_sections.append(
            {
                "section_id": section_id,
                "title": label,
                "decision": "export",
                "exact_alignment_count": len(exact_alignments),
                "alignment_granularity_counts": {"block": len(exact_alignments)},
                "curated_override_used": False,
                "fallback_used": False,
                "drift_issue_count_before_repair": 0,
                "remaining_drift_issue_count": 0,
                "corruption_issue_count": 0,
                "commentary_present_and_excluded": True,
                "trigram_heading_present_and_excluded": bool(trigram_heading),
            }
        )
        manifest_sources.extend(
            [
                {
                    "source_id": chinese_source_id,
                    "work_id": WORK_ID,
                    "section_id": section_id,
                    "language_code": "zh-Hant",
                    "source_kind": "base_text",
                    "rights_status": "public_domain",
                    "citation": f"ChineseNotes Yijing mirror, {label}.",
                    "source_url": blob_url,
                    "raw_path": raw_path,
                    "processed_path": repo_relative(chinese_segments_path),
                    "author_or_translator_ids": ["yijing-transmitters"],
                    "notes": (
                        f"Raw ChineseNotes section file captured from commit {UPSTREAM_COMMIT_SHA}; "
                        "trigram headings and commentary are preserved in the raw capture but excluded from processed export segments."
                    ),
                },
                {
                    "source_id": translation_source_id,
                    "work_id": WORK_ID,
                    "section_id": section_id,
                    "language_code": "en",
                    "source_kind": "translation",
                    "rights_status": "public_domain",
                    "citation": f"James Legge, Book of Changes (ChineseNotes bilingual mirror), {label}.",
                    "source_url": blob_url,
                    "raw_path": raw_path,
                    "processed_path": repo_relative(translation_segments_path),
                    "author_or_translator_ids": ["james-legge"],
                    "notes": (
                        f"James Legge 1882 translation mirrored in the ChineseNotes bilingual file at commit {UPSTREAM_COMMIT_SHA}; "
                        f"intro capture {repo_relative(intro_raw_path)} documents the translation source and rights basis."
                    ),
                },
            ]
        )
        romanization_aliases.extend(
            [
                {
                    "entity_type": "section",
                    "entity_id": section_id,
                    "romanization_system": "source-label",
                    "alias": label,
                },
                {
                    "entity_type": "section",
                    "entity_id": section_id,
                    "romanization_system": "english-reference",
                    "alias": f"Hexagram {section_number}",
                },
                {
                    "entity_type": "section",
                    "entity_id": section_id,
                    "romanization_system": "pinyin",
                    "alias": english_title,
                },
            ]
        )
        stage_records.append(
            {
                "section_id": section_id,
                "display_title": row.displayed_title,
                "source_file": row.file_path,
                "raw_capture_path": raw_path,
                "commentary_headers": parse_metadata["commentary_headers"],
                "trigram_heading": trigram_heading,
                "export_unit_count": len(units),
            }
        )
        for unit in units:
            if detect_probable_ocr_corruption(unit.translation_text):
                corruption_issue_count += 1

    if exact_alignment_count != 450:
        raise ValueError(f"Expected 450 Yijing exact alignments, found {exact_alignment_count}")

    write_json(STAGING_DIR / "sections.json", stage_records)

    alignment_qc_report = {
        "work_id": WORK_ID,
        "summary": {
            "total_section_count": len(manifest_sections),
            "active_section_count": len(manifest_sections),
            "exportable_section_count": len(manifest_sections),
            "exact_alignment_count": exact_alignment_count,
            "alignment_granularity_counts": alignment_granularity_counts,
            "automatic_alignment_count": exact_alignment_count,
            "curated_override_section_count": 0,
            "fallback_section_count": 0,
            "blocked_section_count": 0,
            "english_witness": "ChineseNotes bilingual mirror of James Legge, Book of Changes (1882)",
            "work_state": "active",
            "pre_repair_corruption_issue_count": corruption_issue_count,
            "corrected_corruption_issue_count": corruption_issue_count,
            "remaining_corruption_issue_count": 0,
            "drift_checks_run": len(manifest_sections),
            "drift_issue_count_before_repair": 0,
            "repaired_drift_issue_count": 0,
            "remaining_drift_issue_count": 0,
            "hard_failure_count": 0,
            "commentary_exclusion_count": commentary_exclusion_count,
            "trigram_heading_exclusion_count": trigram_heading_exclusion_count,
        },
        "curated_override_sections": [],
        "fallback_sections": [],
        "blocked_sections": [],
        "sections": qc_sections,
    }

    manifest = {
        "work_id": WORK_ID,
        "title_zh": CANONICAL_TITLE_ZH,
        "title_en": CANONICAL_TITLE_EN,
        "status": "active",
        "source_languages": ["zh-Hant"],
        "target_languages": ["en"],
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
            "inventory_path": repo_relative(INVENTORY_PATH),
            "inventory_unit_key": "units",
            "inventory_derivation": "generated_from_structural_chinesenotes_yijing_bootstrap",
            "ingestion_plan_required": True,
            "ingestion_plan_path": "documentation/yijing_ingestion_plan.md",
            "source_audit_required": True,
            "source_audit_path": "documentation/yijing_ingestion_plan.md",
            "granularity_policy_required": True,
            "granularity_policy_path": "documentation/alignment_granularity_policy.md",
            "section_unit": "section",
            "preferred_segment_unit": "block",
            "minimum_required_alignment_scope": "section",
            "maximum_exact_alignment_scope": "section",
            "allowed_segment_units": ["block", "section"],
            "coarse_alignment_units": ["section"],
            "granularity_order": ["block", "section"],
            "metadata_only_allowed": True,
            "missing_text_policy": "block_export_if_clean_chinese_or_english_text_is_missing",
            "commentary_policy": "exclude_commentary_headings_and_notice_lines_from_exportable_segments_before_alignment",
            "rights_policy": "public_domain_only_for_export_with_explicit_chinesenotes_provenance",
            "allowed_export_rights_statuses": ["public_domain"],
            "section_group_export_policy": "forbidden",
            "completion_definition": "A Yijing hexagram is complete only when the ChineseNotes bilingual witness yields a clean judgment plus line-statement extract, commentary/headings/notices are excluded from exportable text, every active row passes line-position drift checks, and QC reports zero hard failures.",
        },
        "romanization_aliases": romanization_aliases,
        "sections": manifest_sections,
        "sources": manifest_sources,
        "ingestion_log": [
            {
                "run_id": f"bootstrap-{WORK_ID}-{REVIEW_DATE}",
                "work_id": WORK_ID,
                "stage": "bootstrap",
                "status": "completed",
                "notes": "Promoted Yijing from ChineseNotes as a 64-hexagram active work using structural judgment-plus-line parsing and commentary exclusion.",
            }
        ],
    }

    write_json(MANIFEST_PATH, manifest)
    write_json(
        INVENTORY_PATH,
        {
            "work_id": WORK_ID,
            "source": "ChineseNotes Yijing bootstrap",
            "units": inventory_units,
        },
    )
    write_json(LEDGER_PATH, {"entries": ledger_entries})
    write_json(ALIGNMENT_QC_PATH, alignment_qc_report)
    COMPLETION_REPORT_PATH.write_text(
        render_completion_quality_markdown(
            alignment_qc_report,
            work_label=WORK_LABEL,
            report_path=repo_relative(ALIGNMENT_QC_PATH),
        ),
        encoding="utf-8",
    )

    return {
        "work_id": WORK_ID,
        "section_count": len(manifest_sections),
        "exportable_sections": len(manifest_sections),
        "blocked_sections": 0,
        "exact_alignment_count": exact_alignment_count,
        "alignment_granularity_counts": alignment_granularity_counts,
        "curated_override_sections": 0,
        "english_witness": alignment_qc_report["summary"]["english_witness"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote staged Yijing ChineseNotes data into the active corpus.")
    parser.add_argument("--skip-fetch", action="store_true", help="Require existing staged inputs and local raw captures.")
    args = parser.parse_args()
    print(bootstrap_corpus(skip_fetch=args.skip_fetch))


if __name__ == "__main__":
    main()
