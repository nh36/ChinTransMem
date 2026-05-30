from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import (
    corpus_export_paths,
    inventory_units,
    load_sources,
    load_work_inventory,
    load_work_manifest,
    manifest_ingestion_policy,
    read_jsonl,
    section_export_paths,
    work_granularity_report_path,
    write_json,
)
from import_corpus import alignment_path_for_section
from shijing_quality import build_shijing_quality_context, detect_quality_markers


def load_export_rows(work_id: str) -> list[dict[str, Any]]:
    export_path = corpus_export_paths(work_id)["jsonl"]
    if not export_path.exists():
        return []
    return read_jsonl(export_path)


def build_segment_section_map(source_records: list[dict[str, Any]]) -> dict[str, str]:
    segment_map: dict[str, str] = {}
    for source in source_records:
        processed_path = source.get("processed_path")
        if not processed_path:
            continue
        path = Path(processed_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent.parent / path
        if not path.exists():
            continue
        for row in read_jsonl(path):
            segment_map[row["segment_id"]] = row["section_id"]
    return segment_map


def granularity_index(policy: dict[str, Any], value: str) -> int:
    return policy["granularity_order"].index(value)


def is_single_block_poem(row: dict[str, Any]) -> bool:
    return "\n\n" not in row["chinese_text"] and "\n\n" not in row["translation_text"]


def validate_work_alignment_granularity(work_id: str, output_path: Path | None = None) -> dict[str, Any]:
    manifest = load_work_manifest(work_id)
    policy = manifest_ingestion_policy(work_id, manifest)
    inventory = load_work_inventory(work_id, manifest) if policy["inventory_required"] else {"units": []}
    units = inventory_units(inventory, work_id, manifest) if policy["inventory_required"] else []
    export_rows = load_export_rows(work_id)
    export_rows_by_section: dict[str, list[dict[str, Any]]] = {}
    for row in export_rows:
        export_rows_by_section.setdefault(row["section_id"], []).append(row)

    source_records = load_sources(work_id)
    source_map = {source["source_id"]: source for source in source_records}
    segment_section_map = build_segment_section_map(source_records)
    errors: list[str] = []
    warnings: list[str] = []
    section_group_ids: set[str] = set()

    manifest_section_ids = {section["section_id"] for section in manifest["sections"]}
    inventory_section_ids = {unit["section_id"] for unit in units}
    if policy["inventory_required"] and manifest_section_ids != inventory_section_ids:
        errors.append(f"{work_id}: manifest and inventory section IDs disagree.")

    max_scope_index = granularity_index(policy, policy["maximum_exact_alignment_scope"])
    coarse_units = set(policy["coarse_alignment_units"])

    for row in export_rows:
        if row["section_unit"] != policy["section_unit"]:
            errors.append(
                f"{work_id}: alignment {row['alignment_id']} uses section_unit {row['section_unit']} instead of {policy['section_unit']}."
            )
        if row["segment_type"] not in policy["allowed_segment_units"]:
            errors.append(f"{work_id}: alignment {row['alignment_id']} has invalid segment_type {row['segment_type']}.")
        if row["alignment_granularity"] not in policy["allowed_segment_units"]:
            errors.append(
                f"{work_id}: alignment {row['alignment_id']} has invalid alignment_granularity {row['alignment_granularity']}."
            )
            continue
        if granularity_index(policy, row["alignment_granularity"]) > max_scope_index:
            errors.append(
                f"{work_id}: alignment {row['alignment_id']} exceeds maximum scope {policy['maximum_exact_alignment_scope']}."
            )
        if row.get("is_coarse_alignment") and not row.get("coarse_alignment_reason"):
            errors.append(f"{work_id}: coarse alignment {row['alignment_id']} is missing coarse_alignment_reason.")
        if row.get("is_coarse_alignment") and row["alignment_granularity"] not in coarse_units:
            errors.append(
                f"{work_id}: alignment {row['alignment_id']} is marked coarse at unsupported granularity {row['alignment_granularity']}."
            )
        if row["alignment_granularity"] in coarse_units and not row.get("is_coarse_alignment") and not is_single_block_poem(row):
            errors.append(
                f"{work_id}: alignment {row['alignment_id']} uses coarse granularity {row['alignment_granularity']} without a coarse flag."
            )

    all_tmx_text = corpus_export_paths(work_id)["tmx"].read_text(encoding="utf-8")

    for section in manifest["sections"]:
        section_id = section["section_id"]
        section_rows = export_rows_by_section.get(section_id, [])
        section_paths = section_export_paths(section_id, work_id)
        is_complete = section.get("tmx_status") == "complete"

        if is_complete:
            if not section_rows:
                errors.append(f"{work_id}: complete section {section_id} has no exportable exact alignments.")
            expected = section.get("expected_exact_alignment_count")
            if expected is not None and expected != len(section_rows):
                errors.append(
                    f"{work_id}: complete section {section_id} expected {expected} exact alignments but exports {len(section_rows)}."
                )
            for path in section_paths.values():
                if not path.exists():
                    errors.append(f"{work_id}: complete section {section_id} is missing export {path}.")
            source_ids = section.get("source_ids") or {}
            for key in ("source_id", "target_source_id"):
                if source_ids.get(key) not in source_map:
                    errors.append(f"{work_id}: complete section {section_id} references missing source {source_ids.get(key)}.")

            alignment_path = alignment_path_for_section(section)
            if not alignment_path.exists():
                errors.append(f"{work_id}: complete section {section_id} is missing processed alignments.")
                continue
            for alignment in read_jsonl(alignment_path):
                alignment_id = alignment["alignment_id"]
                if alignment["alignment_type"] == "section_group":
                    section_group_ids.add(alignment_id)
                    continue
                referenced_sections = set()
                missing_segment_ids: list[str] = []
                for segment_id in alignment.get("chinese_segment_ids", []) + alignment.get("translation_segment_ids", []):
                    section_ref = segment_section_map.get(segment_id)
                    if section_ref is None:
                        missing_segment_ids.append(segment_id)
                        continue
                    referenced_sections.add(section_ref)
                if missing_segment_ids:
                    errors.append(f"{work_id}: alignment {alignment_id} references missing segments {missing_segment_ids}.")
                if referenced_sections != {section_id}:
                    errors.append(
                        f"{work_id}: alignment {alignment_id} crosses section boundaries {sorted(referenced_sections)}."
                    )
        else:
            leaked = [path for path in section_paths.values() if path.exists()]
            if leaked or section_rows:
                errors.append(f"{work_id}: metadata-only section {section_id} leaked export artifacts.")

    leaked_section_group_ids = sorted(alignment_id for alignment_id in section_group_ids if alignment_id in all_tmx_text)
    if leaked_section_group_ids:
        errors.append(f"{work_id}: section_group alignments leaked into TMX: {leaked_section_group_ids}.")

    if work_id == "shijing":
        quality_context = build_shijing_quality_context(manifest=manifest, export_rows=export_rows)
        for section in quality_context["sections"]:
            if section["is_single_poem_alignment"] and section["english_word_count"] >= quality_context["thresholds"]["english_word_long_threshold"]:
                warnings.append(
                    f"{work_id}: complete section {section['section_id']} has a single poem-level exact alignment with unusually long English text."
                )
            if section["possible_stanza_split"]:
                warnings.append(
                    f"{work_id}: complete section {section['section_id']} may support stanza-level splitting but currently exports one poem-level alignment."
                )
            if section["possible_commentary_leakage_markers"]:
                warnings.append(
                    f"{work_id}: complete section {section['section_id']} shows possible commentary/page-furniture markers {section['possible_commentary_leakage_markers']}."
                )
        for row in export_rows:
            row_markers = detect_quality_markers(row["translation_text"])
            if row_markers:
                warnings.append(
                    f"{work_id}: export row {row['alignment_id']} shows possible heading/commentary markers {row_markers}."
                )

    report = {
        "work_id": work_id,
        "section_count": len(manifest["sections"]),
        "complete_sections": sum(1 for section in manifest["sections"] if section.get("tmx_status") == "complete"),
        "exact_alignment_count": len(export_rows),
        "warning_count": len(warnings),
        "warnings": warnings,
        "error_count": len(errors),
        "errors": errors,
    }
    write_json(output_path or work_granularity_report_path(work_id), report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate work-specific alignment granularity and export scope.")
    parser.add_argument("--work-id", required=True, help="Work identifier to validate.")
    parser.add_argument("--db-path", help="Retained for CLI compatibility; not used by the file-based validator.")
    args = parser.parse_args()
    del args.db_path

    report = validate_work_alignment_granularity(args.work_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
