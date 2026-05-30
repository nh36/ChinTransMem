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
    work_coverage_paths,
    write_json,
)
from shijing_quality import build_shijing_quality_context


def count_export_rows(work_id: str) -> tuple[int, dict[str, int], set[str]]:
    export_path = corpus_export_paths(work_id)["jsonl"]
    if not export_path.exists():
        return 0, {}, set()
    rows = read_jsonl(export_path)
    per_section: dict[str, int] = {}
    coarse_sections: set[str] = set()
    for row in rows:
        section_id = row["section_id"]
        per_section[section_id] = per_section.get(section_id, 0) + 1
        if row.get("is_coarse_alignment") or row.get("alignment_granularity") != row.get("segment_type"):
            coarse_sections.add(section_id)
    return len(rows), per_section, coarse_sections


def unit_has_chinese_source(unit: dict[str, Any]) -> bool:
    if unit.get("text_status") in {"lost_text", "title_only_missing_text"}:
        return False
    if unit.get("coverage_status") == "title_only_lost_text":
        return False
    if unit.get("status") == "missing_chinese_source":
        return False
    return bool(unit.get("zh_page_url") or unit.get("text_status") == "extant" or unit.get("status"))


def unit_has_public_domain_english_witness(unit: dict[str, Any]) -> bool:
    if unit.get("text_status") in {"lost_text", "title_only_missing_text"}:
        return False
    if unit.get("coverage_status") == "title_only_lost_text":
        return False
    english_status = str(unit.get("english_witness_status", ""))
    if english_status in {"missing", "unverified_or_missing"}:
        return False
    return bool(
        english_status
        or unit.get("en_page_url")
        or unit.get("candidate_en_page_url")
        or unit.get("candidate_en_text_url")
        or unit.get("candidate_en_ocr_url")
    )


def unit_has_verified_english_witness(unit: dict[str, Any]) -> bool:
    english_status = str(unit.get("english_witness_status", ""))
    return english_status in {"verified_transcribed_text", "sbe_transcluded_verified", "human_reviewed_ocr"}


def write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    lines = [
        f"# {report['work_id']} coverage audit",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
    ]
    for key in (
        "total_canonical_units",
        "manifest_section_count",
        "complete_sections",
        "metadata_only_sections",
        "units_with_chinese_source",
        "units_with_english_public_domain_witness",
        "units_with_verified_public_domain_english_source",
        "units_with_at_least_one_exact_alignment",
        "exact_alignment_count",
    ):
        lines.append(f"| {key} | {report[key]} |")
    lines.extend(
        [
            "",
            "## Exceptions",
            "",
            f"- Missing from manifest: {len(report['missing_from_manifest'])}",
            f"- Present but metadata-only: {len(report['present_but_metadata_only'])}",
            f"- Present without verified public-domain translation: {len(report['present_without_verified_public_domain_translation'])}",
            f"- Present with coarse or non-preferred exact alignment: {len(report['sections_with_coarse_or_nonpreferred_alignment'])}",
        ]
    )
    if report["work_id"] == "shijing":
        lines.extend(
            [
                "",
                "## Shijing quality signals",
                "",
                "| Metric | Count |",
                "| --- | ---: |",
                f"| ocr_or_fulltext_derived_sections | {len(report['ocr_or_fulltext_derived_sections'])} |",
                f"| sections_needing_human_text_review | {len(report['sections_needing_human_text_review'])} |",
                f"| sections_with_coarse_alignment | {len(report['sections_with_coarse_alignment'])} |",
                f"| sections_with_single_poem_alignment | {len(report['sections_with_single_poem_alignment'])} |",
                f"| sections_with_extreme_length_ratio | {len(report['sections_with_extreme_length_ratio'])} |",
                f"| sections_with_possible_commentary_leakage | {len(report['sections_with_possible_commentary_leakage'])} |",
                "",
                "### Witness mix",
                "",
                "| Witness type | Complete sections |",
                "| --- | ---: |",
            ]
        )
        for witness_type, count in sorted(report["complete_sections_by_witness_type"].items()):
            lines.append(f"| {witness_type} | {count} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def audit_work_coverage(
    work_id: str,
    json_output_path: Path | None = None,
    markdown_output_path: Path | None = None,
) -> dict[str, Any]:
    manifest = load_work_manifest(work_id)
    policy = manifest_ingestion_policy(work_id, manifest)
    inventory = load_work_inventory(work_id, manifest) if policy["inventory_required"] else {"units": []}
    units = inventory_units(inventory, work_id, manifest) if policy["inventory_required"] else []

    manifest_sections = {section["section_id"]: section for section in manifest["sections"]}
    inventory_sections = {unit["section_id"]: unit for unit in units}
    exact_alignment_count, exact_alignment_counts, coarse_sections = count_export_rows(work_id)
    source_records = load_sources(work_id)

    report = {
        "work_id": work_id,
        "total_canonical_units": len(units),
        "manifest_section_count": len(manifest["sections"]),
        "complete_sections": sum(1 for section in manifest["sections"] if section.get("tmx_status") == "complete"),
        "metadata_only_sections": sum(1 for section in manifest["sections"] if section.get("tmx_status") != "complete"),
        "units_with_chinese_source": sum(1 for unit in units if unit_has_chinese_source(unit)),
        "units_with_english_public_domain_witness": sum(1 for unit in units if unit_has_public_domain_english_witness(unit)),
        "units_with_verified_public_domain_english_source": sum(1 for unit in units if unit_has_verified_english_witness(unit)),
        "units_with_at_least_one_exact_alignment": sum(1 for section_id in inventory_sections if exact_alignment_counts.get(section_id, 0) > 0),
        "exact_alignment_count": exact_alignment_count,
        "source_record_count": len(source_records),
        "missing_from_manifest": sorted(inventory_sections.keys() - manifest_sections.keys()),
        "present_but_metadata_only": sorted(
            section_id
            for section_id, section in manifest_sections.items()
            if section.get("tmx_status") != "complete"
        ),
        "present_without_verified_public_domain_translation": sorted(
            section_id
            for section_id, unit in inventory_sections.items()
            if not unit_has_verified_english_witness(unit)
        ),
        "sections_with_coarse_or_nonpreferred_alignment": sorted(coarse_sections),
    }
    if work_id == "shijing":
        quality_context = build_shijing_quality_context(manifest=manifest)
        report.update(
            {
                "complete_sections_by_witness_type": quality_context["summary"]["complete_sections_by_witness_type"],
                "ocr_or_fulltext_derived_sections": sorted(
                    section["section_id"] for section in quality_context["sections"] if section["ocr_or_fulltext_derived"]
                ),
                "sections_needing_human_text_review": sorted(
                    section["section_id"]
                    for section in quality_context["sections"]
                    if section["complete_but_needs_human_text_review"]
                ),
                "sections_with_coarse_alignment": sorted(
                    section["section_id"] for section in quality_context["sections"] if section["has_coarse_alignment"]
                ),
                "sections_with_single_poem_alignment": sorted(
                    section["section_id"] for section in quality_context["sections"] if section["is_single_poem_alignment"]
                ),
                "sections_with_extreme_length_ratio": sorted(
                    section["section_id"]
                    for section in quality_context["sections"]
                    if section["suspiciously_extreme_length_ratio"]
                ),
                "sections_with_possible_commentary_leakage": sorted(
                    section["section_id"]
                    for section in quality_context["sections"]
                    if section["possible_commentary_leakage_markers"]
                ),
            }
        )

    paths = work_coverage_paths(work_id)
    json_path = json_output_path or paths["json"]
    markdown_path = markdown_output_path or paths["markdown"]
    write_json(json_path, report)
    write_markdown_report(markdown_path, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit canonical coverage for a work manifest.")
    parser.add_argument("--work-id", required=True, help="Work identifier to audit.")
    args = parser.parse_args()
    report = audit_work_coverage(args.work_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["missing_from_manifest"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
