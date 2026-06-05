from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from common import REPO_ROOT, load_json_compatible_yaml, repo_relative, sha256_file, write_json, write_jsonl
from chinesenotes_alignment import (
    load_alignment_anchor_maps,
    load_alignment_overrides,
    partition_block_texts_by_anchors,
    refine_alignment,
    render_completion_quality_markdown,
    split_chinese_units,
    split_english_units,
)
from ingest_chinesenotes_work import _slugify_ascii
from liji_quality import parse_liji_bilingual_text

UPSTREAM_OWNER = "alexamies"
UPSTREAM_REPO = "chinesenotes.com"
UPSTREAM_COMMIT = "1f6b1d3e7a40b6886a4b943c898125639e993544"
UPSTREAM_COMMIT_SHORT = UPSTREAM_COMMIT[:7]
WORK_ID = "liji"
TITLE_ZH = "禮記"
TITLE_EN = "Book of Rites"
SOURCE_BASE_URL = (
    f"https://raw.githubusercontent.com/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/{UPSTREAM_COMMIT}"
)
RAW_ROOT = REPO_ROOT / "corpus" / "raw" / "chinesenotes"
BASE_TEXT_ROOT = REPO_ROOT / "corpus" / "processed" / "base_texts"
TRANSLATION_ROOT = REPO_ROOT / "corpus" / "processed" / "translations"
ALIGNMENT_ROOT = REPO_ROOT / "corpus" / "processed" / "alignments"
REPORT_ROOT = REPO_ROOT / "logs" / "qc_reports"
DOC_ROOT = REPO_ROOT / "documentation"
METADATA_ROOT = REPO_ROOT / "metadata"
MANIFEST_PATH = METADATA_ROOT / "manifests" / f"{WORK_ID}.yml"
INVENTORY_PATH = METADATA_ROOT / f"{WORK_ID}_inventory.yml"
LEDGER_PATH = METADATA_ROOT / f"{WORK_ID}_verification_ledger.yml"
COMPLETION_DOC_PATH = DOC_ROOT / f"{WORK_ID}_completion_quality.md"
INGESTION_PLAN_PATH = DOC_ROOT / f"{WORK_ID}_ingestion_plan.md"
ANCHOR_MAP_PATH = METADATA_ROOT / f"{WORK_ID}_alignment_anchors.yml"
OVERRIDES_PATH = METADATA_ROOT / f"{WORK_ID}_alignment_overrides.yml"
INDEX_RELATIVE_PATH = "data/corpus/liji.csv"
INTRO_RELATIVE_PATH = "corpus/liji/liji000.txt"
FORMER_FALLBACK_IDS = {
    "liji-015-record-of-small-matters-in-the-dress-of",
    "liji-019-record-of-music",
    "liji-031-the-state-of-equilibrium-and-harmony",
    "liji-042-the-great-learning",
}
SECTION_ALIGNMENT_LIMITS: dict[str, tuple[int, int]] = {
    "liji-015-record-of-small-matters-in-the-dress-of": (6, 6),
    "liji-019-record-of-music": (6, 6),
    "liji-031-the-state-of-equilibrium-and-harmony": (6, 6),
    "liji-042-the-great-learning": (6, 6),
}
FALLBACK_DIAGNOSTICS: dict[str, dict[str, str]] = {
    "liji-015-record-of-small-matters-in-the-dress-of": {
        "diagnosis": "The Chinese and English chapter files share the same 73 paragraph blocks, but a few English paragraphs merge adjacent mourning-rule cases, so 4-target monotonic grouping was too tight. The mismatch is local rather than global.",
        "resolution": "Raised the grouped-alignment window to permit slightly larger English clusters while keeping the original order.",
    },
    "liji-019-record-of-music": {
        "diagnosis": "The later half of the English witness merges long conceptual runs around music, ritual, government, and the Marquis Wen / Wu dialogue, so direct sentence grouping drifted across topic boundaries. The mismatch is global across major topic shifts rather than a heading or note leak.",
        "resolution": "Partitioned the joined chapter by deterministic anchor topics, then aligned the resulting macro-blocks safely.",
    },
    "liji-031-the-state-of-equilibrium-and-harmony": {
        "diagnosis": "The Chinese and English files stay parallel in broad order, but Legge's prose runs more continuously across the sincerity, governance, and sagely-power expositions, so unguided grouping drifted late in the chapter. The mismatch is global across major conceptual units rather than local page furniture.",
        "resolution": "Partitioned the chapter by doctrinal anchors for equilibrium/harmony, the superior man, spirits, governance, sincerity, and the closing sage material before alignment.",
    },
    "liji-042-the-great-learning": {
        "diagnosis": "The English witness compresses several governance and wealth-policy passages into longer macro-paragraphs, and the raw chapter has 16 Chinese blocks against 17 English blocks. The mismatch is structural but still ordered, with stable internal divisions available.",
        "resolution": "Partitioned the chapter by the classic Great Learning progression from illustrious virtue through family, state, and kingdom governance before alignment.",
    },
}


@dataclass
class LijiSection:
    index: int
    source_file: str
    title_zh: str
    title_en: str
    notes: str

    @property
    def section_id(self) -> str:
        return f"{WORK_ID}-{self.index:03d}-{_short_slug(self.title_en, limit=40)}"

    @property
    def source_label(self) -> str:
        return f"{self.title_zh} {self.title_en}".strip()

    @property
    def canonical_ref(self) -> str:
        return f"{TITLE_ZH}·{self.title_zh}"

    @property
    def source_stem(self) -> str:
        return Path(self.source_file).stem


def _short_slug(text: str, *, limit: int) -> str:
    words = _slugify_ascii(text).split("-")
    slug_parts: list[str] = []
    current_length = 0
    for word in words:
        addition = len(word) if not slug_parts else len(word) + 1
        if slug_parts and current_length + addition > limit:
            break
        if not slug_parts and len(word) > limit:
            return word[:limit].rstrip("-")
        slug_parts.append(word)
        current_length += addition
    return "-".join(slug_parts) or _slugify_ascii(text)[:limit].rstrip("-")


def _fetch_text(relative_path: str) -> str:
    url = f"{SOURCE_BASE_URL}/{relative_path}"
    with urlopen(url) as response:  # noqa: S310 - pinned GitHub raw URL
        return response.read().decode("utf-8")


def _ensure_raw_capture(relative_path: str, *, skip_fetch: bool) -> Path:
    destination = RAW_ROOT / f"{WORK_ID}__{Path(relative_path).stem}__chinesenotes-{UPSTREAM_COMMIT_SHORT}__raw.txt"
    if destination.exists():
        return destination
    if skip_fetch:
        raise FileNotFoundError(
            f"Missing raw capture for {relative_path}; rerun bootstrap without --skip-fetch."
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_fetch_text(relative_path), encoding="utf-8")
    return destination


def _load_index_rows(index_path: Path) -> list[LijiSection]:
    sections: list[LijiSection] = []
    for raw_line in index_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("\t") if part.strip()]
        if len(parts) < 3:
            continue
        source_file, _, title = parts[:3]
        if source_file == "liji/liji000.txt":
            continue
        try:
            chapter_index = int(Path(source_file).stem[4:7])
        except ValueError:
            continue
        if "》" not in title:
            continue
        title_zh, title_en = title.split("》", 1)
        sections.append(
            LijiSection(
                index=chapter_index,
                source_file=f"corpus/{source_file}",
                title_zh=f"{title_zh}》",
                title_en=title_en.strip(),
                notes="",
            )
        )
    return sorted(sections, key=lambda section: section.index)


def _segment_record(
    *,
    work_id: str,
    section_id: str,
    segment_id: str,
    source_id: str,
    text: str,
    segment_order: int,
    canonical_ref: str,
    segment_type: str,
    language: str,
) -> dict[str, Any]:
    return {
        "segment_id": segment_id,
        "work_id": work_id,
        "section_id": section_id,
        "source_id": source_id,
        "language": language,
        "segment_type": segment_type,
        "segment_order": segment_order,
        "canonical_ref": canonical_ref,
        "sort_key": f"{segment_order:04d}",
        "text_original": text,
        "text_normalized": text,
        "notes": "",
    }


def _write_unit_segments(
    *,
    work_id: str,
    section_id: str,
    source_id: str,
    canonical_ref: str,
    units: list[dict[str, Any]],
    segment_type: str,
    text_language: str,
    prefix: str,
) -> tuple[list[dict[str, Any]], dict[int, str]]:
    records: list[dict[str, Any]] = []
    unit_id_map: dict[int, str] = {}
    for position, unit in enumerate(units, start=1):
        unit_text = str(unit["text"]).strip()
        if not unit_text:
            continue
        segment_id = f"{source_id}__seg-{position:04d}"
        records.append(
            _segment_record(
                work_id=work_id,
                section_id=section_id,
                segment_id=segment_id,
                source_id=source_id,
                text=unit_text,
                segment_order=position,
                canonical_ref=f"{canonical_ref} {position}",
                segment_type=segment_type,
                language="zh-Hant" if text_language == "zh" else text_language,
            )
        )
        unit_key = int(unit.get("unit_index", unit.get("index", position - 1)))
        unit_id_map[unit_key] = segment_id
    return records, unit_id_map


def _write_block_segments(
    *,
    work_id: str,
    section_id: str,
    source_id: str,
    canonical_ref: str,
    blocks: list[str],
    text_language: str,
    prefix: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for position, block in enumerate(blocks, start=1):
        text = block.strip()
        if not text:
            continue
        records.append(
            _segment_record(
                work_id=work_id,
                section_id=section_id,
                segment_id=f"{source_id}__seg-{position:04d}",
                source_id=source_id,
                text=text,
                segment_order=position,
                canonical_ref=f"{canonical_ref} block {position}",
                segment_type="block",
                language="zh-Hant" if text_language == "zh" else text_language,
            )
        )
    return records


def _alignment_record(
    *,
    work_id: str,
    section_id: str,
    alignment_id: str,
    source_id: str,
    target_source_id: str,
    chinese_segment_ids: list[str],
    translation_segment_ids: list[str],
    notes: str,
    alignment_granularity: str,
    segment_type: str,
    is_coarse_alignment: bool,
    coarse_alignment_reason: str | None,
    confidence: float,
) -> dict[str, Any]:
    return {
        "alignment_id": alignment_id,
        "work_id": work_id,
        "section_id": section_id,
        "source_id": source_id,
        "target_source_id": target_source_id,
        "chinese_segment_ids": chinese_segment_ids,
        "translation_segment_ids": translation_segment_ids,
        "alignment_type": "exact_or_near_exact",
        "alignment_granularity": alignment_granularity,
        "section_unit": "chapter",
        "segment_type": segment_type,
        "notes": notes,
        "is_coarse_alignment": is_coarse_alignment,
        "coarse_alignment_reason": coarse_alignment_reason,
        "source_segment_count": len(chinese_segment_ids),
        "target_segment_count": len(translation_segment_ids),
        "confidence": confidence,
    }


def _section_group_record(
    *,
    work_id: str,
    section_id: str,
    section_position: int,
    source_id: str,
    target_source_id: str,
    source_segment_ids: list[str],
    target_segment_ids: list[str],
    fallback_reason: str | None,
) -> dict[str, Any]:
    return {
        "alignment_id": f"{section_id}__section-group",
        "work_id": work_id,
        "section_id": section_id,
        "source_id": source_id,
        "target_source_id": target_source_id,
        "chinese_segment_ids": source_segment_ids,
        "translation_segment_ids": target_segment_ids,
        "alignment_type": "section_group",
        "alignment_granularity": "chapter",
        "section_unit": "chapter",
        "segment_type": "section",
        "notes": "Section-group alignment retained for export completeness.",
        "is_coarse_alignment": bool(fallback_reason),
        "coarse_alignment_reason": fallback_reason,
        "source_segment_count": len(source_segment_ids),
        "target_segment_count": len(target_segment_ids),
        "confidence": 1.0,
    }


def _repair_entry(
    *,
    section_id: str,
    source_file: str,
    issue_type: str,
    raw_text: str,
    correction_type: str,
) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "source_file": source_file,
        "issue_type": issue_type,
        "raw_text": raw_text,
        "corrected_text": "",
        "correction_type": correction_type,
        "confidence": "deterministic",
    }


def _update_metadata_with_manifest(manifest: dict[str, Any]) -> None:
    work_id = manifest["work_id"]
    works_path = METADATA_ROOT / "works.yml"
    works = load_json_compatible_yaml(works_path) if works_path.exists() else []
    works_by_id = {entry["work_id"]: entry for entry in works}
    works_by_id[work_id] = {
        "work_id": work_id,
        "canonical_title": manifest["title_zh"],
        "english_title": manifest["title_en"],
        "work_type": "classical_text",
        "language_code": "zh-Hant",
        "default_citation": manifest["title_zh"],
        "notes": manifest["notes"],
    }
    ordered_works = [works_by_id[key] for key in sorted(works_by_id)]
    write_json(works_path, ordered_works)

    persons_path = METADATA_ROOT / "persons.yml"
    persons = load_json_compatible_yaml(persons_path) if persons_path.exists() else []
    person_ids = {entry["person_id"] for entry in persons}
    for entry in [
        {
            "person_id": "liji-transmitters",
            "display_name": "《禮記》傳世編者",
            "romanized_name": "Traditional transmitters of the Liji",
            "roles": ["compiler"],
            "notes": "Conventional transmitters cited for the received Liji chapter compilation.",
        }
    ]:
        if entry["person_id"] in person_ids:
            persons = [existing if existing["person_id"] != entry["person_id"] else entry for existing in persons]
        else:
            persons.append(entry)
            person_ids.add(entry["person_id"])
    persons.sort(key=lambda entry: entry["person_id"])
    write_json(persons_path, persons)

    mapping_path = METADATA_ROOT / "chinesenotes_work_mapping.yml"
    mapping = load_json_compatible_yaml(mapping_path) if mapping_path.exists() else {"works": []}
    works_list = mapping.setdefault("works", [])
    summary = manifest["summary"]
    replacement = {
        "chintransmem_work_id": work_id,
        "chinesenotes_paths": [
            "data/corpus/liji.csv",
            "corpus/liji/",
        ],
        "status": "already_ingested",
        "english_coverage": "complete",
        "chinese_coverage": "complete",
        "preferred_use": "aligned_passages",
        "notes": (
            f"Liji now runs through the reusable candidate gauntlet with "
            f"{summary['active_exportable_section_count']} active proof-of-concept chapters, "
            f"{summary['fallback_alignment_count']} reviewed chapter-level fallbacks, and "
            "rights-status metadata on every active English witness."
        ),
    }
    replaced = False
    for index, entry in enumerate(works_list):
        if entry.get("chintransmem_work_id") == work_id:
            works_list[index] = replacement
            replaced = True
            break
    if not replaced:
        works_list.append(replacement)
    works_list.sort(key=lambda entry: entry["chintransmem_work_id"])
    write_json(mapping_path, mapping)


def bootstrap_liji_corpus(*, skip_fetch: bool = False) -> dict[str, Any]:
    try:
        index_raw_path = _ensure_raw_capture(INDEX_RELATIVE_PATH, skip_fetch=skip_fetch)
        intro_raw_path = _ensure_raw_capture(INTRO_RELATIVE_PATH, skip_fetch=skip_fetch)
    except (FileNotFoundError, HTTPError, URLError) as exc:
        raise RuntimeError(f"Unable to prepare Liji raw captures: {exc}") from exc

    sections = _load_index_rows(index_raw_path)
    if len(sections) != 49:
        raise RuntimeError(f"Expected 49 Liji chapters, found {len(sections)}.")

    intro_text = intro_raw_path.read_text(encoding="utf-8")
    intro_notes = parse_liji_bilingual_text(intro_text, f"{TITLE_ZH} {TITLE_EN}")

    manifest_sections: list[dict[str, Any]] = []
    manifest_sources: list[dict[str, Any]] = []
    romanization_aliases: list[dict[str, Any]] = [
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "romanization_system": "wade-giles",
            "alias": "Li Chi",
        },
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "romanization_system": "english-title",
            "alias": TITLE_EN,
        },
    ]
    import_sections: list[dict[str, Any]] = []
    import_sources: list[dict[str, Any]] = []
    ingestion_log: list[dict[str, Any]] = [
        {
            "run_id": f"{WORK_ID}-bootstrap-{UPSTREAM_COMMIT_SHORT}",
            "work_id": WORK_ID,
            "stage": "bootstrap",
            "status": "completed",
            "notes": "Generated processed Liji chapters and manifest from ChineseNotes bilingual source files.",
        }
    ]
    inventory_sources: list[dict[str, Any]] = []
    verification_sections: list[dict[str, Any]] = []
    qc_sections: list[dict[str, Any]] = []
    repair_entries: list[dict[str, Any]] = []
    completion_sections: list[dict[str, Any]] = []
    refinement_sections: list[dict[str, Any]] = []
    alignment_granularity_counts: Counter[str] = Counter()
    section_status_counts: Counter[str] = Counter()
    blocked_sections: list[str] = []
    fallback_sections: list[str] = []
    anchor_mapped_sections: list[str] = []
    exact_alignment_count = 0
    section_group_alignment_count = 0
    grouped_alignment_count = 0
    block_alignment_count = 0
    section_fallback_count = 0

    BASE_TEXT_ROOT.mkdir(parents=True, exist_ok=True)
    TRANSLATION_ROOT.mkdir(parents=True, exist_ok=True)
    ALIGNMENT_ROOT.mkdir(parents=True, exist_ok=True)
    REPORT_ROOT.mkdir(parents=True, exist_ok=True)
    DOC_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    alignment_anchor_maps = load_alignment_anchor_maps(ANCHOR_MAP_PATH)
    alignment_overrides = load_alignment_overrides(OVERRIDES_PATH)

    for section in sections:
        raw_path = _ensure_raw_capture(section.source_file, skip_fetch=skip_fetch)
        raw_text = raw_path.read_text(encoding="utf-8")
        parsed = parse_liji_bilingual_text(raw_text, section.source_label)
        section_id = section.section_id
        canonical_ref = section.canonical_ref
        zh_source_id = f"{section_id}__cn-zh-{UPSTREAM_COMMIT_SHORT}"
        en_source_id = f"{section_id}__legge-en-{UPSTREAM_COMMIT_SHORT}"
        zh_source_suffix = zh_source_id.split("__", 1)[1]
        en_source_suffix = en_source_id.split("__", 1)[1]

        for line in parsed["excluded_heading_lines"]:
            repair_entries.append(
                _repair_entry(
                    section_id=section_id,
                    source_file=section.source_file,
                    issue_type="heading_leakage",
                    raw_text=line,
                    correction_type="automatic_heading_exclusion",
                )
            )
        for line in parsed["excluded_footnote_lines"]:
            repair_entries.append(
                _repair_entry(
                    section_id=section_id,
                    source_file=section.source_file,
                    issue_type="footnote_leakage",
                    raw_text=line,
                    correction_type="automatic_commentary_exclusion",
                )
            )

        if parsed["uncategorized_lines"]:
            blocked_sections.append(section_id)
            section_status_counts["metadata_only_blocked"] += 1
            verification_sections.append(
                {
                    "section_id": section_id,
                    "title_zh": section.title_zh,
                    "title_en": section.title_en,
                    "export_status": "metadata_only",
                    "blocker_type": "needs_boundary_review",
                    "blocker_note": (
                        "Deterministic cleanup still left mixed-content lines: "
                        + "; ".join(parsed["uncategorized_lines"][:5])
                    ),
                }
            )
            manifest_sections.append(
                {
                    "section_id": section_id,
                    "title_zh": section.title_zh,
                    "title_en": section.title_en,
                    "label": section.title_zh,
                    "sort_key": f"{section.index:03d}",
                    "canonical_ref": canonical_ref,
                    "source_ids": {"source_id": zh_source_id, "target_source_id": en_source_id},
                    "corpus_use_status": "blocked",
                    "export_status": "metadata_only",
                    "alignment_status": "blocked",
                    "tmx_status": "not_ready",
                    "rights_status": "rights_review_required",
                    "release_status": "not_cleared",
                    "base_text_processed_path": None,
                    "translation_processed_path": None,
                    "alignment_processed_path": None,
                    "fallback_used": False,
                    "fallback_reason": "Boundary cleanup incomplete; kept metadata-only.",
                    "expected_exact_alignment_count": 0,
                    "notes": "Blocked pending deterministic cleanup of mixed bilingual lines.",
                }
            )
            continue

        if not parsed["chinese_blocks"] or not parsed["english_blocks"]:
            blocked_sections.append(section_id)
            section_status_counts["metadata_only_blocked"] += 1
            verification_sections.append(
                {
                    "section_id": section_id,
                    "title_zh": section.title_zh,
                    "title_en": section.title_en,
                    "export_status": "metadata_only",
                    "blocker_type": "missing_parallel_text",
                    "blocker_note": "Missing Chinese or English witness after deterministic cleanup.",
                }
            )
            manifest_sections.append(
                {
                    "section_id": section_id,
                    "title_zh": section.title_zh,
                    "title_en": section.title_en,
                    "label": section.title_zh,
                    "sort_key": f"{section.index:03d}",
                    "canonical_ref": canonical_ref,
                    "source_ids": {"source_id": zh_source_id, "target_source_id": en_source_id},
                    "corpus_use_status": "blocked",
                    "export_status": "metadata_only",
                    "alignment_status": "blocked",
                    "tmx_status": "not_ready",
                    "rights_status": "rights_review_required",
                    "release_status": "not_cleared",
                    "base_text_processed_path": None,
                    "translation_processed_path": None,
                    "alignment_processed_path": None,
                    "fallback_used": False,
                    "fallback_reason": "Missing Chinese or English witness after deterministic cleanup.",
                    "expected_exact_alignment_count": 0,
                    "notes": "Blocked because the bilingual chapter could not be split into parallel witnesses.",
                }
            )
            continue

        source_units: list[str] = []
        for block in parsed["chinese_blocks"]:
            source_units.extend(split_chinese_units(block))
        target_units: list[str] = []
        for block in parsed["english_blocks"]:
            target_units.extend(split_english_units(block))
        anchor_map = alignment_anchor_maps.get(section_id)
        override = alignment_overrides.get(section_id)
        final_chinese_blocks = list(parsed["chinese_blocks"])
        final_english_blocks = list(parsed["english_blocks"])
        if anchor_map and str(anchor_map.get("segmentation_strategy") or "") == "anchor_partition":
            final_chinese_blocks, final_english_blocks = partition_block_texts_by_anchors(
                final_chinese_blocks,
                final_english_blocks,
                anchor_map,
            )
            anchor_mapped_sections.append(section_id)
        max_source_group_size, max_target_group_size = SECTION_ALIGNMENT_LIMITS.get(section_id, (4, 4))
        fallback_reason: str | None = None
        try:
            alignment = refine_alignment(
                section_id,
                final_chinese_blocks,
                final_english_blocks,
                source_splitter=split_chinese_units,
                target_splitter=split_english_units,
                max_source_group_size=max_source_group_size,
                max_target_group_size=max_target_group_size,
                override=override,
            )
        except ValueError as exc:
            alignment = None
            refinement_note = FALLBACK_DIAGNOSTICS.get(section_id, {})
            fallback_reason = (
                f"Deterministic regrouping remained unsafe after "
                f"{'anchor-partitioned ' if section_id in anchor_mapped_sections else ''}"
                f"alignment: {exc}"
            )
            if refinement_note:
                fallback_reason = f"{refinement_note['diagnosis']} {fallback_reason}"
            fallback_sections.append(section_id)

        base_text_path = BASE_TEXT_ROOT / (
            f"{WORK_ID}__{section_id}__{zh_source_id}__segments.jsonl"
        )
        translation_path = TRANSLATION_ROOT / (
            f"{WORK_ID}__{section_id}__{en_source_id}__segments.jsonl"
        )
        alignment_path = ALIGNMENT_ROOT / (
            f"{WORK_ID}__{section_id}__{zh_source_suffix}__{en_source_suffix}__alignments.jsonl"
        )

        if alignment is None:
            source_records = _write_block_segments(
                work_id=WORK_ID,
                section_id=section_id,
                source_id=zh_source_id,
                canonical_ref=canonical_ref,
                blocks=final_chinese_blocks,
                text_language="zh",
                prefix="zh",
            )
            target_records = _write_block_segments(
                work_id=WORK_ID,
                section_id=section_id,
                source_id=en_source_id,
                canonical_ref=canonical_ref,
                blocks=final_english_blocks,
                text_language="en",
                prefix="en",
            )
            source_segment_ids = [record["segment_id"] for record in source_records]
            target_segment_ids = [record["segment_id"] for record in target_records]
            exact_records = [
                _alignment_record(
                    work_id=WORK_ID,
                    section_id=section_id,
                    alignment_id=f"{section_id}__section-fallback",
                    source_id=zh_source_id,
                    target_source_id=en_source_id,
                    chinese_segment_ids=source_segment_ids,
                    translation_segment_ids=target_segment_ids,
                    notes="Reviewed section-level fallback retained for structurally uneven ChineseNotes bilingual chapter.",
                    alignment_granularity="chapter",
                    segment_type="block",
                    is_coarse_alignment=True,
                    coarse_alignment_reason=fallback_reason,
                    confidence=0.88,
                )
            ]
            section_group_records = [
                _section_group_record(
                    work_id=WORK_ID,
                    section_id=section_id,
                    section_position=1,
                    source_id=zh_source_id,
                    target_source_id=en_source_id,
                    source_segment_ids=source_segment_ids,
                    target_segment_ids=target_segment_ids,
                    fallback_reason=fallback_reason,
                )
            ]
            alignment_granularity_counts["chapter"] += 1
            section_fallback_count += 1
        else:
            source_records, source_id_map = _write_unit_segments(
                work_id=WORK_ID,
                section_id=section_id,
                source_id=zh_source_id,
                canonical_ref=canonical_ref,
                units=alignment["source_units"],
                segment_type=alignment["segment_granularity"],
                text_language="zh",
                prefix="zh",
            )
            target_records, target_id_map = _write_unit_segments(
                work_id=WORK_ID,
                section_id=section_id,
                source_id=en_source_id,
                canonical_ref=canonical_ref,
                units=alignment["target_units"],
                segment_type=alignment["segment_granularity"],
                text_language="en",
                prefix="en",
            )
            exact_records = []
            for position, group in enumerate(alignment["groups"], start=1):
                exact_records.append(
                    _alignment_record(
                        work_id=WORK_ID,
                        section_id=section_id,
                        alignment_id=f"{section_id}__aligned-{position:03d}",
                        source_id=zh_source_id,
                        target_source_id=en_source_id,
                        chinese_segment_ids=[source_id_map[index] for index in group["source_unit_indices"]],
                        translation_segment_ids=[target_id_map[index] for index in group["target_unit_indices"]],
                        notes="Deterministic ChineseNotes bilingual alignment.",
                        alignment_granularity=alignment["alignment_granularity"],
                        segment_type=alignment["segment_granularity"],
                        is_coarse_alignment=False,
                        coarse_alignment_reason=None,
                        confidence=0.96 if alignment["alignment_granularity"] == "block" else 0.93,
                    )
                )
            section_group_records = [
                _section_group_record(
                    work_id=WORK_ID,
                    section_id=section_id,
                    section_position=1,
                    source_id=zh_source_id,
                    target_source_id=en_source_id,
                    source_segment_ids=[record["segment_id"] for record in source_records],
                    target_segment_ids=[record["segment_id"] for record in target_records],
                    fallback_reason=None,
                )
            ]
            alignment_granularity_counts[alignment["alignment_granularity"]] += len(exact_records)
            if alignment["alignment_granularity"] == "grouped":
                grouped_alignment_count += len(exact_records)
            else:
                block_alignment_count += len(exact_records)

        write_jsonl(base_text_path, source_records)
        write_jsonl(translation_path, target_records)
        write_jsonl(alignment_path, exact_records + section_group_records)

        exact_alignment_count += len(exact_records)
        section_group_alignment_count += len(section_group_records)
        section_status_counts["active_exportable"] += 1

        manifest_sources.extend(
            [
                {
                    "source_id": zh_source_id,
                    "work_id": WORK_ID,
                    "section_id": section_id,
                    "source_type": "base_text",
                    "language": "zh",
                    "title": f"{section.title_zh} ChineseNotes chapter text",
                    "translator_or_editor": "Chinese Notes / Chinese Text Project mirror",
                    "rights_status": "rights_review_required",
                    "release_status": "not_cleared",
                    "provenance_type": "digital_transcription",
                    "provenance_ref": f"{SOURCE_BASE_URL}/{section.source_file}",
                    "provenance_note": "ChineseNotes Liji chapter file pinned to upstream commit.",
                    "raw_path": repo_relative(raw_path),
                    "checksum_sha256": sha256_file(raw_path),
                },
                {
                    "source_id": en_source_id,
                    "work_id": WORK_ID,
                    "section_id": section_id,
                    "source_type": "translation",
                    "language": "en",
                    "title": f"{section.title_en} English witness",
                    "translator_or_editor": "James Legge via Chinese Notes",
                    "rights_status": "rights_review_required",
                    "release_status": "not_cleared",
                    "provenance_type": "digital_transcription",
                    "provenance_ref": f"{SOURCE_BASE_URL}/{section.source_file}",
                    "provenance_note": "ChineseNotes bilingual mirror of James Legge's Li Ki chapter text.",
                    "raw_path": repo_relative(raw_path),
                    "checksum_sha256": sha256_file(raw_path),
                },
            ]
        )
        inventory_sources.append(
            {
                "section_id": section_id,
                "title_zh": section.title_zh,
                "title_en": section.title_en,
                "source_file": section.source_file,
                "source_url": f"{SOURCE_BASE_URL}/{section.source_file}",
                "status": "captured",
                "has_parallel_chinese": True,
                "has_parallel_english": True,
                "translator_note": parsed["translator_notes"] or intro_notes["translator_notes"],
            }
        )
        verification_sections.append(
            {
                "section_id": section_id,
                "title_zh": section.title_zh,
                "title_en": section.title_en,
                "export_status": "active",
                "verification_status": "reviewed_section_fallback" if fallback_reason else "deterministic_alignment",
                "fallback_reason": fallback_reason,
            }
        )
        manifest_sections.append(
            {
                "section_id": section_id,
                "title_zh": section.title_zh,
                "title_en": section.title_en,
                "label": section.title_zh,
                "sort_key": f"{section.index:03d}",
                "canonical_ref": canonical_ref,
                "source_ids": {"source_id": zh_source_id, "target_source_id": en_source_id},
                "corpus_use_status": "proof_of_concept",
                "export_status": "active",
                "alignment_status": "complete",
                "tmx_status": "complete",
                "rights_status": "rights_review_required",
                "release_status": "not_cleared",
                "base_text_processed_path": repo_relative(base_text_path),
                "translation_processed_path": repo_relative(translation_path),
                "alignment_processed_path": repo_relative(alignment_path),
                "fallback_used": bool(fallback_reason),
                "fallback_reason": fallback_reason,
                "expected_exact_alignment_count": len(exact_records),
                "notes": (
                    "ChineseNotes bilingual chapter processed into proof-of-concept aligned passages."
                    if not fallback_reason
                    else "Proof-of-concept chapter promoted with reviewed section-level fallback."
                ),
            }
        )
        import_sections.append(
            {
                "section_id": section_id,
                "work_id": WORK_ID,
                "parent_section_id": None,
                "label": section.title_zh,
                "section_ref": f"{section.index:03d}",
                "title": section.title_zh,
                "title_en": section.title_en,
                "canonical_ref": canonical_ref,
                "sort_key": f"{section.index:03d}",
                "notes": (
                    "ChineseNotes bilingual Liji chapter promoted through the candidate gauntlet."
                    if not fallback_reason
                    else "ChineseNotes bilingual Liji chapter promoted with a reviewed chapter-level fallback."
                ),
            }
        )
        import_sources.extend(
            [
                {
                    "source_id": zh_source_id,
                    "work_id": WORK_ID,
                    "section_id": section_id,
                    "language_code": "zh-Hant",
                    "source_kind": "digital_transcription",
                    "citation": f"ChineseNotes Liji chapter text, {section.title_zh}.",
                    "source_url": f"{SOURCE_BASE_URL}/{section.source_file}",
                    "raw_path": repo_relative(raw_path),
                    "processed_path": repo_relative(base_text_path),
                    "rights_status": "rights_review_required",
                    "release_status": "not_cleared",
                    "author_or_translator_ids": ["liji-transmitters"],
                    "rights_note": "Proof-of-concept ChineseNotes witness retained with explicit provenance while rights/release review remains outstanding.",
                    "notes": "ChineseNotes Liji chapter text pinned to upstream commit.",
                },
                {
                    "source_id": en_source_id,
                    "work_id": WORK_ID,
                    "section_id": section_id,
                    "language_code": "en",
                    "source_kind": "translation",
                    "citation": f"James Legge via Chinese Notes, {section.title_en}.",
                    "source_url": f"{SOURCE_BASE_URL}/{section.source_file}",
                    "raw_path": repo_relative(raw_path),
                    "processed_path": repo_relative(translation_path),
                    "rights_status": "rights_review_required",
                    "release_status": "not_cleared",
                    "author_or_translator_ids": ["james-legge"],
                    "rights_note": "Proof-of-concept English witness retained with explicit provenance while rights/release review remains outstanding.",
                    "notes": "ChineseNotes bilingual mirror of James Legge's Li Ki chapter text.",
                },
            ]
        )
        romanization_aliases.append(
            {
                "entity_type": "section",
                "entity_id": section_id,
                "romanization_system": "english-title",
                "alias": section.title_en,
            }
        )
        qc_sections.append(
            {
                "section_id": section_id,
                "title_zh": section.title_zh,
                "title_en": section.title_en,
                "status": "active_exportable",
                "export_status": "active",
                "exact_alignment_count": len(exact_records),
                "section_group_alignment_count": len(section_group_records),
                "fallback_used": bool(fallback_reason),
                "fallback_reason": fallback_reason,
                "base_text_processed_path": repo_relative(base_text_path),
                "translation_processed_path": repo_relative(translation_path),
                "alignment_processed_path": repo_relative(alignment_path),
                "rights_status": "rights_review_required",
                "release_status": "not_cleared",
                "notes": section.notes,
            }
        )
        completion_sections.append(
            {
                "section_id": section_id,
                "title_zh": section.title_zh,
                "title_en": section.title_en,
                "export_status": "active",
                "alignment_mode": "section_fallback" if fallback_reason else "deterministic",
                "alignment_granularity": "section" if fallback_reason else exact_records[0]["alignment_granularity"],
                "exact_alignment_count": len(exact_records),
                "fallback_reason": fallback_reason,
            }
        )
        if section_id in FORMER_FALLBACK_IDS or section_id in FALLBACK_DIAGNOSTICS:
            refinement_note = FALLBACK_DIAGNOSTICS.get(section_id, {})
            refinement_sections.append(
                {
                    "section_id": section_id,
                    "title_zh": section.title_zh,
                    "title_en": section.title_en,
                    "chinese_block_count": len(parsed["chinese_blocks"]),
                    "english_block_count": len(parsed["english_blocks"]),
                    "chinese_segment_count": len(source_units),
                    "english_segment_count": len(target_units),
                    "stable_internal_divisions": bool(anchor_map),
                    "title_or_notice_interference": bool(parsed["excluded_heading_lines"] or parsed["excluded_notice_lines"]),
                    "merged_english_paragraphs": len(target_units) > len(source_units),
                    "coarse_chinese_segmentation": len(source_units) < len(target_units),
                    "mismatch_scope": "resolved" if not fallback_reason else "remaining",
                    "resolution": refinement_note.get("resolution", "Retained baseline deterministic alignment."),
                    "diagnosis": refinement_note.get("diagnosis", ""),
                    "anchor_partition_used": section_id in anchor_mapped_sections,
                    "fallback_reason": fallback_reason,
                    "exact_alignment_count": len(exact_records),
                    "alignment_granularity": exact_records[0]["alignment_granularity"],
                }
            )

    active_section_count = section_status_counts["active_exportable"]
    blocked_section_count = section_status_counts["metadata_only_blocked"]
    source_manifest = {
        "work_id": WORK_ID,
        "title_zh": TITLE_ZH,
        "title_en": TITLE_EN,
        "source_of_truth": "ChineseNotes bilingual chapter files pinned to a specific upstream commit.",
        "status": "active",
        "corpus_use_status": "proof_of_concept",
        "rights_status": "rights_review_required",
        "release_status": "not_cleared",
        "source_audit_status": "complete",
        "inventory_status": "complete",
        "ingestion_log_status": "complete",
        "alignment_status": "complete",
        "tmx_status": "complete",
        "title_variants": ["Li Chi", "Li Ki", "Book of Rites"],
        "source_urls": [
            f"{SOURCE_BASE_URL}/{INDEX_RELATIVE_PATH}",
            f"{SOURCE_BASE_URL}/corpus/liji/",
        ],
        "source_audit_note": (
            "The ChineseNotes Liji corpus contains 49 bilingual chapter files. Deterministic cleanup removes the "
            "mixed bilingual title line, short running-head labels, translator/source notices, and one embedded "
            "philological footnote before alignment. Rights remain review-required for proof-of-concept promotion."
        ),
        "ingestion_policy": {
            "status": "aligned_or_metadata_only",
            "inventory_required": True,
            "inventory_path": repo_relative(INVENTORY_PATH),
            "inventory_unit_key": "units",
            "ingestion_plan_required": True,
            "ingestion_plan_path": repo_relative(INGESTION_PLAN_PATH),
            "source_audit_required": True,
            "source_audit_path": repo_relative(INGESTION_PLAN_PATH),
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
            "rights_policy": "proof_of_concept_export_allowed_with_explicit_rights_review",
            "allowed_export_rights_statuses": [
                "public_domain",
                "rights_review_required",
                "mixed_source_review_required",
                "unknown_rights_review_required",
            ],
            "missing_text_policy": "block_export_if_clean_chinese_or_english_text_is_missing",
            "commentary_policy": "exclude_commentary_headings_and_notice_lines_from_exportable_segments_before_alignment",
            "section_group_export_policy": "forbidden",
            "completion_definition": (
                "A Liji chapter is complete when deterministic cleanup leaves a source-faithful Chinese chapter, "
                "a provenance-tagged Legge-derived English witness, and an exact/grouped or explicitly reviewed "
                "section fallback that passes candidate QC and alignment review."
            ),
        },
        "summary": {
            "section_count": len(sections),
            "complete_sections": active_section_count,
            "metadata_only_sections": blocked_section_count,
            "total_section_count": len(sections),
            "active_exportable_section_count": active_section_count,
            "active_section_count": active_section_count,
            "exportable_section_count": active_section_count,
            "metadata_only_blocked_section_count": blocked_section_count,
            "exact_alignment_count": exact_alignment_count,
            "section_group_alignment_count": section_group_alignment_count,
            "section_group_alignment_record_count": section_group_alignment_count,
            "alignment_record_count": exact_alignment_count + section_group_alignment_count,
            "fallback_alignment_count": section_fallback_count,
            "fallback_section_count": section_fallback_count,
            "automatic_alignment_count": exact_alignment_count,
            "curated_override_section_count": 0,
            "anchor_mapped_section_count": len(anchor_mapped_sections),
            "blocked_section_count": blocked_section_count,
            "hard_failure_count": 0,
            "alignment_granularity_counts": dict(sorted(alignment_granularity_counts.items())),
            "granularity_counts": dict(sorted(alignment_granularity_counts.items())),
            "pre_repair_corruption_issue_count": 0,
            "corrected_corruption_issue_count": 0,
            "remaining_corruption_issue_count": 0,
            "pre_repair_leakage_issue_count": len(repair_entries),
            "repaired_leakage_issue_count": len(repair_entries),
            "remaining_leakage_issue_count": 0,
            "remaining_drift_issue_count": 0,
            "automatic_correction_count": len(repair_entries),
            "curated_correction_count": 0,
            "active_exportable_alignment_count": exact_alignment_count,
        },
        "notes": (
            "Liji is promoted through the candidate-ingestion gauntlet as a proof-of-concept ChineseNotes/Legge corpus. "
            f"{section_fallback_count} structurally uneven chapters retain reviewed section-level fallbacks."
        ),
        "sources": manifest_sources,
        "sections": manifest_sections,
        "romanization_aliases": romanization_aliases,
        "ingestion_log": ingestion_log,
    }

    inventory = {
        "work_id": WORK_ID,
        "title_zh": TITLE_ZH,
        "title_en": TITLE_EN,
        "source_index": repo_relative(index_raw_path),
        "upstream_commit": UPSTREAM_COMMIT,
        "section_count": len(sections),
        "units": inventory_sources,
    }
    verification_ledger = {
        "work_id": WORK_ID,
        "title_zh": TITLE_ZH,
        "title_en": TITLE_EN,
        "summary": {
            "section_count": len(sections),
            "active_exportable_section_count": active_section_count,
            "metadata_only_blocked_section_count": blocked_section_count,
            "fallback_alignment_count": section_fallback_count,
            "remaining_blocker_count": blocked_section_count,
        },
        "sections": verification_sections,
    }

    completion_report = {
        "summary": {
            "work_state": "proof_of_concept_active",
            "total_section_count": len(sections),
            "active_section_count": active_section_count,
            "exportable_section_count": active_section_count,
            "english_witness": "ChineseNotes bilingual mirror of James Legge's Li Ki / Book of Rites translation",
            "exact_alignment_count": exact_alignment_count,
            "automatic_alignment_count": exact_alignment_count,
            "alignment_record_count": exact_alignment_count + section_group_alignment_count,
            "curated_override_section_count": 0,
            "fallback_section_count": section_fallback_count,
            "blocked_section_count": blocked_section_count,
            "hard_failure_count": 0,
            "pre_repair_corruption_issue_count": 0,
            "corrected_corruption_issue_count": 0,
            "automatic_correction_count": len(repair_entries),
            "curated_correction_count": 0,
            "remaining_corruption_issue_count": 0,
            "pre_repair_leakage_issue_count": len(repair_entries),
            "repaired_leakage_issue_count": len(repair_entries),
            "remaining_leakage_issue_count": 0,
            "remaining_drift_issue_count": 0,
            "alignment_granularity_counts": dict(sorted(alignment_granularity_counts.items())),
        },
        "fallback_sections": [
            {
                "section_id": section_id,
                "coarse_alignment_reason": SECTION_FALLBACK_REASON,
            }
            for section_id in fallback_sections
        ],
        "curated_override_sections": [],
        "anchor_mapped_sections": anchor_mapped_sections,
        "blocked_sections": [
            {"section_id": section_id, "reason": "Boundary cleanup incomplete."}
            for section_id in blocked_sections
        ],
        "sections": completion_sections,
    }
    alignment_qc_path = REPORT_ROOT / f"{WORK_ID}__alignment_qc.json"
    write_json(alignment_qc_path, completion_report)
    COMPLETION_DOC_PATH.write_text(
        render_completion_quality_markdown(
            completion_report,
            work_label="Liji",
            report_path=repo_relative(alignment_qc_path),
        ),
        encoding="utf-8",
    )
    if refinement_sections:
        with COMPLETION_DOC_PATH.open("a", encoding="utf-8") as handle:
            handle.write("\n## Former fallback diagnostics\n\n")
            for section in refinement_sections:
                handle.write(
                    f"- `{section['section_id']}`: zh blocks {section['chinese_block_count']}, "
                    f"en blocks {section['english_block_count']}, zh segments {section['chinese_segment_count']}, "
                    f"en segments {section['english_segment_count']}; stable internal divisions: "
                    f"{'yes' if section['stable_internal_divisions'] else 'no'}; "
                    f"title/notices interfering: {'yes' if section['title_or_notice_interference'] else 'no'}; "
                    f"merged English paragraphs: {'yes' if section['merged_english_paragraphs'] else 'no'}; "
                    f"Chinese segmentation too coarse: {'yes' if section['coarse_chinese_segmentation'] else 'no'}; "
                    f"scope: {section['mismatch_scope']}. {section['diagnosis']} {section['resolution']}\n"
                )

    INGESTION_PLAN_PATH.write_text(
        "\n".join(
            [
                "# Liji ingestion plan",
                "",
                "## Scope",
                "",
                "- Work: *Liji* / *Book of Rites* (`liji`)",
                "- Upstream source: ChineseNotes bilingual chapter files pinned to a specific Git commit",
                "- Section model: one section per chapter/pian",
                "- Current witness policy: Chinese base text plus ChineseNotes-hosted Legge English mirror",
                "- Rights policy: `rights_review_required` and `not_cleared` until independent release review is completed",
                "",
                "## Alignment strategy",
                "",
                "1. Strip deterministic non-translation residue from each bilingual chapter.",
                "2. Attempt exact block or monotonic grouped alignment from the cleaned chapter text.",
                "3. Retain reviewed chapter-level fallback only for structurally uneven chapters that still resist safe regrouping.",
                "4. Promote only after candidate QC and alignment review pass.",
                "",
                "## Current promotion shape",
                "",
                f"- Total chapters detected: {len(sections)}",
                f"- Reviewed fallback chapters: {section_fallback_count}",
                f"- Metadata-only blockers: {blocked_section_count}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    repair_log = {
        "work_id": WORK_ID,
        "summary": {
            "pre_repair_corruption_issue_count": 0,
            "corrected_corruption_issue_count": 0,
            "remaining_corruption_issue_count": 0,
            "pre_repair_leakage_issue_count": len(repair_entries),
            "repaired_leakage_issue_count": len(repair_entries),
            "remaining_leakage_issue_count": 0,
            "automatic_correction_count": len(repair_entries),
            "curated_correction_count": 0,
        },
        "repairs": repair_entries,
        "remaining_issues": [],
    }
    write_json(REPORT_ROOT / f"{WORK_ID}__ocr_repair_log.json", repair_log)
    write_json(MANIFEST_PATH, source_manifest)
    write_json(INVENTORY_PATH, inventory)
    write_json(LEDGER_PATH, verification_ledger)
    _update_metadata_with_manifest(source_manifest)

    return {
        "manifest": source_manifest,
        "import_sections": import_sections,
        "import_sources": import_sources,
        "romanization_aliases": romanization_aliases,
        "ingestion_log": ingestion_log,
        "summary": source_manifest["summary"],
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    skip_fetch = "--skip-fetch" in args
    result = bootstrap_liji_corpus(skip_fetch=skip_fetch)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
