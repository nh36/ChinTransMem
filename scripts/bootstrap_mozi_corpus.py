from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

from chinesenotes_alignment import (
    find_anchor_drift_issues,
    load_alignment_anchor_maps,
    load_alignment_overrides,
    refine_alignment,
    render_completion_quality_markdown,
    split_chinese_units,
)
from common import REPO_ROOT, load_json_compatible_yaml, repo_relative, section_export_paths, sha256_file, write_json, write_jsonl
from ingest_chinesenotes_work import (
    PUBLIC_DOMAIN_RE,
    TRANSLATOR_ATTRIBUTION_RE,
    _extract_notice_lines,
    _parse_section_body,
)
from mozi_ocr import detect_mozi_leakage_issues, detect_mozi_ocr_issues, looks_like_mozi_note_line, repair_mozi_ocr_text

UPSTREAM_COMMIT_SHA = "1f6b1d3e7a40b6886a4b943c898125639e993544"
UPSTREAM_BASE_URL = "https://raw.githubusercontent.com/craigbrelsford/ChineseNotes.com/{commit}/data/corpus/mozi.csv"
INTRO_URL = "https://raw.githubusercontent.com/craigbrelsford/ChineseNotes.com/{commit}/corpus/mozi/index.html"

INDEX_CAPTURE_PATH = REPO_ROOT / "corpus" / "raw" / "chinesenotes" / "mozi__index__chinesenotes-1f6b1d3__raw.csv"
INTRO_CAPTURE_PATH = REPO_ROOT / "corpus" / "raw" / "chinesenotes" / "mozi__intro__chinesenotes-1f6b1d3__raw.txt"
RAW_CAPTURE_DIR = REPO_ROOT / "corpus" / "raw" / "chinesenotes"
ARCHIVE_RAW_TEXT_PATH = REPO_ROOT / "corpus" / "raw" / "archiveorg" / "mozi__mei-1929__archiveorg-in-ernet-dli-2015-283868__raw.txt"
ARCHIVE_ITEM_URL = "https://archive.org/details/in.ernet.dli.2015.283868"
ARCHIVE_DOWNLOAD_URL = "https://archive.org/download/in.ernet.dli.2015.283868/2015.283868.The-Works_djvu.txt"

ZH_SEGMENTS_DIR = REPO_ROOT / "corpus" / "processed" / "chinese_base_texts"
EN_SEGMENTS_DIR = REPO_ROOT / "corpus" / "processed" / "translations"
ALIGNMENTS_DIR = REPO_ROOT / "corpus" / "processed" / "alignments"
STAGING_DIR = REPO_ROOT / "corpus" / "staging" / "chinesenotes" / "mozi"
METADATA_DIR = REPO_ROOT / "metadata"
LOGS_DIR = REPO_ROOT / "logs" / "qc_reports"
DOCS_DIR = REPO_ROOT / "documentation"
ALIGNMENT_ANCHORS_PATH = METADATA_DIR / "mozi_alignment_anchors.yml"
ALIGNMENT_OVERRIDES_PATH = METADATA_DIR / "mozi_alignment_overrides.yml"

WORK_ID = "mozi"
WORK_TITLE_ZH = "墨子"
WORK_TITLE_EN = "Mozi"
WORK_TITLE_VARIANTS = [
    "Mozi",
    "Motse",
    "Micius",
]
WORK_SOURCE_URL = "https://github.com/craigbrelsford/ChineseNotes.com/tree/{commit}/corpus/mozi"
SOURCE_WITNESS_SUFFIX = "chinesenotes-1f6b1d3"
TARGET_WITNESS_SUFFIX = "mei-archiveocr-v1-1929"
PROOF_OF_CONCEPT_RIGHTS_STATUS = "rights_review_required"
PROOF_OF_CONCEPT_RELEASE_STATUS = "not_cleared"
PROOF_OF_CONCEPT_USE_STATUS = "proof_of_concept"
BLOCKED_RIGHTS_STATUS = "unknown_rights_review_required"
RELEASE_READY_STATUS = "cleared"
ACCESS_DATE = "2026-06-01"

MEI_CHAPTER_START_PATTERNS: dict[int, str] = {
    1: r"BOOK\s+I\s+.*?CHAPTER\s+.*?BEMEKDIN\w+\s+THE\s+L\w+",
    2: r"CHAPTER\s+II\b",
    3: r"On\s+Dyeing",
    4: r"CHAPTER\s+IV\b",
    5: r"Seven\s+Causes\s+of\s+Anxiety",
    6: r"Indulgence\s+in\s+Excess",
    7: r"CHAPTER\s+VII\b",
    8: r"CHAPTER\s+VIII\b",
    9: r"CHAPTER\s+IX\b",
    10: r"CHAPTER\s+X['\s]",
    11: r"BOOK\s+III\s+CHAPTEE\s+XI",
    12: r"CHAPTER\s+XII\b",
    13: r"CHAPTER\s+XIII\b",
    14: r"CHAPTER\s+XIV\b",
    15: r"CHAPTER\s+XV\b",
    16: r"CHAPTER\s+XVI\b",
    17: r"CHAPTER\s+XVII\b",
    18: r"CHAPTER\s+XVIII\b",
    20: r"CHAPTER\s+XX\b",
    21: r"CHAPTER\s+XXI\b",
    25: r"CHAPTER\s+XXV\b",
    26: r"Will\s+of\s+Hea\w+\s*\(I\)",
    27: r"CHAPTER\s+XXVII\b",
    28: r"CHAPTER\s+XXVIII\b",
    31: r"CHAPTER\s+XXXI\b",
    32: r"CHAPTER\s+XXXII\b",
    35: r"CHAPTER\s+XXXV\b",
    36: r"CHAPTER\s+XXXVI\b",
    37: r"Anti\-Fatalism\s*\(III\)",
    39: r"ANTI\-CONFUCIA\w+\s*\(II\)",
    46: r"BOOK\s+XI\s+CHAPTEE\s+XLVI",
    47: r"BOOK\s+XII\s+CHAPTEE\s+XLVII",
    48: r"Kung\s+M\w+ng",
    49: r"Lu[’']s\s+Question",
    50: r"CHAPTER\s+L\b",
}
MEI_COVERED_CHAPTERS = sorted(MEI_CHAPTER_START_PATTERNS)
MEI_UNUSABLE_EXTRACT_CHAPTERS = {46, 47, 48, 49, 50}

HEADER_RE = re.compile(r"^(?:BOOK|CHAP\w*)\b", re.IGNORECASE)
PAGE_HEADER_RE = re.compile(r"^(?:TH[LEI]\s+WOE?R?KS?\s+(?:OF|OP)\s+MOTSE)\b", re.IGNORECASE)
FOOTNOTE_MARKER_RE = re.compile(r'^[\^®*»«°"\d]')
STRICT_ENGLISH_UNIT_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+")
ASCII_TOKEN_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
MEI_HEADER_RESIDUE_RE = re.compile(
    r"Motse,\s*the\s+Neglected\s+Rival\s+of\s+Confucius.*?THE\s+WORKS\s+OF\s+MOTS[EA!]?\s*",
    re.IGNORECASE,
)
MEI_FOOTNOTE_RESIDUE_RE = re.compile(
    r"thi\s+comparison\s+with\s+the\s+list\s+of\s+Chronological\s+Table\s+appended.*?strict\.\s*",
    re.IGNORECASE,
)
MEI_GLOSSARY_RESIDUE_RE = re.compile(r"Partiality\s+in\s+love,\s+wrong,\s*\d+.*$", re.IGNORECASE)


def _fetch_text(url: str) -> str:
    with urllib.request.urlopen(url) as response:
        return response.read().decode("utf-8")


def _ensure_text_capture(path: Path, url: str, *, skip_fetch: bool) -> None:
    if path.exists():
        return
    if skip_fetch:
        raise FileNotFoundError(f"Missing required raw capture: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_fetch_text(url), encoding="utf-8")


def _load_source_rows(index_capture_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with index_capture_path.open("r", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        row_index = 0
        for raw_row in reader:
            if not raw_row or raw_row[0].startswith("#"):
                continue
            row_index += 1
            row = raw_row + [""] * max(0, 3 - len(raw_row))
            rows.append(
                {
                    "row_index": row_index,
                    "source_relative_path": row[0].strip(),
                    "work_slug": row[1].strip(),
                    "displayed_title": row[2].strip(),
                }
            )
    return rows


def _parse_displayed_title(displayed_title: str) -> tuple[str, str]:
    chapter_match = re.match(r"^卷[^\s]+\s+(\S+)\s+Book\s+\d+\s+-\s+(.+)$", displayed_title)
    if chapter_match:
        return chapter_match.group(1).strip(), chapter_match.group(2).strip()
    if "(" in displayed_title and displayed_title.endswith(")"):
        chinese_title, _, english_title = displayed_title.partition("(")
        return chinese_title.strip(), english_title[:-1].strip()
    return displayed_title.strip(), displayed_title.strip()


def _slugify_ascii(text: str) -> str:
    lowered = text.lower()
    lowered = lowered.replace("&", " and ")
    lowered = re.sub(r"[^a-z0-9]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered)
    return lowered.strip("-") or "section"


def _section_id(section_number: int, english_title: str) -> str:
    return f"{WORK_ID}-{section_number:03d}-{_slugify_ascii(english_title)}"


def _canonical_chapter_number(source_relative_path: str) -> int:
    match = re.search(r"mozi(\d+)\.txt$", source_relative_path)
    if match is None:
        raise ValueError(f"Unable to parse canonical chapter number from {source_relative_path}")
    return int(match.group(1))


def _source_sha256(path: Path) -> str:
    return sha256_file(path)


def _source_blob_url(source_relative_path: str) -> str:
    return f"https://github.com/craigbrelsford/ChineseNotes.com/blob/{UPSTREAM_COMMIT_SHA}/{source_relative_path}"


def _looks_like_short_title(line: str) -> bool:
    words = ASCII_TOKEN_RE.findall(line)
    if not words or len(words) > 8:
        return False
    if re.search(r"[.!?;:]", line):
        return False
    return True


def _looks_like_running_header(line: str, english_title: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    words = ASCII_TOKEN_RE.findall(stripped)
    if not words or len(words) > 12:
        return False
    letters = [char for char in stripped if char.isalpha()]
    uppercase_ratio = (sum(1 for char in letters if char.isupper()) / len(letters)) if letters else 0.0
    normalized = re.sub(r"[^A-Za-z ]+", " ", stripped).casefold()
    normalized_title = re.sub(r"[^A-Za-z ]+", " ", english_title).casefold()
    if "mots" in normalized and uppercase_ratio >= 0.55:
        return True
    if normalized_title and normalized_title in normalized and uppercase_ratio >= 0.55:
        return True
    if uppercase_ratio >= 0.8 and len(words) <= 8:
        return True
    return False


def _strict_split_english_units(text: str) -> list[str]:
    parts = [part.strip(" ;") for part in STRICT_ENGLISH_UNIT_BOUNDARY_RE.split(text) if part.strip(" ;")]
    merged: list[str] = []
    for part in parts:
        if merged and part and part[0].islower():
            if part.startswith(("of ", "under ", "and ", "to ", "for ")) or len(ASCII_TOKEN_RE.findall(part)) <= 5:
                merged[-1] = f"{merged[-1]} {part}"
                continue
        merged.append(part)
    return merged


def _clean_mei_unit(text: str) -> str:
    cleaned = MEI_HEADER_RESIDUE_RE.sub("", text)
    cleaned = MEI_FOOTNOTE_RESIDUE_RE.sub("", cleaned)
    cleaned = MEI_GLOSSARY_RESIDUE_RE.sub("", cleaned)
    return cleaned.strip(" ;")


def _mozi_leakage_issue_entries(text: str) -> list[dict[str, str]]:
    issues = detect_mozi_leakage_issues(text)
    if issues:
        return issues
    normalized = " ".join(text.split())
    return [{"token": normalized[:120], "issue_type": "note_commentary_leakage"}]


def _mozi_leakage_repair_entry(
    *,
    section_id: str,
    raw_text: str,
    correction_type: str,
    source_path: str,
    confidence: float = 0.99,
) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "raw_token": " ".join(raw_text.split())[:200],
        "corrected_token": "",
        "correction_type": correction_type,
        "confidence": confidence,
        "mode": "automatic",
        "source_path": source_path,
    }


def _alignment_preview_rows(section_id: str, alignment: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, group in enumerate(alignment["groups"], start=1):
        chinese_text = "".join(
            str(alignment["source_units"][unit_index]["text"]).strip()
            for unit_index in group["source_unit_indices"]
        )
        translation_text = " ".join(
            str(alignment["target_units"][unit_index]["text"]).strip()
            for unit_index in group["target_unit_indices"]
        )
        rows.append(
            {
                "alignment_id": f"{section_id}__preview-alignment-{index:03d}",
                "section_id": section_id,
                "chinese_text": chinese_text,
                "translation_text": translation_text,
            }
        )
    return rows


def _existing_export_rows(section_id: str) -> list[dict[str, Any]]:
    export_path = REPO_ROOT / "corpus" / "exports" / "jsonl" / f"{WORK_ID}__{section_id}__aligned_passages.jsonl"
    if not export_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in export_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        rows.append(json.loads(stripped))
    return rows


def _extract_mei_chapter_offsets(raw_text: str) -> dict[int, tuple[int, int]]:
    offsets: dict[int, tuple[int, int]] = {}
    cursor = 10_000
    chapter_numbers = sorted(MEI_CHAPTER_START_PATTERNS)
    starts: dict[int, int] = {}
    for chapter_number in chapter_numbers:
        pattern = re.compile(MEI_CHAPTER_START_PATTERNS[chapter_number], re.IGNORECASE | re.DOTALL)
        match = pattern.search(raw_text, cursor)
        if match is None:
            continue
        start = match.start()
        starts[chapter_number] = start
        cursor = start + 1
    for index, chapter_number in enumerate(sorted(starts)):
        start = starts[chapter_number]
        if index + 1 < len(starts):
            next_start = starts[sorted(starts)[index + 1]]
        else:
            next_start = len(raw_text)
        offsets[chapter_number] = (start, next_start)
    return offsets


def _extract_mei_english_units(
    raw_text: str,
    chapter_offsets: tuple[int, int],
    *,
    section_id: str,
    english_title: str,
    source_path: str,
) -> tuple[
    list[str],
    list[dict[str, Any]],
    list[dict[str, str]],
    list[dict[str, str]],
    list[dict[str, Any]],
    list[dict[str, str]],
    list[dict[str, str]],
]:
    start, end = chapter_offsets
    chapter_text = raw_text[start:end].replace("\r", "")
    raw_lines: list[str] = []
    for raw_line in chapter_text.splitlines():
        stripped = raw_line.strip()
        if (
            not stripped
            or re.fullmatch(r"\d+", stripped)
            or HEADER_RE.match(stripped)
            or PAGE_HEADER_RE.match(stripped)
            or _looks_like_running_header(stripped, english_title)
        ):
            raw_lines.append("")
            continue
        raw_lines.append(stripped)

    kept_lines: list[str] = []
    skipping_note_block = False
    after_blank_line = False
    leakage_repair_entries: list[dict[str, Any]] = []
    pre_leakage_issues: list[dict[str, str]] = []
    for line in raw_lines:
        if skipping_note_block:
            if not line:
                after_blank_line = True
                continue
            if FOOTNOTE_MARKER_RE.match(line):
                pre_leakage_issues.extend(_mozi_leakage_issue_entries(line))
                leakage_repair_entries.append(
                    _mozi_leakage_repair_entry(
                        section_id=section_id,
                        raw_text=line,
                        correction_type="automatic_footnote_marker_removal",
                        source_path=source_path,
                    )
                )
                after_blank_line = False
                continue
            if after_blank_line and not looks_like_mozi_note_line(line):
                skipping_note_block = False
                after_blank_line = False
            else:
                pre_leakage_issues.extend(_mozi_leakage_issue_entries(line))
                leakage_repair_entries.append(
                    _mozi_leakage_repair_entry(
                        section_id=section_id,
                        raw_text=line,
                        correction_type="automatic_note_block_removal",
                        source_path=source_path,
                    )
                )
                continue
        if FOOTNOTE_MARKER_RE.match(line):
            pre_leakage_issues.extend(_mozi_leakage_issue_entries(line))
            leakage_repair_entries.append(
                _mozi_leakage_repair_entry(
                    section_id=section_id,
                    raw_text=line,
                    correction_type="automatic_footnote_marker_removal",
                    source_path=source_path,
                )
            )
            skipping_note_block = True
            after_blank_line = False
            continue
        if looks_like_mozi_note_line(line):
            pre_leakage_issues.extend(_mozi_leakage_issue_entries(line))
            leakage_repair_entries.append(
                _mozi_leakage_repair_entry(
                    section_id=section_id,
                    raw_text=line,
                    correction_type="automatic_note_line_removal",
                    source_path=source_path,
                )
            )
            continue
        if line:
            kept_lines.append(line)

    while kept_lines and _looks_like_short_title(kept_lines[0]):
        kept_lines.pop(0)

    merged_lines: list[str] = []
    for line in kept_lines:
        if merged_lines and merged_lines[-1].endswith("-"):
            merged_lines[-1] = f"{merged_lines[-1]}{line.lstrip()}"
            continue
        merged_lines.append(line)

    cleaned_text = re.sub(r"\s+", " ", " ".join(merged_lines))
    cleaned_text = MEI_HEADER_RESIDUE_RE.sub("", cleaned_text)
    cleaned_text = MEI_FOOTNOTE_RESIDUE_RE.sub("", cleaned_text)
    cleaned_text = MEI_GLOSSARY_RESIDUE_RE.sub("", cleaned_text)
    cleaned_text = cleaned_text.replace("^", "").replace("®", "").replace("*", "").strip()
    cleaned_text = re.sub(
        r"(?<![.!?])\s+(Now these (?:four|five|six) (?:kings|lords|princes)\b)",
        r". \1",
        cleaned_text,
    )
    units: list[str] = []
    repair_entries: list[dict[str, Any]] = []
    pre_repair_issues: list[dict[str, str]] = []
    remaining_issues: list[dict[str, str]] = []
    remaining_leakage_issues: list[dict[str, str]] = []
    for unit in _strict_split_english_units(cleaned_text):
        cleaned_unit = _clean_mei_unit(unit)
        cleaned_unit, unit_repairs, unit_pre_issues, unit_remaining_issues = repair_mozi_ocr_text(
            cleaned_unit,
            section_id=section_id,
            source_path=source_path,
        )
        repair_entries.extend(unit_repairs)
        pre_repair_issues.extend(unit_pre_issues)
        remaining_issues.extend(unit_remaining_issues)
        leakage_issues = detect_mozi_leakage_issues(cleaned_unit)
        if leakage_issues and looks_like_mozi_note_line(cleaned_unit):
            pre_leakage_issues.extend(leakage_issues)
            leakage_repair_entries.append(
                _mozi_leakage_repair_entry(
                    section_id=section_id,
                    raw_text=cleaned_unit,
                    correction_type="automatic_note_unit_removal",
                    source_path=source_path,
                )
            )
            continue
        remaining_leakage_issues.extend(leakage_issues)
        if len(ASCII_TOKEN_RE.findall(cleaned_unit)) >= 3:
            units.append(cleaned_unit)
    return (
        units,
        repair_entries,
        pre_repair_issues,
        remaining_issues,
        leakage_repair_entries,
        pre_leakage_issues,
        remaining_leakage_issues,
    )


def _apply_curated_mozi_unit_overrides(
    *,
    section_id: str,
    units: list[str],
    source_path: str,
) -> tuple[list[str], list[dict[str, Any]]]:
    if section_id != "mozi-003-that-which-is-affectable":
        return units, []

    corrected_units: list[str] = []
    repairs: list[dict[str, Any]] = []
    six_bad_princes_written = False
    for unit in units:
        normalized = " ".join(unit.split())
        replacement: str | None = None
        remove_unit = False
        if "of Hsia came under the influence of Kan Hsin" in normalized:
            replacement = (
                "Chieh of Hsia came under the influence of Kan Hsin and T’uei Yi; "
                "Chow of Yin, under that of the Duke of Gh'ungi and Lai; "
                "King Li, under that of Chhng Fu, Duke Li, and Yi Chung of the State of Jung; "
                "and King Yu, under that of Yi, Duke of Fu, and Ku, Duke of Ta’ai."
            )
        elif normalized.startswith("Lord Huan of Ch’i came under the influence"):
            replacement = (
                "Lord Huan of Ch’i came under the influence of Kuan Chung and Pao Shu; "
                "Lord Wen of Chin, under that of Uncle Fan and Kao Yen; "
                "Lord Chuang of Ch’u, under that of Sun Shu and the Minister of Shen; "
                "Ho Lu of Wu, under that of Wu Yuan and Wen Yi; "
                "and Kou Chien of Yueh, under that of Pan Li and Minister Chimg."
            )
        elif normalized.startswith("Fan Chi She came under the influence"):
            replacement = (
                "Fan Chi She came under the influence of Ch’ang Liu Shuo and Wang Sheng; "
                "Chung Hsing Yin, under that of Chi Ch’in and Kao Chiang; "
                "Pu Ch’a, under that of Wang Sun Lo and Minister P’i; "
                "Chih Po Yao, under that of Chih Kuo and Chang Wu; "
                "Shang of Chung Shan, under that of Wei Yi and Yen Ch'ang; "
                "and Lord K'ang of Sung, under that of T'ang Yang and Tien Pu Li."
            )
            six_bad_princes_written = True
        elif six_bad_princes_written and (
            normalized.startswith("under that of Wang")
            or normalized.startswith("Chih Kuo and Chang Wu")
        ):
            remove_unit = True
        elif "Tu Kan Mu was a pupil of Tse Hsia" in normalized or normalized.startswith("For full story see p."):
            remove_unit = True
        elif normalized.startswith("Examples of such are"):
            replacement = "Examples of such are Tuan Kan Mu, Ch’intse, and Fu Yueh."
        elif normalized.startswith("And, examples of such are Tse HsL"):
            replacement = "Examples of such are Tse Hsi, Yi Ya, and Shu Tiao."
        elif normalized.startswith("An Ode says:") and normalized.endswith(" Confucius"):
            replacement = normalized.rsplit(" Confucius", 1)[0]

        if remove_unit:
            repairs.append(
                {
                    "section_id": section_id,
                    "raw_token": normalized[:200],
                    "corrected_token": "",
                    "correction_type": "curated_section_unit_removal",
                    "confidence": 0.99,
                    "mode": "curated",
                    "source_path": source_path,
                }
            )
            continue
        if replacement and replacement != normalized:
            repairs.append(
                {
                    "section_id": section_id,
                    "raw_token": normalized[:200],
                    "corrected_token": replacement,
                    "correction_type": "curated_section_unit_override",
                    "confidence": 0.99,
                    "mode": "curated",
                    "source_path": source_path,
                }
            )
            corrected_units.append(replacement)
            continue
        corrected_units.append(unit)
    return corrected_units, repairs


def _sentence_segment_record(
    *,
    section_id: str,
    source_id: str,
    segment_index: int,
    sentence_text: str,
    language: str,
    section_number: int,
) -> dict[str, Any]:
    segment_id = f"{source_id}__seg-{segment_index:04d}"
    return {
        "segment_id": segment_id,
        "section_id": section_id,
        "source_id": source_id,
        "work_id": WORK_ID,
        "segment_type": "sentence",
        "segment_order": segment_index,
        "text_original": sentence_text,
        "text_normalized": sentence_text,
        "canonical_ref": f"{section_number}.{segment_index}",
        "notes": "",
    }


def _build_alignment_records(
    *,
    section_id: str,
    source_id: str,
    target_source_id: str,
    section_number: int,
    chinese_segments: list[dict[str, Any]],
    english_segments: list[dict[str, Any]],
    alignment: dict[str, Any],
    notes: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    source_segment_ids = [segment["segment_id"] for segment in chinese_segments]
    target_segment_ids = [segment["segment_id"] for segment in english_segments]
    alignment_granularity = alignment.get("alignment_granularity", "grouped")
    segment_granularity = alignment.get("segment_granularity", "sentence")
    groups = alignment.get("groups") or []
    for group_index, group in enumerate(groups, start=1):
        source_indexes = list(group["source_unit_indices"])
        target_indexes = list(group["target_unit_indices"])
        source_group_ids = [source_segment_ids[index] for index in source_indexes]
        target_group_ids = [target_segment_ids[index] for index in target_indexes]
        row_alignment_granularity = group.get("alignment_granularity", alignment_granularity)
        records.append(
            {
                "alignment_id": f"{section_id}__align-{group_index:04d}",
                "work_id": WORK_ID,
                "section_id": section_id,
                "source_id": source_id,
                "target_source_id": target_source_id,
                "chinese_segment_ids": source_group_ids,
                "translation_segment_ids": target_group_ids,
                "alignment_type": "exact_or_near_exact",
                "alignment_granularity": row_alignment_granularity,
                "section_unit": "chapter",
                "segment_type": segment_granularity,
                "source_segment_count": len(source_group_ids),
                "target_segment_count": len(target_group_ids),
                "confidence": 0.93 if row_alignment_granularity == "grouped" else 0.96,
                "notes": notes,
                "canonical_ref": f"{section_number}.{group_index}",
            }
        )
    records.append(
        {
            "alignment_id": f"{section_id}__group-0001",
            "work_id": WORK_ID,
            "section_id": section_id,
            "source_id": source_id,
            "target_source_id": target_source_id,
            "chinese_segment_ids": source_segment_ids,
            "translation_segment_ids": target_segment_ids,
            "alignment_type": "section_group",
            "alignment_granularity": alignment_granularity,
            "section_unit": "chapter",
            "segment_type": segment_granularity,
            "source_segment_count": len(source_segment_ids),
            "target_segment_count": len(target_segment_ids),
            "confidence": 0.87,
            "notes": f"Section-level summary over {len(groups)} monotonic sentence-group alignments.",
            "canonical_ref": f"{section_number}.group",
        }
    )
    return records


def _build_section_fallback_alignment(
    *,
    section_id: str,
    source_id: str,
    target_source_id: str,
    section_number: int,
    chinese_segments: list[dict[str, Any]],
    english_segments: list[dict[str, Any]],
    reason: str,
) -> list[dict[str, Any]]:
    source_segment_ids = [segment["segment_id"] for segment in chinese_segments]
    target_segment_ids = [segment["segment_id"] for segment in english_segments]
    return [
        {
            "alignment_id": f"{section_id}__align-0001",
            "work_id": WORK_ID,
            "section_id": section_id,
            "source_id": source_id,
            "target_source_id": target_source_id,
            "chinese_segment_ids": source_segment_ids,
            "translation_segment_ids": target_segment_ids,
            "alignment_type": "exact_or_near_exact",
            "alignment_granularity": "chapter",
            "section_unit": "chapter",
            "segment_type": "sentence",
            "source_segment_count": len(source_segment_ids),
            "target_segment_count": len(target_segment_ids),
            "confidence": 0.72,
            "notes": "Chapter-level fallback alignment retained for proof-of-concept export only.",
            "canonical_ref": f"{section_number}.1",
            "is_coarse_alignment": True,
            "coarse_alignment_reason": reason,
        },
        {
            "alignment_id": f"{section_id}__group-0001",
            "work_id": WORK_ID,
            "section_id": section_id,
            "source_id": source_id,
            "target_source_id": target_source_id,
            "chinese_segment_ids": source_segment_ids,
            "translation_segment_ids": target_segment_ids,
            "alignment_type": "section_group",
            "alignment_granularity": "chapter",
            "section_unit": "chapter",
            "segment_type": "sentence",
            "source_segment_count": len(source_segment_ids),
            "target_segment_count": len(target_segment_ids),
            "confidence": 0.72,
            "notes": f"Chapter-level fallback alignment retained because {reason}",
            "canonical_ref": f"{section_number}.group",
        },
    ]


def _remove_stale_blocked_section_artifacts(section_id: str) -> None:
    english_segments_path = EN_SEGMENTS_DIR / f"{WORK_ID}__{section_id}__{TARGET_WITNESS_SUFFIX}__segments.jsonl"
    alignments_path = ALIGNMENTS_DIR / (
        f"{WORK_ID}__{section_id}__{SOURCE_WITNESS_SUFFIX}__{TARGET_WITNESS_SUFFIX}__alignments.jsonl"
    )
    for path in [english_segments_path, alignments_path, *section_export_paths(section_id, WORK_ID).values()]:
        if path.exists():
            path.unlink()


def _metadata_only_reason(canonical_chapter_number: int) -> str:
    if canonical_chapter_number not in MEI_COVERED_CHAPTERS:
        return "No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged."
    if canonical_chapter_number in MEI_UNUSABLE_EXTRACT_CHAPTERS:
        return "The committed Mei 1929 OCR witness contains this chapter number, but the extracted English resolves to unrelated dialogue or glossary material instead of the matching Mozi chapter. Leave this chapter metadata-only until a clean attributable English witness is captured."
    return "The committed Mei 1929 OCR witness covers this chapter, but the chapter boundary or usable English text could not be parsed reliably enough for proof-of-concept export."


def _mapping_entry_template() -> dict[str, Any]:
    mapping = load_json_compatible_yaml(METADATA_DIR / "chinesenotes_work_mapping.yml")
    for entry in mapping.get("works", []):
        if entry.get("chintransmem_work_id") == WORK_ID:
            return entry
    return {"chintransmem_work_id": WORK_ID}


def bootstrap_corpus(*, skip_fetch: bool = False) -> dict[str, Any]:
    _ensure_text_capture(INDEX_CAPTURE_PATH, UPSTREAM_BASE_URL.format(commit=UPSTREAM_COMMIT_SHA), skip_fetch=skip_fetch)
    _ensure_text_capture(INTRO_CAPTURE_PATH, INTRO_URL.format(commit=UPSTREAM_COMMIT_SHA), skip_fetch=skip_fetch)
    _ensure_text_capture(ARCHIVE_RAW_TEXT_PATH, ARCHIVE_DOWNLOAD_URL, skip_fetch=skip_fetch)

    intro_text = INTRO_CAPTURE_PATH.read_text(encoding="utf-8")
    inherited_translator_notes = _extract_notice_lines(intro_text, TRANSLATOR_ATTRIBUTION_RE)
    inherited_rights_notes = _extract_notice_lines(intro_text, PUBLIC_DOMAIN_RE)
    source_rows = _load_source_rows(INDEX_CAPTURE_PATH)

    mei_raw_text = ARCHIVE_RAW_TEXT_PATH.read_text(encoding="utf-8", errors="replace")
    mei_offsets = _extract_mei_chapter_offsets(mei_raw_text)
    alignment_anchor_maps = load_alignment_anchor_maps(ALIGNMENT_ANCHORS_PATH)
    alignment_overrides = load_alignment_overrides(ALIGNMENT_OVERRIDES_PATH)

    manifest_sections: list[dict[str, Any]] = []
    manifest_sources: list[dict[str, Any]] = []
    romanization_aliases: list[dict[str, Any]] = [
        {"entity_type": "work", "entity_id": WORK_ID, "romanization_system": "pinyin", "alias": "Mozi"},
        {"entity_type": "work", "entity_id": WORK_ID, "romanization_system": "historical", "alias": "Mo Tzu"},
        {"entity_type": "work", "entity_id": WORK_ID, "romanization_system": "historical", "alias": "Motse"},
        {"entity_type": "work", "entity_id": WORK_ID, "romanization_system": "english-title", "alias": "Mozi"},
    ]
    inventory_units: list[dict[str, Any]] = []
    verification_ledger: list[dict[str, Any]] = []
    staged_chinese_units: list[dict[str, Any]] = []
    staged_english_units: list[dict[str, Any]] = []
    qc_sections: list[dict[str, Any]] = []
    blocked_sections: list[dict[str, Any]] = []
    fallback_sections: list[dict[str, Any]] = []
    source_url_entries = [WORK_SOURCE_URL.format(commit=UPSTREAM_COMMIT_SHA), ARCHIVE_ITEM_URL, ARCHIVE_DOWNLOAD_URL]
    ocr_repair_entries: list[dict[str, Any]] = []
    leakage_repair_entries: list[dict[str, Any]] = []
    ocr_remaining_issues: list[dict[str, Any]] = []
    leakage_remaining_issues: list[dict[str, Any]] = []
    final_ocr_remaining_issues: list[dict[str, Any]] = []
    final_leakage_remaining_issues: list[dict[str, Any]] = []

    alignment_granularity_counts: dict[str, int] = {}
    exact_alignment_count = 0
    fallback_section_count = 0
    active_section_count = 0
    pre_repair_corruption_issue_count = 0
    pre_repair_leakage_issue_count = 0
    automatic_correction_count = 0
    curated_correction_count = 0
    repaired_leakage_issue_count = 0
    drift_checks_run = 0
    drift_issue_count_before_repair = 0
    remaining_drift_issue_count = 0
    anchor_mapped_section_ids: list[str] = []
    curated_override_section_ids: list[str] = []
    preexisting_active_section_count = 0

    for row in source_rows:
        chinese_title, english_title = _parse_displayed_title(row["displayed_title"])
        section_id = _section_id(row["row_index"], english_title)
        existing_rows = _existing_export_rows(section_id)
        if not existing_rows:
            continue
        preexisting_active_section_count += 1
        pre_repair_leakage_issue_count += sum(
            len(detect_mozi_leakage_issues(str(existing_row.get("translation_text", "")))) for existing_row in existing_rows
        )

    archive_sha256 = _source_sha256(ARCHIVE_RAW_TEXT_PATH)

    for row in source_rows:
        section_number = row["row_index"]
        chinese_title, english_title = _parse_displayed_title(row["displayed_title"])
        section_id = _section_id(section_number, english_title)
        canonical_chapter_number = _canonical_chapter_number(row["source_relative_path"])
        source_url = _source_blob_url(row["source_relative_path"])
        romanization_aliases.append(
            {
                "entity_type": "section",
                "entity_id": section_id,
                "romanization_system": "source-label",
                "alias": row["displayed_title"],
            }
        )
        if english_title:
            romanization_aliases.append(
                {
                    "entity_type": "section",
                    "entity_id": section_id,
                    "romanization_system": "english-title",
                    "alias": english_title,
                }
            )
        raw_capture_path = RAW_CAPTURE_DIR / f"{WORK_ID}__{section_id}__{SOURCE_WITNESS_SUFFIX}__raw.txt"
        if not raw_capture_path.exists():
            if skip_fetch:
                raise FileNotFoundError(f"Missing expected raw capture: {raw_capture_path}")
            raw_capture_path.write_text(_fetch_text(source_url), encoding="utf-8")
        raw_body = raw_capture_path.read_text(encoding="utf-8")
        source_record = {
            "row_index": section_number,
            "source_relative_path": row["source_relative_path"],
            "displayed_title": row["displayed_title"],
            "local_checkout_root": str(REPO_ROOT),
            "local_raw_capture_path": str(raw_capture_path),
            "upstream_commit_sha": UPSTREAM_COMMIT_SHA,
            "sha256": _source_sha256(raw_capture_path),
        }
        _, chinese_blocks, _, _ = _parse_section_body(
            work_id=WORK_ID,
            section_number=section_number,
            heading=row["displayed_title"],
            body=raw_body,
            inherited_translator_notes=inherited_translator_notes,
            inherited_rights_notes=inherited_rights_notes,
            source_record=source_record,
            section_id=section_id,
            section_unit="chapter",
            merge_wrapped_lines=True,
        )
        chinese_units: list[str] = []
        for block in chinese_blocks:
            chinese_units.extend(split_chinese_units(block["text_original"]))
        chinese_units = [unit for unit in chinese_units if unit]
        if not chinese_units:
            raise ValueError(f"{section_id} produced no Chinese sentence units")

        source_id = f"{section_id}__{SOURCE_WITNESS_SUFFIX}"
        source_segments = [
            _sentence_segment_record(
                section_id=section_id,
                source_id=source_id,
                segment_index=index,
                sentence_text=sentence,
                language="zh",
                section_number=section_number,
            )
            for index, sentence in enumerate(chinese_units, start=1)
        ]
        source_segments_path = ZH_SEGMENTS_DIR / f"{WORK_ID}__{section_id}__{source_id}__segments.jsonl"
        write_jsonl(source_segments_path, source_segments)

        staged_chinese_units.extend(
            {
                "section_id": section_id,
                "canonical_chapter_number": canonical_chapter_number,
                "language": "zh",
                "unit_type": "sentence",
                "position": segment["segment_order"],
                "text_original": segment["text_original"],
            }
            for segment in source_segments
        )

        chinese_source_record = {
            "source_id": source_id,
            "work_id": WORK_ID,
            "section_id": section_id,
            "language_code": "zh",
            "source_kind": "digital_transcription",
            "author_or_translator_ids": [],
            "citation": f"ChineseNotes Mozi mirror, {chinese_title}.",
            "source_url": source_url,
            "raw_path": repo_relative(raw_capture_path),
            "processed_path": repo_relative(source_segments_path),
            "rights_status": "public_domain",
            "release_status": PROOF_OF_CONCEPT_RELEASE_STATUS,
            "rights_note": "Ancient Chinese source text is public domain, but this proof-of-concept export still depends on a later English witness that remains under rights review.",
            "notes": "ChineseNotes-derived Mozi base text used for proof-of-concept TM research. Release clearance is tracked at the combined work level and remains pending.",
        }
        manifest_sources.append(chinese_source_record)

        manifest_section: dict[str, Any] = {
            "section_id": section_id,
            "title": chinese_title,
            "label": f"{chinese_title} {english_title}",
            "canonical_ref": f"墨子 {canonical_chapter_number} {chinese_title}",
            "sort_key": section_number,
            "sequence": section_number,
            "canonical_chapter_number": canonical_chapter_number,
            "source_relative_path": row["source_relative_path"],
            "title_zh": chinese_title,
            "title_en": english_title,
            "status": "metadata_only",
            "corpus_use_status": "blocked",
            "export_status": "metadata_only",
            "release_status": PROOF_OF_CONCEPT_RELEASE_STATUS,
            "source_ids": {"source_id": source_id},
            "source_processed_path": repo_relative(source_segments_path),
            "translation_processed_path": None,
            "alignment_processed_path": None,
            "alignment_status": "blocked",
            "tmx_status": "blocked",
            "expected_exact_alignment_count": 0,
            "blockers": [],
            "notes": "",
        }
        inventory_unit: dict[str, Any] = {
            "section_id": section_id,
            "canonical_order": section_number,
            "canonical_chapter_number": canonical_chapter_number,
            "title_zh": chinese_title,
            "title_en": english_title,
            "source_relative_path": row["source_relative_path"],
            "zh_source_url": source_url,
            "english_source_url": None,
            "source_id": source_id,
            "target_source_id": None,
            "decision": "metadata_only",
            "coverage_status": "metadata_only_blocked",
            "export_status": "metadata_only",
            "corpus_use_status": "blocked",
            "release_status": PROOF_OF_CONCEPT_RELEASE_STATUS,
            "rights_status": BLOCKED_RIGHTS_STATUS,
            "english_witness_status": "missing",
            "verification_status": "blocked_missing_english_witness",
            "source_processed_path": repo_relative(source_segments_path),
            "translation_processed_path": None,
            "alignment_processed_path": None,
            "blocker_reason": _metadata_only_reason(canonical_chapter_number),
        }

        english_units = []
        if canonical_chapter_number in MEI_UNUSABLE_EXTRACT_CHAPTERS:
            english_units = []
        elif canonical_chapter_number in mei_offsets:
            (
                english_units,
                unit_repairs,
                unit_pre_issues,
                unit_remaining_issues,
                unit_leakage_repairs,
                _unit_pre_leakage_issues,
                unit_remaining_leakage_issues,
            ) = _extract_mei_english_units(
                mei_raw_text,
                mei_offsets[canonical_chapter_number],
                section_id=section_id,
                english_title=english_title,
                source_path=repo_relative(ARCHIVE_RAW_TEXT_PATH),
            )
            ocr_repair_entries.extend(unit_repairs)
            leakage_repair_entries.extend(unit_leakage_repairs)
            pre_repair_corruption_issue_count += len(unit_pre_issues)
            automatic_correction_count += sum(1 for entry in unit_repairs if entry["mode"] == "automatic")
            curated_correction_count += sum(1 for entry in unit_repairs if entry["mode"] == "curated")
            ocr_remaining_issues.extend(
                {
                    "section_id": section_id,
                    "token": issue["token"],
                    "issue_type": issue["issue_type"],
                    "source_path": repo_relative(ARCHIVE_RAW_TEXT_PATH),
                }
                for issue in unit_remaining_issues
            )
            leakage_remaining_issues.extend(
                {
                    "section_id": section_id,
                    "token": issue["token"],
                    "issue_type": issue["issue_type"],
                    "source_path": repo_relative(ARCHIVE_RAW_TEXT_PATH),
                }
                for issue in unit_remaining_leakage_issues
            )
            english_units, curated_unit_repairs = _apply_curated_mozi_unit_overrides(
                section_id=section_id,
                units=english_units,
                source_path=repo_relative(ARCHIVE_RAW_TEXT_PATH),
            )
            leakage_repair_entries.extend(curated_unit_repairs)

        if canonical_chapter_number in mei_offsets and english_units:
            target_source_id = f"{section_id}__{TARGET_WITNESS_SUFFIX}"
            english_segments = []
            for index, sentence in enumerate(english_units, start=1):
                repaired_sentence, sentence_repairs, sentence_pre_issues, sentence_remaining_issues = repair_mozi_ocr_text(
                    sentence,
                    section_id=section_id,
                    source_path=repo_relative(ARCHIVE_RAW_TEXT_PATH),
                )
                ocr_repair_entries.extend(sentence_repairs)
                pre_repair_corruption_issue_count += len(sentence_pre_issues)
                ocr_remaining_issues.extend(
                    {
                        "section_id": section_id,
                        "token": issue["token"],
                        "issue_type": issue["issue_type"],
                        "source_path": repo_relative(ARCHIVE_RAW_TEXT_PATH),
                    }
                    for issue in sentence_remaining_issues
                )
                automatic_correction_count += sum(1 for entry in sentence_repairs if entry["mode"] == "automatic")
                curated_correction_count += sum(1 for entry in sentence_repairs if entry["mode"] == "curated")
                leakage_remaining_issues.extend(
                    {
                        "section_id": section_id,
                        "token": issue["token"],
                        "issue_type": issue["issue_type"],
                        "source_path": repo_relative(ARCHIVE_RAW_TEXT_PATH),
                    }
                    for issue in detect_mozi_leakage_issues(repaired_sentence)
                )
                english_segments.append(
                    _sentence_segment_record(
                        section_id=section_id,
                        source_id=target_source_id,
                        segment_index=index,
                        sentence_text=repaired_sentence,
                        language="en",
                        section_number=section_number,
                    )
                )
            english_segments_path = EN_SEGMENTS_DIR / f"{WORK_ID}__{section_id}__{target_source_id}__segments.jsonl"
            write_jsonl(english_segments_path, english_segments)
            staged_english_units.extend(
                {
                    "section_id": section_id,
                    "canonical_chapter_number": canonical_chapter_number,
                    "language": "en",
                    "unit_type": "sentence",
                    "position": segment["segment_order"],
                    "text_original": segment["text_original"],
                    "source_witness": "Mei 1929 Archive.org OCR",
                }
                for segment in english_segments
            )

            fallback_reason = ""
            anchor_map = alignment_anchor_maps.get(section_id)
            override = alignment_overrides.get(section_id)
            alignment_anchor_map_used = False
            alignment_curated_override_used = False
            alignment_strategy = "monotonic_sentence_grouping"
            drift_checks_run += 1
            try:
                if anchor_map and override:
                    try:
                        auto_alignment = refine_alignment(
                            section_id,
                            chinese_units,
                            english_units,
                            source_splitter=None,
                            target_splitter=None,
                            default_segment_granularity="sentence",
                            block_alignment_granularity="sentence",
                            max_source_group_size=6,
                            max_target_group_size=6,
                            override=None,
                        )
                        drift_issue_count_before_repair += len(
                            find_anchor_drift_issues(
                                _alignment_preview_rows(section_id, auto_alignment),
                                list(anchor_map.get("anchors", [])),
                            )
                        )
                    except ValueError:
                        pass
                alignment = refine_alignment(
                    section_id,
                    chinese_units,
                    english_units,
                    source_splitter=None,
                    target_splitter=None,
                    default_segment_granularity="sentence",
                    block_alignment_granularity="sentence",
                    max_source_group_size=6,
                    max_target_group_size=6,
                    override=override,
                )
                alignment_strategy = str(alignment.get("strategy") or alignment_strategy)
                alignment_curated_override_used = bool(alignment.get("curated_override_used"))
                if alignment_curated_override_used:
                    curated_override_section_ids.append(section_id)
                if anchor_map:
                    anchor_drift_issues = find_anchor_drift_issues(
                        _alignment_preview_rows(section_id, alignment),
                        list(anchor_map.get("anchors", [])),
                    )
                    alignment_anchor_map_used = True
                    anchor_mapped_section_ids.append(section_id)
                    remaining_drift_issue_count += len(anchor_drift_issues)
                    if anchor_drift_issues:
                        raise ValueError(
                            "Anchor drift remains after repair: "
                            + "; ".join(f"{issue['anchor_id']} ({issue['issue']})" for issue in anchor_drift_issues)
                        )
                    alignment["anchor_map_used"] = True
                    alignment["anchor_count"] = len(anchor_map.get("anchors", []))
                else:
                    alignment["anchor_map_used"] = False
                    alignment["anchor_count"] = 0
                alignment_records = _build_alignment_records(
                    section_id=section_id,
                    source_id=source_id,
                    target_source_id=target_source_id,
                    section_number=section_number,
                    chinese_segments=source_segments,
                    english_segments=english_segments,
                    alignment=alignment,
                    notes="Monotonic sentence alignment over ChineseNotes Chinese and Mei OCR English sentence units.",
                )
                leakage_remaining_issues.extend(
                    {
                        "section_id": section_id,
                        "token": issue["token"],
                        "issue_type": issue["issue_type"],
                        "source_path": repo_relative(ARCHIVE_RAW_TEXT_PATH),
                    }
                    for record in alignment_records
                    for issue in detect_mozi_leakage_issues(str(record.get("translation_text", "")))
                )
                exact_rows = [record for record in alignment_records if record["alignment_type"] == "exact_or_near_exact"]
                final_ocr_remaining_issues.extend(
                    {
                        "section_id": section_id,
                        "alignment_id": str(record["alignment_id"]),
                        "token": issue["token"],
                        "issue_type": issue["issue_type"],
                        "source_path": repo_relative(ARCHIVE_RAW_TEXT_PATH),
                    }
                    for record in exact_rows
                    for issue in detect_mozi_ocr_issues(str(record.get("translation_text", "")))
                )
                final_leakage_remaining_issues.extend(
                    {
                        "section_id": section_id,
                        "alignment_id": str(record["alignment_id"]),
                        "token": issue["token"],
                        "issue_type": issue["issue_type"],
                        "source_path": repo_relative(ARCHIVE_RAW_TEXT_PATH),
                    }
                    for record in exact_rows
                    for issue in detect_mozi_leakage_issues(str(record.get("translation_text", "")))
                )
                for record in exact_rows:
                    granularity = record["alignment_granularity"]
                    alignment_granularity_counts[granularity] = alignment_granularity_counts.get(granularity, 0) + 1
                exact_alignment_count += len(exact_rows)
            except ValueError as exc:
                raw_fallback_reason = str(exc)
                if len(source_segments) <= 2 and len(english_segments) >= 30:
                    fallback_reason = (
                        "ChineseNotes source segmentation remains too coarse for grouped alignment at this chapter scale; "
                        "retained chapter-level fallback after OCR repair."
                    )
                else:
                    fallback_reason = (
                        "English OCR segmentation still requires chapter-level coarse alignment after repair because grouped "
                        f"alignment remained unreliable ({raw_fallback_reason})."
                    )
                fallback_section_count += 1
                alignment_records = _build_section_fallback_alignment(
                    section_id=section_id,
                    source_id=source_id,
                    target_source_id=target_source_id,
                    section_number=section_number,
                    chinese_segments=source_segments,
                    english_segments=english_segments,
                    reason=fallback_reason,
                )
                exact_alignment_count += 1
                alignment_granularity_counts["chapter"] = alignment_granularity_counts.get("chapter", 0) + 1
                fallback_sections.append(
                    {
                        "section_id": section_id,
                        "coarse_alignment_reason": fallback_reason,
                    }
                )

            source_suffix = source_id.split("__", 1)[1]
            target_suffix = target_source_id.split("__", 1)[1]
            alignments_path = ALIGNMENTS_DIR / f"{WORK_ID}__{section_id}__{source_suffix}__{target_suffix}__alignments.jsonl"
            write_jsonl(alignments_path, alignment_records)

            manifest_section.update(
                {
                    "status": "complete",
                    "corpus_use_status": PROOF_OF_CONCEPT_USE_STATUS,
                    "export_status": "active",
                    "source_ids": {"source_id": source_id, "target_source_id": target_source_id},
                    "translation_processed_path": repo_relative(english_segments_path),
                    "alignment_processed_path": repo_relative(alignments_path),
                    "alignment_status": "complete",
                    "tmx_status": "complete",
                    "expected_exact_alignment_count": len(
                        [record for record in alignment_records if record["alignment_type"] == "exact_or_near_exact"]
                    ),
                    "notes": (
                        "Proof-of-concept export built from ChineseNotes Chinese plus Archive.org OCR capture of Yi-Pao Mei 1929. "
                        "Rights review remains pending before any release."
                    ),
                    "fallback_reason": fallback_reason or None,
                }
            )
            inventory_unit.update(
                {
                    "english_source_url": ARCHIVE_ITEM_URL,
                    "target_source_id": target_source_id,
                    "decision": "proof_of_concept_export",
                    "coverage_status": "proof_of_concept_export",
                    "export_status": "active",
                    "corpus_use_status": PROOF_OF_CONCEPT_USE_STATUS,
                    "rights_status": PROOF_OF_CONCEPT_RIGHTS_STATUS,
                    "english_witness_status": "archive_ocr_mei_1929",
                    "verification_status": "proof_of_concept_witness_captured",
                    "translation_processed_path": repo_relative(english_segments_path),
                    "alignment_processed_path": repo_relative(alignments_path),
                    "blocker_reason": "",
                }
            )
            manifest_sources.append(
                {
                    "source_id": target_source_id,
                    "work_id": WORK_ID,
                    "section_id": section_id,
                    "language_code": "en",
                    "source_kind": "ocr_full_text_capture",
                    "author_or_translator_ids": ["yi-pao-mei"],
                    "citation": f"Yi-Pao Mei, The Works of Motse from the Chinese (Archive.org OCR), {english_title}.",
                    "source_url": ARCHIVE_ITEM_URL,
                    "raw_path": repo_relative(ARCHIVE_RAW_TEXT_PATH),
                    "processed_path": repo_relative(english_segments_path),
                    "rights_status": PROOF_OF_CONCEPT_RIGHTS_STATUS,
                    "release_status": PROOF_OF_CONCEPT_RELEASE_STATUS,
                    "rights_note": "Usable proof-of-concept English witness with attribution and provenance recorded, but public-domain/release clearance has not yet been verified for redistribution.",
                    "notes": "Per-section English extracted deterministically from the committed Archive.org OCR capture. Use for research proof-of-concept TM only until rights review is complete.",
                }
            )
            verification_ledger.append(
                {
                    "section_id": section_id,
                    "canonical_chapter_number": canonical_chapter_number,
                    "title_zh": chinese_title,
                    "title_en": english_title,
                    "decision": "proof_of_concept_export",
                    "export_status": "active",
                    "corpus_use_status": PROOF_OF_CONCEPT_USE_STATUS,
                    "release_status": PROOF_OF_CONCEPT_RELEASE_STATUS,
                    "rights_status": PROOF_OF_CONCEPT_RIGHTS_STATUS,
                    "source_id": source_id,
                    "target_source_id": target_source_id,
                    "source_url": source_url,
                    "translation_source_url": ARCHIVE_ITEM_URL,
                    "translation_lookup_url": ARCHIVE_DOWNLOAD_URL,
                    "source_path": repo_relative(raw_capture_path),
                    "translation_source_path": repo_relative(ARCHIVE_RAW_TEXT_PATH),
                    "processed_source_path": repo_relative(source_segments_path),
                    "processed_translation_path": repo_relative(english_segments_path),
                    "processed_alignment_path": repo_relative(alignments_path),
                    "alignment_strategy": alignment_strategy,
                    "alignment_fallback_reason": fallback_reason or "",
                    "translator_attribution": "Yi-Pao Mei",
                    "rights_note": "Proof-of-concept export retained for TM research while release clearance remains pending.",
                    "reviewer_note": "Clean usable English captured from committed Mei OCR witness.",
                }
            )
            qc_sections.append(
                {
                    "section_id": section_id,
                    "canonical_chapter_number": canonical_chapter_number,
                    "decision": "proof_of_concept_export",
                    "source_sentence_count": len(source_segments),
                    "target_sentence_count": len(english_segments),
                    "exact_alignment_count": manifest_section["expected_exact_alignment_count"],
                    "fallback_used": bool(fallback_reason),
                    "fallback_reason": fallback_reason,
                    "alignment_anchor_map_used": alignment_anchor_map_used,
                    "curated_override_used": alignment_curated_override_used,
                    "rights_status": PROOF_OF_CONCEPT_RIGHTS_STATUS,
                    "release_status": PROOF_OF_CONCEPT_RELEASE_STATUS,
                }
            )
            active_section_count += 1
        else:
            blocker_reason = _metadata_only_reason(canonical_chapter_number)
            _remove_stale_blocked_section_artifacts(section_id)
            manifest_section["blockers"] = [blocker_reason]
            manifest_section["notes"] = blocker_reason
            inventory_unit["blocker_reason"] = blocker_reason
            blocked_sections.append(
                {
                    "section_id": section_id,
                    "canonical_chapter_number": canonical_chapter_number,
                    "reason": blocker_reason,
                }
            )
            verification_ledger.append(
                {
                    "section_id": section_id,
                    "canonical_chapter_number": canonical_chapter_number,
                    "title_zh": chinese_title,
                    "title_en": english_title,
                    "decision": "metadata_only",
                    "export_status": "metadata_only",
                    "corpus_use_status": "blocked",
                    "release_status": PROOF_OF_CONCEPT_RELEASE_STATUS,
                    "rights_status": BLOCKED_RIGHTS_STATUS,
                    "source_id": source_id,
                    "target_source_id": "",
                    "source_url": source_url,
                    "translation_source_url": "",
                    "translation_lookup_url": "",
                    "source_path": repo_relative(raw_capture_path),
                    "translation_source_path": "",
                    "processed_source_path": repo_relative(source_segments_path),
                    "processed_translation_path": "",
                    "processed_alignment_path": "",
                    "alignment_strategy": "",
                    "alignment_fallback_reason": "",
                    "translator_attribution": "",
                    "rights_note": blocker_reason,
                    "reviewer_note": blocker_reason,
                }
            )
            qc_sections.append(
                {
                    "section_id": section_id,
                    "canonical_chapter_number": canonical_chapter_number,
                    "decision": "metadata_only",
                    "source_sentence_count": len(source_segments),
                    "target_sentence_count": 0,
                    "exact_alignment_count": 0,
                    "fallback_used": False,
                    "fallback_reason": "",
                    "rights_status": BLOCKED_RIGHTS_STATUS,
                    "release_status": PROOF_OF_CONCEPT_RELEASE_STATUS,
                }
            )

        manifest_sections.append(manifest_section)
        inventory_units.append(inventory_unit)

    repaired_leakage_issue_count = max(pre_repair_leakage_issue_count - len(final_leakage_remaining_issues), 0)
    repaired_drift_issue_count = max(drift_issue_count_before_repair - remaining_drift_issue_count, 0)

    summary = {
        "work_id": WORK_ID,
        "work_title_zh": WORK_TITLE_ZH,
        "work_title_en": WORK_TITLE_EN,
        "section_count": len(source_rows),
        "complete_sections": active_section_count,
        "metadata_only_sections": len(source_rows) - active_section_count,
        "total_section_count": len(source_rows),
        "active_section_count": active_section_count,
        "exportable_section_count": active_section_count,
        "metadata_only_section_count": len(source_rows) - active_section_count,
        "blocked_section_count": len(source_rows) - active_section_count,
        "exact_alignment_count": exact_alignment_count,
        "automatic_alignment_count": exact_alignment_count,
        "alignment_record_count": exact_alignment_count + active_section_count,
        "section_group_alignment_record_count": active_section_count,
        "alignment_granularity_counts": alignment_granularity_counts,
        "curated_override_section_count": len(curated_override_section_ids),
        "fallback_section_count": fallback_section_count,
        "rights_review_required_section_count": active_section_count,
        "release_ready_section_count": 0,
        "genuine_blocker_count": len(source_rows) - active_section_count,
        "english_witness": "Archive.org DjVu OCR capture of Yi-Pao Mei, The Works of Motse from the Chinese (1929) for the translated chapter subset",
        "work_state": "proof_of_concept_partial_active",
        "hard_failure_count": 0,
        "corruption_issue_count": len(final_ocr_remaining_issues),
        "pre_repair_corruption_issue_count": pre_repair_corruption_issue_count,
        "corrected_corruption_issue_count": automatic_correction_count + curated_correction_count,
        "automatic_correction_count": automatic_correction_count,
        "curated_correction_count": curated_correction_count,
        "remaining_corruption_issue_count": len(final_ocr_remaining_issues),
        "pre_repair_leakage_issue_count": pre_repair_leakage_issue_count,
        "repaired_leakage_issue_count": repaired_leakage_issue_count,
        "remaining_leakage_issue_count": len(final_leakage_remaining_issues),
        "drift_checks_run": drift_checks_run,
        "anchor_mapped_section_count": len(anchor_mapped_section_ids),
        "drift_issue_count_before_repair": drift_issue_count_before_repair,
        "repaired_drift_issue_count": repaired_drift_issue_count,
        "remaining_drift_issue_count": remaining_drift_issue_count,
    }

    manifest = {
        "work_id": WORK_ID,
        "title_zh": WORK_TITLE_ZH,
        "title_en": WORK_TITLE_EN,
        "title_variants": WORK_TITLE_VARIANTS,
        "status": "active",
        "corpus_use_status": PROOF_OF_CONCEPT_USE_STATUS,
        "release_status": PROOF_OF_CONCEPT_RELEASE_STATUS,
        "source_urls": source_url_entries,
        "source_audit_status": "complete",
        "source_audit_note": "Proof-of-concept active subset built from ChineseNotes Chinese plus committed Archive.org OCR capture of Yi-Pao Mei 1929. Alternate Archive.org OCR layers (ABBYY XML, DjVu XML, hOCR HTML, and search text) were reviewed, but no materially cleaner drop-in text layer was found; active exports therefore use the archived OCR text with deterministic repair rules and explicit repair logging.",
        "inventory_status": "complete",
        "ingestion_log_status": "complete",
        "alignment_status": "complete",
        "tmx_status": "complete",
        "ingestion_policy": {
            "status": "aligned_or_metadata_only",
            "inventory_required": True,
            "inventory_path": "metadata/mozi_inventory.yml",
            "inventory_unit_key": "units",
            "source_inventory_required": True,
            "source_inventory_path": "metadata/mozi_inventory.yml",
            "ingestion_plan_required": True,
            "ingestion_plan_path": "documentation/mozi_ingestion_plan.md",
            "source_audit_required": True,
            "source_audit_path": "documentation/mozi_ingestion_plan.md",
            "granularity_policy_required": True,
            "granularity_policy_path": "documentation/alignment_granularity_policy.md",
            "section_unit": "chapter",
            "preferred_segment_unit": "sentence",
            "minimum_required_alignment_scope": "chapter",
            "maximum_exact_alignment_scope": "chapter",
            "allowed_segment_units": ["sentence", "grouped", "block", "chapter"],
            "coarse_alignment_units": ["chapter"],
            "granularity_order": ["sentence", "grouped", "block", "chapter"],
            "metadata_only_allowed": True,
            "missing_text_policy": "block_export_if_clean_chinese_or_english_text_is_missing",
            "commentary_policy": "exclude_commentary_headings_and_notice_lines_from_exportable_segments_before_alignment",
            "rights_policy": "proof_of_concept_export_allowed_with_explicit_rights_review",
            "allowed_export_rights_statuses": [
                "public_domain",
                PROOF_OF_CONCEPT_RIGHTS_STATUS,
                "mixed_source_review_required",
                BLOCKED_RIGHTS_STATUS,
            ],
            "section_group_export_policy": "forbidden",
            "completion_definition": "A Mozi chapter is complete for proof-of-concept use only when the ChineseNotes Chinese base text and an attributable English witness are both captured cleanly enough for sentence-level or grouped alignment, source and rights metadata are explicit, and any coarse fallback is exported with a recorded reason. Release readiness remains separate from active proof-of-concept export.",
        },
        "notes": "Mozi is active as a proof-of-concept corpus. Exportable chapters use ChineseNotes Chinese plus Archive.org OCR of Yi-Pao Mei 1929, with explicit rights-review metadata, release_status not_cleared, deterministic OCR repair logging, and note/commentary leakage exclusion before alignment. Remaining chapters stay metadata-only only for genuine witness-parsing or missing-English reasons.",
        "summary": summary,
        "romanization_aliases": romanization_aliases,
        "sources": manifest_sources,
        "sections": manifest_sections,
    }

    alignment_qc_report = {
        "summary": summary,
        "sections": qc_sections,
        "blocked_sections": blocked_sections,
        "fallback_sections": fallback_sections,
        "curated_override_sections": curated_override_section_ids,
        "anchor_mapped_sections": anchor_mapped_section_ids,
    }

    coverage_mapping = _mapping_entry_template()
    coverage_mapping.update(
        {
            "chintransmem_work_id": WORK_ID,
            "chinesenotes_paths": ["data/corpus/mozi.csv", "corpus/mozi/"],
            "status": "proof_of_concept_ingested",
            "english_coverage": "partial",
            "chinese_coverage": "complete",
            "preferred_use": "proof_of_concept",
            "notes": (
                f"ChineseNotes Chinese scaffold with Archive.org Mei 1929 OCR English for {active_section_count} proof-of-concept-active chapters; "
                f"{len(source_rows) - active_section_count} chapters remain metadata-only pending a clean attributable English witness. "
                "Available alternate Archive.org OCR layers were reviewed, but deterministic repair of the committed OCR text proved more reliable than switching layers."
            ),
            "generated_summary": summary,
        }
    )

    write_jsonl(STAGING_DIR / "chinese_blocks.jsonl", staged_chinese_units)
    write_jsonl(STAGING_DIR / "english_blocks.jsonl", staged_english_units)
    write_json(METADATA_DIR / "manifests" / "mozi.yml", manifest)
    write_json(METADATA_DIR / "mozi_inventory.yml", {"work_id": WORK_ID, "units": inventory_units})
    write_json(METADATA_DIR / "mozi_verification_ledger.yml", {"work_id": WORK_ID, "entries": verification_ledger})
    write_json(
        LOGS_DIR / "mozi__ocr_repair_log.json",
        {
            "summary": {
                "issue_count_before_repair": pre_repair_corruption_issue_count,
                "automatic_correction_count": automatic_correction_count,
                "curated_correction_count": curated_correction_count,
                "remaining_issue_count": len(final_ocr_remaining_issues),
                "pre_repair_leakage_issue_count": pre_repair_leakage_issue_count,
                "repaired_leakage_issue_count": repaired_leakage_issue_count,
                "remaining_leakage_issue_count": len(final_leakage_remaining_issues),
                "automatic_leakage_repair_count": len(leakage_repair_entries),
                "remaining_total_issue_count": len(final_ocr_remaining_issues) + len(final_leakage_remaining_issues),
                "cleaner_source_layer_found": False,
                "source_layer_audit": {
                    "reviewed_layers": [
                        "Archive.org DjVu OCR text",
                        "Archive.org ABBYY XML",
                        "Archive.org DjVu XML",
                        "Archive.org hOCR HTML",
                        "Archive.org hOCR search text",
                    ],
                    "selected_layer": "Archive.org DjVu OCR text with deterministic repair rules",
                },
            },
            "repairs": ocr_repair_entries + leakage_repair_entries,
            "remaining_issues": final_ocr_remaining_issues + final_leakage_remaining_issues,
        },
    )

    existing_mapping = load_json_compatible_yaml(METADATA_DIR / "chinesenotes_work_mapping.yml")
    updated_mapping: list[dict[str, Any]] = []
    replaced = False
    for entry in existing_mapping.get("works", []):
        if entry.get("chintransmem_work_id") == WORK_ID:
            updated_mapping.append(coverage_mapping)
            replaced = True
        else:
            updated_mapping.append(entry)
    if not replaced:
        updated_mapping.append(coverage_mapping)
    write_json(METADATA_DIR / "chinesenotes_work_mapping.yml", {"works": updated_mapping})

    write_json(LOGS_DIR / "mozi__alignment_qc.json", alignment_qc_report)
    completion_markdown = render_completion_quality_markdown(
        alignment_qc_report,
        work_label="Mozi completion quality",
        report_path=repo_relative(LOGS_DIR / "mozi__alignment_qc.json"),
    )
    completion_markdown += (
        "\n## Proof-of-concept rights posture\n"
        f"- Active Mozi exports: {active_section_count}\n"
        f"- Rights review required: {active_section_count}\n"
        "- Release-ready chapters: 0\n"
        f"- Metadata-only genuine blockers: {len(source_rows) - active_section_count}\n"
    )
    (DOCS_DIR / "mozi_completion_quality.md").write_text(completion_markdown, encoding="utf-8")

    manifest_digest = hashlib.sha256(json.dumps(manifest, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    print(
        f"Bootstrapped {WORK_ID}: {active_section_count} proof-of-concept-active chapters, "
        f"{len(source_rows) - active_section_count} metadata-only blockers, {exact_alignment_count} exact/grouped export rows."
    )
    print(f"Manifest digest: {manifest_digest}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap the Mozi corpus from ChineseNotes and Mei OCR.")
    parser.add_argument("--skip-fetch", action="store_true", help="Use existing raw captures only.")
    args = parser.parse_args()
    print(json.dumps(bootstrap_corpus(skip_fetch=args.skip_fetch), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
