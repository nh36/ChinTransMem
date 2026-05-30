from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    DEFAULT_DB_PATH,
    DEFAULT_WORK_ID,
    REPO_ROOT,
    connect_db,
    corpus_export_paths,
    load_work_manifest,
    manifest_sections,
    repo_relative,
    section_export_paths,
    sha256_file,
    write_json,
)


def run_qc(
    db_path: Path | str = DEFAULT_DB_PATH,
    report_output: Path | str | None = None,
    *,
    work_id: str = DEFAULT_WORK_ID,
) -> dict[str, object]:
    manifest = load_work_manifest(work_id)
    if report_output is None:
        report_output = corpus_export_paths(work_id)["tmx_validation"].with_name(f"{work_id}__corpus_qc.json")
    with connect_db(db_path) as connection:
        counts = {
            "works": connection.execute("SELECT COUNT(*) FROM works WHERE work_id = ?", (work_id,)).fetchone()[0],
            "sections": connection.execute("SELECT COUNT(*) FROM sections WHERE work_id = ?", (work_id,)).fetchone()[0],
            "persons": connection.execute("SELECT COUNT(*) FROM persons").fetchone()[0],
            "sources": connection.execute("SELECT COUNT(*) FROM sources WHERE work_id = ?", (work_id,)).fetchone()[0],
            "segments": connection.execute("SELECT COUNT(*) FROM segments WHERE work_id = ?", (work_id,)).fetchone()[0],
            "alignments": connection.execute("SELECT COUNT(*) FROM alignments WHERE work_id = ?", (work_id,)).fetchone()[0],
        }

        section_reports: list[dict[str, object]] = []
        overall_status = "pass"
        for section in manifest_sections(work_id):
            segment_rows = connection.execute(
                """
                SELECT segment_id, source_id
                FROM segments
                WHERE work_id = ? AND section_id = ?
                """,
                (work_id, section["section_id"]),
            ).fetchall()
            exact_alignment_rows = connection.execute(
                """
                SELECT alignment_id, chinese_segment_ids_json, translation_segment_ids_json
                FROM alignments
                WHERE work_id = ? AND section_id = ? AND alignment_type = 'exact_or_near_exact'
                ORDER BY alignment_id
                """,
                (work_id, section["section_id"]),
            ).fetchall()
            grouped_alignment_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM alignments
                WHERE work_id = ? AND section_id = ? AND alignment_type = 'section_group'
                """,
                (work_id, section["section_id"]),
            ).fetchone()[0]

            source_ids = section.get("source_ids", {})
            chinese_segments = {
                row["segment_id"] for row in segment_rows if row["source_id"] == source_ids.get("source_id")
            }
            translation_segments = {
                row["segment_id"] for row in segment_rows if row["source_id"] == source_ids.get("target_source_id")
            }
            covered_chinese: set[str] = set()
            covered_translation: set[str] = set()
            for row in exact_alignment_rows:
                covered_chinese.update(json.loads(row["chinese_segment_ids_json"]))
                covered_translation.update(json.loads(row["translation_segment_ids_json"]))

            unmatched_chinese = sorted(chinese_segments - covered_chinese)
            unmatched_translation = sorted(translation_segments - covered_translation)
            status = "pass"
            requires_exact_alignment = section.get("alignment_status", "complete") == "complete"
            is_metadata_only = section.get("alignment_status") == "metadata_only"
            if (
                len(exact_alignment_rows) != section.get("expected_exact_alignment_count", 0)
                or (not is_metadata_only and grouped_alignment_count != 1)
                or (requires_exact_alignment and unmatched_chinese)
                or (requires_exact_alignment and unmatched_translation)
            ):
                status = "fail"
                overall_status = "fail"

            section_reports.append(
                {
                    "section_id": section["section_id"],
                    "alignment_status": section.get("alignment_status", "complete"),
                    "tmx_status": section.get("tmx_status", "complete"),
                    "status": status,
                    "expected_exact_alignment_count": section["expected_exact_alignment_count"],
                    "exact_alignment_count": len(exact_alignment_rows),
                    "grouped_alignment_count": grouped_alignment_count,
                    "unmatched_chinese_segment_ids": unmatched_chinese,
                    "unmatched_translation_segment_ids": unmatched_translation,
                }
            )

    tracked_paths: list[Path] = [REPO_ROOT / "metadata" / "sections.yml", REPO_ROOT / "metadata" / "sources.yml"]
    manifest_path = REPO_ROOT / "metadata" / "manifests" / f"{work_id}.yml"
    if manifest_path.exists():
        tracked_paths.append(manifest_path)
    if work_id == DEFAULT_WORK_ID:
        tracked_paths.append(REPO_ROOT / "metadata" / "corpus_manifest.yml")
    tracked_paths.extend(
        path
        for section in manifest_sections(work_id)
        for path in (
            section_export_paths(section["section_id"], work_id)["jsonl"],
            section_export_paths(section["section_id"], work_id)["csv"],
            section_export_paths(section["section_id"], work_id)["tmx"],
            section_export_paths(section["section_id"], work_id)["tmx_validation"],
        )
        if path.exists()
    )
    tracked_paths.extend(path for path in corpus_export_paths(work_id).values() if path.exists())
    report = {
        "status": overall_status,
        "work_id": work_id,
        "manifest_summary": manifest["summary"],
        "counts": counts,
        "sections": section_reports,
        "checksums": {repo_relative(path): sha256_file(path) for path in tracked_paths},
    }
    write_json(report_output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a QC report for a work in the corpus.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file.")
    parser.add_argument("--work-id", default=DEFAULT_WORK_ID, help="Which work manifest to QC.")
    parser.add_argument("--report-output", default=None, help="Where to write the QC report.")
    args = parser.parse_args()

    report = run_qc(args.db, args.report_output, work_id=args.work_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
