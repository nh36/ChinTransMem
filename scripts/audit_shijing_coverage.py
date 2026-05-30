from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import (
    REPO_ROOT,
    corpus_export_paths,
    load_json_compatible_yaml,
    load_work_manifest,
    section_export_paths,
    write_json,
)
from import_corpus import alignment_path_for_section

INVENTORY_PATH = REPO_ROOT / "metadata" / "shijing_poem_inventory.yml"
MARKDOWN_OUTPUT = REPO_ROOT / "documentation" / "shijing_coverage_audit.md"
JSON_OUTPUT = REPO_ROOT / "logs" / "qc_reports" / "shijing__coverage_audit.json"
WORK_ID = "shijing"


def _load_complete_section_export(section_id: str) -> list[dict[str, Any]]:
    jsonl_path = section_export_paths(section_id, WORK_ID)["jsonl"]
    if not jsonl_path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def audit_shijing_coverage(
    json_output: Path | str = JSON_OUTPUT,
    markdown_output: Path | str = MARKDOWN_OUTPUT,
) -> dict[str, Any]:
    inventory_payload = load_json_compatible_yaml(INVENTORY_PATH)
    inventory = inventory_payload["poems"]
    manifest = load_work_manifest(WORK_ID)
    sources = load_json_compatible_yaml(REPO_ROOT / "metadata" / "sources.yml")
    shijing_sources = [source for source in sources if source["work_id"] == WORK_ID]
    manifest_sections = manifest["sections"]
    inventory_map = {item["section_id"]: item for item in inventory}
    manifest_map = {section["section_id"]: section for section in manifest_sections}
    source_map: dict[str, list[dict[str, Any]]] = {}
    for source in shijing_sources:
        source_map.setdefault(source["section_id"], []).append(source)

    metadata_only_sections: list[dict[str, Any]] = []
    coarse_complete_sections: list[dict[str, Any]] = []
    missing_public_domain_translation: list[dict[str, Any]] = []
    missing_from_repo: list[dict[str, Any]] = []
    complete_sections_with_files = 0
    exact_alignment_sections = 0
    english_witness_sections = 0
    verified_english_sections = 0
    chinese_source_sections = 0

    for item in inventory:
        section_id = item["section_id"]
        manifest_section = manifest_map.get(section_id)
        if manifest_section is None:
            missing_from_repo.append(item)
            continue
        if item["status"] != "missing_chinese_source":
            chinese_source_sections += 1
        if item.get("en_page_url") or item.get("candidate_en_page_url"):
            english_witness_sections += 1
        if item.get("english_witness_status") == "verified_transcribed_text":
            verified_english_sections += 1
        if manifest_section.get("status") == "missing_public_domain_translation":
            missing_public_domain_translation.append(
                {"section_id": section_id, "label": manifest_section["label"]}
            )
        if manifest_section.get("status") != "complete":
            metadata_only_sections.append(
                {
                    "section_id": section_id,
                    "label": manifest_section["label"],
                    "status": manifest_section.get("status"),
                    "coverage_status": manifest_section.get("coverage_status"),
                }
            )
            continue

        section_sources = source_map.get(section_id, [])
        has_source_files = (
            len(section_sources) == 2
            and all((REPO_ROOT / source["raw_path"]).exists() for source in section_sources)
            and all((REPO_ROOT / source["processed_path"]).exists() for source in section_sources)
        )
        has_alignment_file = alignment_path_for_section(manifest_section).exists()
        export_paths = section_export_paths(section_id, WORK_ID)
        has_export_files = all(
            export_paths[key].exists() for key in ("jsonl", "csv", "tmx")
        )
        if has_source_files and has_alignment_file and has_export_files:
            complete_sections_with_files += 1
        if manifest_section.get("expected_exact_alignment_count", 0) > 0:
            exact_alignment_sections += 1
        export_rows = _load_complete_section_export(section_id)
        if any(row.get("is_coarse_alignment") for row in export_rows):
            coarse_complete_sections.append(
                {
                    "section_id": section_id,
                    "label": manifest_section["label"],
                    "exact_alignment_count": manifest_section.get("expected_exact_alignment_count", 0),
                }
            )

    report = {
        "status": "pass" if not missing_from_repo else "fail",
        "work_id": WORK_ID,
        "inventory_summary": inventory_payload["count_basis"],
        "manifest_summary": manifest["summary"],
        "total_canonical_poems": len(inventory),
        "poems_represented_as_sections": len(manifest_sections),
        "poems_with_chinese_source": chinese_source_sections,
        "poems_with_english_public_domain_witness": english_witness_sections,
        "poems_with_verified_public_domain_english_source": verified_english_sections,
        "poems_with_at_least_one_exact_alignment": exact_alignment_sections,
        "complete_sections_with_all_repo_files": complete_sections_with_files,
        "missing_from_repo": missing_from_repo,
        "metadata_only_sections": metadata_only_sections,
        "missing_public_domain_translation": missing_public_domain_translation,
        "coarse_or_unusual_complete_sections": coarse_complete_sections,
        "corpus_export_paths": {key: str(value) for key, value in corpus_export_paths(WORK_ID).items()},
    }
    write_json(json_output, report)
    markdown = "\n".join(
        [
            "# Shijing coverage audit",
            "",
            f"- Canonical index entries: {report['total_canonical_poems']}",
            f"- Manifest sections: {report['poems_represented_as_sections']}",
            f"- Chinese extant/sourceable entries: {report['poems_with_chinese_source']}",
            (
                "- Public-domain English witnesses: "
                f"{report['poems_with_english_public_domain_witness']} "
                f"({report['poems_with_verified_public_domain_english_source']} verified transcribed, "
                f"{report['poems_with_english_public_domain_witness'] - report['poems_with_verified_public_domain_english_source']} still awaiting section-level extraction)"
            ),
            f"- Sections with at least one exact alignment: {report['poems_with_at_least_one_exact_alignment']}",
            f"- Metadata-only sections: {len(metadata_only_sections)}",
            f"- Title-only missing-text entries: {manifest['summary'].get('missing_chinese_source_sections', 0)}",
            f"- Coarse complete sections: {len(coarse_complete_sections)}",
            "",
            "## Coverage status",
            "",
            (
                "The Shijing manifest is canonically complete at the poem level. "
                "Only sections with verified public-domain English text stay TMX-exportable; "
                "the remaining extant poems are represented as `needs_alignment` metadata-only sections with "
                "a full public-domain English witness recorded and OCR fallback preserved."
            ),
        ]
    )
    Path(markdown_output).write_text(f"{markdown}\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit canonical Shijing coverage against the manifest and exports.")
    parser.add_argument("--json-output", default=str(JSON_OUTPUT), help="Where to write the JSON audit report.")
    parser.add_argument(
        "--markdown-output",
        default=str(MARKDOWN_OUTPUT),
        help="Where to write the Markdown audit report.",
    )
    args = parser.parse_args()
    report = audit_shijing_coverage(args.json_output, args.markdown_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
