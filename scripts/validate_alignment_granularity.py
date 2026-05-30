from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET

from common import DEFAULT_DB_PATH, REPO_ROOT, connect_db, corpus_export_paths, load_work_manifest, manifest_sections, write_json
from export_corpus import load_exact_alignment_rows

XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"
DEFAULT_REPORT_OUTPUT = REPO_ROOT / "logs" / "qc_reports" / "shijing__granularity_qc.json"


def validate_alignment_granularity(
    db_path: Path | str = DEFAULT_DB_PATH,
    report_output: Path | str = DEFAULT_REPORT_OUTPUT,
    *,
    work_id: str = "shijing",
) -> dict[str, Any]:
    manifest = load_work_manifest(work_id)
    sections = manifest["sections"]
    complete_sections = [section for section in sections if section.get("tmx_status", "complete") == "complete"]
    exact_rows = load_exact_alignment_rows(db_path, work_id)
    exact_row_map: dict[str, list[dict[str, Any]]] = {}
    for row in exact_rows:
        exact_row_map.setdefault(row["section_id"], []).append(row)

    failures: list[str] = []
    notes: list[str] = []
    stanza_exact_alignment_count = 0
    poem_exact_alignment_count = 0
    coarse_alignment_count = 0

    if manifest["summary"]["section_count"] != len(sections):
        failures.append("Manifest summary section_count does not match the section list length.")

    with connect_db(db_path) as connection:
        segment_section_map = {
            row["segment_id"]: row["section_id"]
            for row in connection.execute("SELECT segment_id, section_id FROM segments WHERE work_id = ?", (work_id,)).fetchall()
        }
        exact_alignment_rows = connection.execute(
            """
            SELECT alignment_id, section_id, chinese_segment_ids_json, translation_segment_ids_json
            FROM alignments
            WHERE work_id = ? AND alignment_type = 'exact_or_near_exact'
            """,
            (work_id,),
        ).fetchall()
        grouped_alignment_ids = {
            row["alignment_id"]
            for row in connection.execute(
                "SELECT alignment_id FROM alignments WHERE work_id = ? AND alignment_type = 'section_group'",
                (work_id,),
            ).fetchall()
        }

    for row in exact_alignment_rows:
        chinese_ids = json.loads(row["chinese_segment_ids_json"])
        translation_ids = json.loads(row["translation_segment_ids_json"])
        referenced_sections = {segment_section_map[segment_id] for segment_id in [*chinese_ids, *translation_ids]}
        if referenced_sections != {row["section_id"]}:
            failures.append(f"Exact alignment {row['alignment_id']} crosses poem boundaries: {sorted(referenced_sections)}")

    for section in complete_sections:
        section_rows = exact_row_map.get(section["section_id"], [])
        if not section_rows:
            failures.append(f"Complete section {section['section_id']} has no exact alignment rows.")
            continue
        for row in section_rows:
            if row["alignment_granularity"] == "stanza":
                stanza_exact_alignment_count += 1
            if row["alignment_granularity"] == "poem":
                poem_exact_alignment_count += 1
                has_multiple_stanzas = "\n\n" in str(row["chinese_text"]) or "\n\n" in str(row["translation_text"])
                if has_multiple_stanzas and not row["is_coarse_alignment"]:
                    failures.append(
                        f"Poem-level Shijing alignment {row['alignment_id']} is missing a coarse flag despite multi-stanza text."
                    )
            if row["is_coarse_alignment"]:
                coarse_alignment_count += 1
                if row["alignment_granularity"] != "poem":
                    failures.append(f"Non-poem alignment {row['alignment_id']} is incorrectly marked coarse.")
                if not row.get("coarse_alignment_reason"):
                    failures.append(f"Coarse alignment {row['alignment_id']} is missing a coarse_alignment_reason.")

    metadata_only_sections = [section for section in sections if section.get("tmx_status") != "complete"]
    for section in metadata_only_sections:
        paths = corpus_export_paths(work_id)
        section_tmx = REPO_ROOT / "corpus" / "exports" / "tmx" / f"{work_id}__{section['section_id']}__aligned_passages.tmx"
        if section_tmx.exists():
            failures.append(f"Metadata-only section {section['section_id']} unexpectedly has a TMX export.")
        if section.get("status") in {"needs_review", "needs_alignment"} and section.get("source_ids"):
            failures.append(f"Metadata-only section {section['section_id']} should not carry source_ids yet.")

    corpus_tmx = corpus_export_paths(work_id)["tmx"]
    if corpus_tmx.exists():
        tree = ET.parse(corpus_tmx)
        tuids = {tu.attrib.get("tuid", "") for tu in tree.getroot().findall("./body/tu")}
        leaked_group_ids = sorted(alignment_id for alignment_id in grouped_alignment_ids if alignment_id in tuids)
        if leaked_group_ids:
            failures.append(f"Section-group alignments leaked into TMX export: {leaked_group_ids[:5]}")
    else:
        failures.append(f"Missing corpus TMX export: {corpus_tmx}")

    if stanza_exact_alignment_count == 0:
        notes.append("No stanza-level exact alignments were found for this work.")
    else:
        notes.append(f"Stanza-level exact alignments present: {stanza_exact_alignment_count}.")
    if poem_exact_alignment_count:
        notes.append(f"Poem-level exact alignments present: {poem_exact_alignment_count}.")
    notes.append(
        "Stanza-level alignment remains preferred where structurally safe; poem-level exact alignment is treated as the coarse fallback."
    )

    report = {
        "status": "pass" if not failures else "fail",
        "work_id": work_id,
        "manifest_section_count": len(sections),
        "complete_section_count": len(complete_sections),
        "metadata_only_section_count": len(metadata_only_sections),
        "exact_alignment_count": len(exact_rows),
        "stanza_exact_alignment_count": stanza_exact_alignment_count,
        "poem_exact_alignment_count": poem_exact_alignment_count,
        "coarse_alignment_count": coarse_alignment_count,
        "failures": failures,
        "notes": notes,
    }
    write_json(report_output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate alignment granularity and coarse-alignment policy for a work.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file.")
    parser.add_argument("--work-id", default="shijing", help="Which work to validate.")
    parser.add_argument("--report-output", default=str(DEFAULT_REPORT_OUTPUT), help="Where to write the QC report.")
    args = parser.parse_args()
    report = validate_alignment_granularity(args.db, args.report_output, work_id=args.work_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "pass":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
