from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    DEFAULT_CORPUS_QC_REPORT,
    DEFAULT_DB_PATH,
    REPO_ROOT,
    connect_db,
    corpus_export_paths,
    load_corpus_manifest,
    manifest_sections,
    repo_relative,
    section_export_paths,
    sha256_file,
    write_json,
)


def run_qc(db_path: Path | str = DEFAULT_DB_PATH, report_output: Path | str = DEFAULT_CORPUS_QC_REPORT) -> dict[str, object]:
    manifest = load_corpus_manifest()
    with connect_db(db_path) as connection:
        counts = {
            "works": connection.execute("SELECT COUNT(*) FROM works").fetchone()[0],
            "sections": connection.execute("SELECT COUNT(*) FROM sections").fetchone()[0],
            "persons": connection.execute("SELECT COUNT(*) FROM persons").fetchone()[0],
            "sources": connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
            "segments": connection.execute("SELECT COUNT(*) FROM segments").fetchone()[0],
            "alignments": connection.execute("SELECT COUNT(*) FROM alignments").fetchone()[0],
        }

        section_reports: list[dict[str, object]] = []
        overall_status = "pass"
        for section in manifest_sections():
            segment_rows = connection.execute(
                """
                SELECT segment_id, source_id
                FROM segments
                WHERE section_id = ?
                """,
                (section["section_id"],),
            ).fetchall()
            exact_alignment_rows = connection.execute(
                """
                SELECT alignment_id, chinese_segment_ids_json, translation_segment_ids_json
                FROM alignments
                WHERE section_id = ? AND alignment_type = 'exact_or_near_exact'
                ORDER BY alignment_id
                """,
                (section["section_id"],),
            ).fetchall()
            grouped_alignment_count = connection.execute(
                """
                SELECT COUNT(*)
                FROM alignments
                WHERE section_id = ? AND alignment_type = 'section_group'
                """,
                (section["section_id"],),
            ).fetchone()[0]

            chinese_segments = {row["segment_id"] for row in segment_rows if row["source_id"] == section["source_ids"]["source_id"]}
            translation_segments = {
                row["segment_id"] for row in segment_rows if row["source_id"] == section["source_ids"]["target_source_id"]
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
            if (
                len(exact_alignment_rows) != section["expected_exact_alignment_count"]
                or grouped_alignment_count != 1
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

    tracked_paths: list[Path] = [REPO_ROOT / "metadata" / name for name in ("corpus_manifest.yml", "sections.yml", "sources.yml")]
    tracked_paths.extend(
        path
        for section in manifest_sections()
        for path in (
            section_export_paths(section["section_id"])["jsonl"],
            section_export_paths(section["section_id"])["csv"],
            section_export_paths(section["section_id"])["tmx"],
            section_export_paths(section["section_id"])["tmx_validation"],
        )
        if path.exists()
    )
    tracked_paths.extend(path for path in corpus_export_paths().values() if path.exists())
    report = {
        "status": overall_status,
        "manifest_summary": manifest["summary"],
        "counts": counts,
        "sections": section_reports,
        "checksums": {repo_relative(path): sha256_file(path) for path in tracked_paths},
    }
    write_json(report_output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a QC report for the full Lunyu corpus.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file.")
    parser.add_argument("--report-output", default=str(DEFAULT_CORPUS_QC_REPORT), help="Where to write the QC report.")
    args = parser.parse_args()

    report = run_qc(args.db, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
