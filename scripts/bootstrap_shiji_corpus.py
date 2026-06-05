from __future__ import annotations

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
    refine_alignment,
    render_completion_quality_markdown,
    split_chinese_units,
    split_english_units,
)
from ingest_chinesenotes_work import _slugify_ascii
from liji_quality import parse_chinesenotes_bilingual_text

UPSTREAM_OWNER = "alexamies"
UPSTREAM_REPO = "chinesenotes.com"
UPSTREAM_COMMIT = "1f6b1d3e7a40b6886a4b943c898125639e993544"
UPSTREAM_COMMIT_SHORT = UPSTREAM_COMMIT[:7]
WORK_ID = "shiji"
TITLE_ZH = "史記"
TITLE_EN = "Records of the Grand Historian"
SOURCE_BASE_URL = f"https://raw.githubusercontent.com/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/{UPSTREAM_COMMIT}"
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
BATCH_MAPPING_PATH = METADATA_ROOT / f"{WORK_ID}_batch_mapping.yml"
INDEX_RELATIVE_PATH = "data/corpus/shiji.csv"


@dataclass
class ShijiSection:
    number: int
    source_file: str
    title_zh: str
    title_en: str
    batch_id: str

    @property
    def section_id(self) -> str:
        return f"{WORK_ID}-{self.number:03d}-{_short_slug(self.title_en, limit=44)}"

    @property
    def canonical_ref(self) -> str:
        return f"{TITLE_ZH}·{self.title_zh}"


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


def _batch_id_for_number(number: int) -> str:
    if 1 <= number <= 12:
        return "benji"
    if 13 <= number <= 22:
        return "biao"
    if 23 <= number <= 30:
        return "shu"
    if 31 <= number <= 60:
        return "shijia"
    return "liezhuan"


def _fetch_text(relative_path: str) -> str:
    with urlopen(f"{SOURCE_BASE_URL}/{relative_path}") as response:  # noqa: S310
        return response.read().decode("utf-8")


def _ensure_raw_capture(relative_path: str, *, skip_fetch: bool) -> Path:
    destination = RAW_ROOT / f"{WORK_ID}__{Path(relative_path).stem}__chinesenotes-{UPSTREAM_COMMIT_SHORT}__raw.txt"
    if destination.exists():
        return destination
    if skip_fetch:
        raise FileNotFoundError(f"Missing raw capture for {relative_path}; rerun without --skip-fetch.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(_fetch_text(relative_path), encoding="utf-8")
    return destination


def _load_index_rows(index_path: Path) -> list[ShijiSection]:
    sections: list[ShijiSection] = []
    for raw_line in index_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("\t") if part.strip()]
        if len(parts) < 3:
            continue
        source_file, _, title = parts[:3]
        if not source_file.startswith("shiji/") or source_file == "shiji/shiji000.txt":
            continue
        try:
            section_number = int(Path(source_file).stem[5:8])
        except ValueError:
            continue
        if "》" not in title:
            continue
        title_zh, title_en = title.split("》", 1)
        sections.append(
            ShijiSection(
                number=section_number,
                source_file=f"corpus/{source_file}",
                title_zh=f"{title_zh}》",
                title_en=title_en.strip(),
                batch_id=_batch_id_for_number(section_number),
            )
        )
    return sorted(sections, key=lambda section: section.number)


def _selected_numbers(batch_mapping: dict[str, Any], batch_id: str | None = None) -> set[int]:
    selected: set[int] = set()
    for batch in batch_mapping.get("batches", []):
        batch_name = str(batch.get("batch_id") or "")
        if batch_id and batch_name != batch_id:
            continue
        if batch_id or str(batch.get("status") or "") in {"active_proof_of_concept", "active_release_ready"}:
            selected.update(int(value) for value in batch.get("selected_chapter_numbers", []))
    return selected


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


def _write_block_segments(
    *,
    work_id: str,
    section_id: str,
    source_id: str,
    canonical_ref: str,
    blocks: list[str],
    language: str,
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
                language=language,
            )
        )
    return records


def _write_unit_segments(
    *,
    work_id: str,
    section_id: str,
    source_id: str,
    canonical_ref: str,
    units: list[dict[str, Any]],
    language: str,
    segment_type: str,
) -> tuple[list[dict[str, Any]], dict[int, str]]:
    records: list[dict[str, Any]] = []
    unit_map: dict[int, str] = {}
    for position, unit in enumerate(units, start=1):
        text = str(unit["text"]).strip()
        if not text:
            continue
        segment_id = f"{source_id}__seg-{position:04d}"
        records.append(
            _segment_record(
                work_id=work_id,
                section_id=section_id,
                segment_id=segment_id,
                source_id=source_id,
                text=text,
                segment_order=position,
                canonical_ref=f"{canonical_ref} {position}",
                segment_type=segment_type,
                language=language,
            )
        )
        unit_map[int(unit.get("unit_index", position - 1))] = segment_id
    return records, unit_map


def _alignment_record(
    *,
    work_id: str,
    section_id: str,
    alignment_id: str,
    source_id: str,
    target_source_id: str,
    chinese_segment_ids: list[str],
    translation_segment_ids: list[str],
    alignment_granularity: str,
    segment_type: str,
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
        "notes": "Deterministic ChineseNotes Shiji batch alignment.",
        "is_coarse_alignment": False,
        "coarse_alignment_reason": None,
        "source_segment_count": len(chinese_segment_ids),
        "target_segment_count": len(translation_segment_ids),
        "confidence": confidence,
    }


def _section_group_record(
    *,
    work_id: str,
    section_id: str,
    source_id: str,
    target_source_id: str,
    chinese_segment_ids: list[str],
    translation_segment_ids: list[str],
) -> dict[str, Any]:
    return {
        "alignment_id": f"{section_id}__section-group",
        "work_id": work_id,
        "section_id": section_id,
        "source_id": source_id,
        "target_source_id": target_source_id,
        "chinese_segment_ids": chinese_segment_ids,
        "translation_segment_ids": translation_segment_ids,
        "alignment_type": "section_group",
        "alignment_granularity": "chapter",
        "section_unit": "chapter",
        "segment_type": "section",
        "notes": "Section-group alignment retained for bookkeeping and QC.",
        "is_coarse_alignment": False,
        "coarse_alignment_reason": None,
        "source_segment_count": len(chinese_segment_ids),
        "target_segment_count": len(translation_segment_ids),
        "confidence": 1.0,
    }


def _update_metadata(
    manifest: dict[str, Any],
    *,
    batch_mapping: dict[str, Any],
) -> None:
    works_path = METADATA_ROOT / "works.yml"
    works = load_json_compatible_yaml(works_path) if works_path.exists() else []
    works_by_id = {entry["work_id"]: entry for entry in works}
    works_by_id[WORK_ID] = {
        "work_id": WORK_ID,
        "canonical_title": TITLE_ZH,
        "english_title": TITLE_EN,
        "work_type": "classical_text",
        "language_code": "zh-Hant",
        "default_citation": TITLE_ZH,
        "notes": manifest["notes"],
    }
    write_json(works_path, [works_by_id[key] for key in sorted(works_by_id)])

    persons_path = METADATA_ROOT / "persons.yml"
    persons = load_json_compatible_yaml(persons_path) if persons_path.exists() else []
    by_person = {entry["person_id"]: entry for entry in persons}
    by_person["sima-qian"] = {
        "person_id": "sima-qian",
        "display_name": "司馬遷",
        "romanized_name": "Sima Qian",
        "roles": ["compiler"],
        "notes": "Traditional compiler of the received Shiji.",
    }
    write_json(persons_path, [by_person[key] for key in sorted(by_person)])

    mapping_path = METADATA_ROOT / "chinesenotes_work_mapping.yml"
    mapping = load_json_compatible_yaml(mapping_path) if mapping_path.exists() else {"works": []}
    works_list = mapping.setdefault("works", [])
    replacement = {
        "chintransmem_work_id": WORK_ID,
        "chinesenotes_paths": ["data/corpus/shiji.csv", "corpus/shiji/"],
        "status": "already_ingested",
        "english_coverage": "pilot_partial",
        "chinese_coverage": "pilot_partial",
        "preferred_use": "aligned_passages",
        "notes": (
            f"Shiji now uses a batch-aware candidate gauntlet. The initial benji pilot stages chapters "
            f"{batch_mapping['batches'][0]['selected_chapter_numbers']} and currently promotes "
            f"{manifest['summary']['active_section_count']} active proof-of-concept sections."
        ),
    }
    replaced = False
    for index, entry in enumerate(works_list):
        if entry.get("chintransmem_work_id") == WORK_ID:
            works_list[index] = replacement
            replaced = True
            break
    if not replaced:
        works_list.append(replacement)
    works_list.sort(key=lambda entry: entry["chintransmem_work_id"])
    write_json(mapping_path, mapping)


def bootstrap_shiji_corpus(*, skip_fetch: bool = False, batch_id: str | None = None) -> dict[str, Any]:
    try:
        index_raw = _ensure_raw_capture(INDEX_RELATIVE_PATH, skip_fetch=skip_fetch)
    except (FileNotFoundError, HTTPError, URLError) as exc:
        raise RuntimeError(f"Unable to prepare Shiji index capture: {exc}") from exc

    batch_mapping = load_json_compatible_yaml(BATCH_MAPPING_PATH)
    sections = _load_index_rows(index_raw)
    selected_numbers = _selected_numbers(batch_mapping, batch_id)
    selected_sections = [section for section in sections if section.number in selected_numbers]

    manifest_sections: list[dict[str, Any]] = []
    manifest_sources: list[dict[str, Any]] = []
    romanization_aliases: list[dict[str, Any]] = [
        {"entity_type": "work", "entity_id": WORK_ID, "romanization_system": "pinyin", "alias": "Shiji"},
        {"entity_type": "work", "entity_id": WORK_ID, "romanization_system": "english-title", "alias": TITLE_EN},
    ]
    import_sections: list[dict[str, Any]] = []
    import_sources: list[dict[str, Any]] = []
    inventory_units: list[dict[str, Any]] = []
    verification_sections: list[dict[str, Any]] = []
    completion_sections: list[dict[str, Any]] = []
    alignment_granularity_counts: Counter[str] = Counter()
    exact_alignment_count = 0
    section_group_alignment_count = 0
    blocked_section_count = 0
    active_section_count = 0
    blocked_sections: list[dict[str, Any]] = []

    for section in selected_sections:
        raw_path = _ensure_raw_capture(section.source_file, skip_fetch=skip_fetch)
        parsed = parse_chinesenotes_bilingual_text(raw_path.read_text(encoding="utf-8"), f"{section.title_zh} {section.title_en}")
        section_id = section.section_id
        canonical_ref = section.canonical_ref
        zh_source_id = f"{section_id}__cn-zh-{UPSTREAM_COMMIT_SHORT}"
        en_source_id = f"{section_id}__cn-en-{UPSTREAM_COMMIT_SHORT}"
        zh_source_suffix = zh_source_id.split("__", 1)[1]
        en_source_suffix = en_source_id.split("__", 1)[1]

        zh_segments_path = BASE_TEXT_ROOT / f"{WORK_ID}__{section_id}__{zh_source_id}__segments.jsonl"
        en_segments_path = TRANSLATION_ROOT / f"{WORK_ID}__{section_id}__{en_source_id}__segments.jsonl"
        alignment_path = ALIGNMENT_ROOT / f"{WORK_ID}__{section_id}__{zh_source_suffix}__{en_source_suffix}__alignments.jsonl"

        zh_blocks = list(parsed["chinese_blocks"])
        en_blocks = list(parsed["english_blocks"])
        zh_units = [unit for block in zh_blocks for unit in split_chinese_units(block)]
        en_units = [unit for block in en_blocks for unit in split_english_units(block)]

        source_records = _write_block_segments(
            work_id=WORK_ID,
            section_id=section_id,
            source_id=zh_source_id,
            canonical_ref=canonical_ref,
            blocks=zh_blocks,
            language="zh-Hant",
        )
        write_jsonl(zh_segments_path, source_records)

        translation_records = _write_block_segments(
            work_id=WORK_ID,
            section_id=section_id,
            source_id=en_source_id,
            canonical_ref=canonical_ref,
            blocks=en_blocks,
            language="en",
        )
        write_jsonl(en_segments_path, translation_records)

        blocked_reason: str | None = None
        exact_records: list[dict[str, Any]] = []
        section_group_records: list[dict[str, Any]] = []
        if not zh_blocks or not en_blocks:
            blocked_reason = "ChineseNotes pilot witness is missing clean Chinese or English content for this chapter."
        else:
            try:
                alignment = refine_alignment(
                    section_id,
                    zh_blocks,
                    en_blocks,
                    source_splitter=split_chinese_units,
                    target_splitter=split_english_units,
                    max_source_group_size=6,
                    max_target_group_size=8,
                )
                zh_unit_records, zh_map = _write_unit_segments(
                    work_id=WORK_ID,
                    section_id=section_id,
                    source_id=zh_source_id,
                    canonical_ref=canonical_ref,
                    units=alignment["source_units"],
                    language="zh-Hant",
                    segment_type=alignment["segment_granularity"],
                )
                en_unit_records, en_map = _write_unit_segments(
                    work_id=WORK_ID,
                    section_id=section_id,
                    source_id=en_source_id,
                    canonical_ref=canonical_ref,
                    units=alignment["target_units"],
                    language="en",
                    segment_type=alignment["segment_granularity"],
                )
                write_jsonl(zh_segments_path, zh_unit_records)
                write_jsonl(en_segments_path, en_unit_records)
                for position, group in enumerate(alignment["groups"], start=1):
                    exact_records.append(
                        _alignment_record(
                            work_id=WORK_ID,
                            section_id=section_id,
                            alignment_id=f"{section_id}__aligned-{position:03d}",
                            source_id=zh_source_id,
                            target_source_id=en_source_id,
                            chinese_segment_ids=[zh_map[index] for index in group["source_unit_indices"]],
                            translation_segment_ids=[en_map[index] for index in group["target_unit_indices"]],
                            alignment_granularity=alignment["alignment_granularity"],
                            segment_type=alignment["segment_granularity"],
                            confidence=0.96 if alignment["alignment_granularity"] == "block" else 0.93,
                        )
                    )
                section_group_records = [
                    _section_group_record(
                        work_id=WORK_ID,
                        section_id=section_id,
                        source_id=zh_source_id,
                        target_source_id=en_source_id,
                        chinese_segment_ids=[record["segment_id"] for record in zh_unit_records],
                        translation_segment_ids=[record["segment_id"] for record in en_unit_records],
                    )
                ]
                write_jsonl(alignment_path, exact_records + section_group_records)
                exact_alignment_count += len(exact_records)
                section_group_alignment_count += 1
                active_section_count += 1
                alignment_granularity_counts[alignment["alignment_granularity"]] += len(exact_records)
            except ValueError as exc:
                blocked_reason = (
                    "ChineseNotes Shiji pilot witness remains too structurally uneven for safe export in this tranche: "
                    + str(exc)
                )

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
                    "provenance_note": "ChineseNotes Shiji chapter file pinned to the upstream commit.",
                    "raw_path": repo_relative(raw_path),
                    "checksum_sha256": sha256_file(raw_path),
                },
                {
                    "source_id": en_source_id,
                    "work_id": WORK_ID,
                    "section_id": section_id,
                    "source_type": "translation",
                    "language": "en",
                    "title": f"{section.title_en} ChineseNotes English witness",
                    "translator_or_editor": "Chinese Notes bilingual English witness (translator unresolved)",
                    "rights_status": "rights_review_required",
                    "release_status": "not_cleared",
                    "provenance_type": "digital_transcription",
                    "provenance_ref": f"{SOURCE_BASE_URL}/{section.source_file}",
                    "provenance_note": "ChineseNotes-hosted bilingual English witness. Translator attribution is not yet resolved from the source file and remains provisional.",
                    "raw_path": repo_relative(raw_path),
                    "checksum_sha256": sha256_file(raw_path),
                },
            ]
        )

        inventory_units.append(
            {
                "section_id": section_id,
                "section_number": section.number,
                "batch_id": section.batch_id,
                "title_zh": section.title_zh,
                "title_en": section.title_en,
                "source_file": section.source_file,
                "source_url": f"{SOURCE_BASE_URL}/{section.source_file}",
                "status": "captured",
                "english_witness": "Chinese Notes bilingual English witness",
            }
        )

        romanization_aliases.append(
            {
                "entity_type": "section",
                "entity_id": section_id,
                "romanization_system": "english-title",
                "alias": section.title_en,
            }
        )

        if blocked_reason:
            blocked_section_count += 1
            blocked_sections.append({"section_id": section_id, "reason": blocked_reason})
            verification_sections.append(
                {
                    "section_id": section_id,
                    "batch_id": section.batch_id,
                    "title_zh": section.title_zh,
                    "title_en": section.title_en,
                    "export_status": "metadata_only",
                    "blocker_note": blocked_reason,
                }
            )
            manifest_sections.append(
                {
                    "section_id": section_id,
                    "batch_id": section.batch_id,
                    "title_zh": section.title_zh,
                    "title_en": section.title_en,
                    "label": section.title_zh,
                    "sort_key": f"{section.number:03d}",
                    "canonical_ref": canonical_ref,
                    "source_ids": {"source_id": zh_source_id},
                    "corpus_use_status": "blocked",
                    "export_status": "metadata_only",
                    "alignment_status": "blocked",
                    "tmx_status": "not_ready",
                    "rights_status": "rights_review_required",
                    "release_status": "not_cleared",
                    "base_text_processed_path": repo_relative(zh_segments_path),
                    "translation_processed_path": repo_relative(en_segments_path),
                    "alignment_processed_path": None,
                    "fallback_used": False,
                    "fallback_reason": blocked_reason,
                    "expected_exact_alignment_count": 0,
                    "notes": "Retained as metadata-only until a more reliable Shiji English witness or safer segmentation path is available.",
                }
            )
        else:
            verification_sections.append(
                {
                    "section_id": section_id,
                    "batch_id": section.batch_id,
                    "title_zh": section.title_zh,
                    "title_en": section.title_en,
                    "export_status": "active",
                    "verification_status": "deterministic_alignment",
                }
            )
            manifest_sections.append(
                {
                    "section_id": section_id,
                    "batch_id": section.batch_id,
                    "title_zh": section.title_zh,
                    "title_en": section.title_en,
                    "label": section.title_zh,
                    "sort_key": f"{section.number:03d}",
                    "canonical_ref": canonical_ref,
                    "source_ids": {"source_id": zh_source_id, "target_source_id": en_source_id},
                    "corpus_use_status": "proof_of_concept",
                    "export_status": "active",
                    "alignment_status": "complete",
                    "tmx_status": "complete",
                    "rights_status": "rights_review_required",
                    "release_status": "not_cleared",
                    "base_text_processed_path": repo_relative(zh_segments_path),
                    "translation_processed_path": repo_relative(en_segments_path),
                    "alignment_processed_path": repo_relative(alignment_path),
                    "fallback_used": False,
                    "fallback_reason": None,
                    "expected_exact_alignment_count": len(exact_records),
                    "notes": "Batch-scoped Shiji proof-of-concept export from the benji pilot tranche.",
                }
            )
            completion_sections.append(
                {
                    "section_id": section_id,
                    "title_zh": section.title_zh,
                    "title_en": section.title_en,
                    "export_status": "active",
                    "alignment_mode": "deterministic",
                    "alignment_granularity": exact_records[0]["alignment_granularity"] if exact_records else "block",
                    "exact_alignment_count": len(exact_records),
                    "fallback_reason": None,
                }
            )

        import_sections.append(
            {
                "section_id": section_id,
                "work_id": WORK_ID,
                "parent_section_id": None,
                "label": section.title_zh,
                "canonical_ref": canonical_ref,
                "sort_key": f"{section.number:03d}",
                "notes": "Shiji batch-scoped section metadata.",
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
                    "citation": f"ChineseNotes Shiji chapter text, {section.title_zh}.",
                    "source_url": f"{SOURCE_BASE_URL}/{section.source_file}",
                    "raw_path": repo_relative(raw_path),
                    "processed_path": repo_relative(zh_segments_path),
                    "rights_status": "rights_review_required",
                    "release_status": "not_cleared",
                    "author_or_translator_ids": ["sima-qian"],
                    "rights_note": "Proof-of-concept Shiji Chinese witness retained with explicit provenance while release review remains outstanding.",
                    "notes": "ChineseNotes Shiji chapter text pinned to the upstream commit.",
                },
                {
                    "source_id": en_source_id,
                    "work_id": WORK_ID,
                    "section_id": section_id,
                    "language_code": "en",
                    "source_kind": "translation",
                    "citation": f"ChineseNotes bilingual Shiji English witness, {section.title_en}.",
                    "source_url": f"{SOURCE_BASE_URL}/{section.source_file}",
                    "raw_path": repo_relative(raw_path),
                    "processed_path": repo_relative(en_segments_path),
                    "rights_status": "rights_review_required",
                    "release_status": "not_cleared",
                    "author_or_translator_ids": [],
                    "rights_note": "Proof-of-concept English witness retained with explicit provenance while translator attribution and release review remain unresolved.",
                    "notes": "ChineseNotes-hosted bilingual English witness for the Shiji pilot tranche.",
                },
            ]
        )

    batch_summary = {
        "work_id": WORK_ID,
        "title_zh": TITLE_ZH,
        "title_en": TITLE_EN,
        "section_count": len(selected_sections),
        "complete_sections": active_section_count,
        "metadata_only_sections": blocked_section_count,
        "total_section_count": len(selected_sections),
        "active_exportable_section_count": active_section_count,
        "active_section_count": active_section_count,
        "exportable_section_count": active_section_count,
        "metadata_only_blocked_section_count": blocked_section_count,
        "exact_alignment_count": exact_alignment_count,
        "section_group_alignment_count": section_group_alignment_count,
        "section_group_alignment_record_count": section_group_alignment_count,
        "alignment_record_count": exact_alignment_count + section_group_alignment_count,
        "fallback_alignment_count": 0,
        "fallback_section_count": 0,
        "automatic_alignment_count": exact_alignment_count,
        "curated_override_section_count": 0,
        "blocked_section_count": blocked_section_count,
        "hard_failure_count": 0,
        "alignment_granularity_counts": dict(sorted(alignment_granularity_counts.items())),
        "pre_repair_corruption_issue_count": 0,
        "corrected_corruption_issue_count": 0,
        "remaining_corruption_issue_count": 0,
        "pre_repair_leakage_issue_count": 0,
        "repaired_leakage_issue_count": 0,
        "remaining_leakage_issue_count": 0,
        "remaining_drift_issue_count": 0,
        "automatic_correction_count": 0,
        "curated_correction_count": 0,
        "active_exportable_alignment_count": exact_alignment_count,
    }

    manifest = {
        "work_id": WORK_ID,
        "title_zh": TITLE_ZH,
        "title_en": TITLE_EN,
        "source_of_truth": "ChineseNotes chapter files staged through a batch-aware gauntlet.",
        "status": "active",
        "corpus_use_status": "proof_of_concept",
        "rights_status": "rights_review_required",
        "release_status": "not_cleared",
        "source_audit_status": "complete",
        "inventory_status": "complete",
        "ingestion_log_status": "complete",
        "alignment_status": "complete",
        "tmx_status": "complete",
        "title_variants": ["Shiji", "Records of the Grand Historian"],
        "source_urls": [f"{SOURCE_BASE_URL}/{INDEX_RELATIVE_PATH}", f"{SOURCE_BASE_URL}/corpus/shiji/"],
        "source_audit_note": "Shiji is staged by batch. The initial benji pilot uses only the first three annals because later annals in the first division lack stable bilingual paragraph structure in the current ChineseNotes witness.",
        "ingestion_policy": {
            "status": "aligned_or_metadata_only",
            "inventory_required": True,
            "inventory_path": repo_relative(INVENTORY_PATH),
            "inventory_unit_key": "units",
            "ingestion_plan_required": True,
            "ingestion_plan_path": "documentation/shiji_ingestion_plan.md",
            "source_audit_required": True,
            "source_audit_path": "documentation/shiji_ingestion_plan.md",
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
            "allowed_export_rights_statuses": ["public_domain", "rights_review_required", "mixed_source_review_required", "unknown_rights_review_required"],
            "missing_text_policy": "block_export_if_clean_chinese_or_english_text_is_missing",
            "commentary_policy": "exclude_commentary_headings_and_notice_lines_from_exportable_segments_before_alignment",
            "section_group_export_policy": "forbidden",
            "completion_definition": "A Shiji batch section is complete when a provenance-tagged ChineseNotes chapter file yields clean Chinese and attributable provisional English text, deterministic alignment passes the candidate gauntlet, and any structurally unsafe section is left metadata-only.",
        },
        "summary": batch_summary,
        "notes": f"Shiji remains batch-scoped. This committed proof-of-concept state covers the initial benji pilot tranche with {active_section_count} active sections and {blocked_section_count} metadata-only blockers.",
        "sources": manifest_sources,
        "sections": manifest_sections,
        "romanization_aliases": romanization_aliases,
        "ingestion_log": [
            {
                "run_id": f"{WORK_ID}-bootstrap-{batch_id or 'active'}-{UPSTREAM_COMMIT_SHORT}",
                "work_id": WORK_ID,
                "stage": "bootstrap",
                "status": "completed",
                "notes": f"Generated the Shiji {batch_id or 'active'} pilot manifest from ChineseNotes chapter files.",
            }
        ],
    }

    inventory = {
        "work_id": WORK_ID,
        "title_zh": TITLE_ZH,
        "title_en": TITLE_EN,
        "source_index": repo_relative(index_raw),
        "upstream_commit": UPSTREAM_COMMIT,
        "section_count": len(selected_sections),
        "units": inventory_units,
    }
    verification_ledger = {
        "work_id": WORK_ID,
        "title_zh": TITLE_ZH,
        "title_en": TITLE_EN,
        "summary": {
            "section_count": len(selected_sections),
            "active_exportable_section_count": active_section_count,
            "metadata_only_blocked_section_count": blocked_section_count,
        },
        "sections": verification_sections,
    }

    write_json(MANIFEST_PATH, manifest)
    write_json(INVENTORY_PATH, inventory)
    write_json(LEDGER_PATH, verification_ledger)
    _update_metadata(manifest, batch_mapping=batch_mapping)

    completion_report = {
        "summary": {
            "work_state": "proof_of_concept_active",
            "total_section_count": len(selected_sections),
            "active_section_count": active_section_count,
            "exportable_section_count": active_section_count,
            "english_witness": "ChineseNotes-hosted bilingual English witness (translator attribution unresolved)",
            "exact_alignment_count": exact_alignment_count,
            "automatic_alignment_count": exact_alignment_count,
            "alignment_record_count": exact_alignment_count + section_group_alignment_count,
            "curated_override_section_count": 0,
            "fallback_section_count": 0,
            "blocked_section_count": blocked_section_count,
            "hard_failure_count": 0,
            "pre_repair_corruption_issue_count": 0,
            "corrected_corruption_issue_count": 0,
            "automatic_correction_count": 0,
            "curated_correction_count": 0,
            "remaining_corruption_issue_count": 0,
            "pre_repair_leakage_issue_count": 0,
            "repaired_leakage_issue_count": 0,
            "remaining_leakage_issue_count": 0,
            "remaining_drift_issue_count": 0,
            "alignment_granularity_counts": dict(sorted(alignment_granularity_counts.items())),
        },
        "fallback_sections": [],
        "curated_override_sections": [],
        "anchor_mapped_sections": [],
        "blocked_sections": blocked_sections,
        "sections": completion_sections,
    }
    alignment_qc_path = REPORT_ROOT / f"{WORK_ID}__alignment_qc.json"
    write_json(alignment_qc_path, completion_report)
    COMPLETION_DOC_PATH.write_text(
        render_completion_quality_markdown(
            completion_report,
            work_label="Shiji",
            report_path=repo_relative(alignment_qc_path),
        ),
        encoding="utf-8",
    )

    return {
        "manifest": manifest,
        "import_sections": import_sections,
        "import_sources": import_sources,
        "romanization_aliases": romanization_aliases,
        "ingestion_log": list(manifest["ingestion_log"]),
        "summary": batch_summary,
    }


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    skip_fetch = "--skip-fetch" in args
    batch_id = None
    for index, value in enumerate(args):
        if value == "--batch-id" and index + 1 < len(args):
            batch_id = args[index + 1]
            break
    result = bootstrap_shiji_corpus(skip_fetch=skip_fetch, batch_id=batch_id)
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
