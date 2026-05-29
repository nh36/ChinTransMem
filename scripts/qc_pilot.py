from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    DEFAULT_DB_PATH,
    DEFAULT_QC_REPORT,
    PILOT_SECTION_ID,
    REPO_ROOT,
    connect_db,
    repo_relative,
    sha256_file,
    write_json,
)


def run_qc(db_path: Path | str = DEFAULT_DB_PATH, report_output: Path | str = DEFAULT_QC_REPORT) -> dict[str, object]:
    with connect_db(db_path) as connection:
        source_rows = connection.execute(
            """
            SELECT source_id, raw_path, processed_path
            FROM sources
            WHERE section_id = ?
            ORDER BY source_id
            """,
            (PILOT_SECTION_ID,),
        ).fetchall()
        segment_rows = connection.execute(
            """
            SELECT segment_id, source_id
            FROM segments
            WHERE section_id = ?
            """,
            (PILOT_SECTION_ID,),
        ).fetchall()
        alignment_rows = connection.execute(
            """
            SELECT alignment_id, alignment_type, chinese_segment_ids_json, translation_segment_ids_json
            FROM alignments
            WHERE section_id = ?
            ORDER BY alignment_id
            """,
            (PILOT_SECTION_ID,),
        ).fetchall()
        counts = {
            "works": connection.execute("SELECT COUNT(*) FROM works").fetchone()[0],
            "sections": connection.execute("SELECT COUNT(*) FROM sections").fetchone()[0],
            "persons": connection.execute("SELECT COUNT(*) FROM persons").fetchone()[0],
            "sources": connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
            "segments": connection.execute("SELECT COUNT(*) FROM segments").fetchone()[0],
            "alignments": connection.execute("SELECT COUNT(*) FROM alignments").fetchone()[0],
        }

    chinese_segments = {row["segment_id"] for row in segment_rows if row["source_id"] == "zhwikisource-20260529"}
    translation_segments = {row["segment_id"] for row in segment_rows if row["source_id"] == "legge-cc-v1-1893"}
    covered_chinese: set[str] = set()
    covered_translation: set[str] = set()
    many_to_many_alignment_ids: list[str] = []

    for row in alignment_rows:
        chinese_ids = set(json.loads(row["chinese_segment_ids_json"]))
        translation_ids = set(json.loads(row["translation_segment_ids_json"]))
        covered_chinese.update(chinese_ids)
        covered_translation.update(translation_ids)
        if len(chinese_ids) > 1 or len(translation_ids) > 1:
            many_to_many_alignment_ids.append(row["alignment_id"])

    unmatched_chinese = sorted(chinese_segments - covered_chinese)
    unmatched_translation = sorted(translation_segments - covered_translation)

    tracked_paths = []
    for source_row in source_rows:
        tracked_paths.append(REPO_ROOT / source_row["raw_path"])
        tracked_paths.append(REPO_ROOT / source_row["processed_path"])
    tracked_paths.append(
        REPO_ROOT
        / "corpus"
        / "processed"
        / "alignments"
        / "lunyu__book-01-xueer__zhwikisource-20260529__legge-cc-v1-1893__alignments.jsonl"
    )
    tracked_paths.append(
        REPO_ROOT
        / "corpus"
        / "processed"
        / "chinese_base_texts"
        / "lunyu__book-01-xueer__zhwikisource-20260529__base.txt"
    )
    tracked_paths.append(
        REPO_ROOT
        / "corpus"
        / "processed"
        / "translations"
        / "lunyu__book-01-xueer__legge-cc-v1-1893__translation.txt"
    )
    optional_paths = [
        REPO_ROOT / "corpus" / "exports" / "jsonl" / "lunyu__book-01-xueer__aligned_passages.jsonl",
        REPO_ROOT / "corpus" / "exports" / "csv" / "lunyu__book-01-xueer__aligned_passages.csv",
        REPO_ROOT / "corpus" / "exports" / "tmx" / "lunyu__book-01-xueer__aligned_passages.tmx",
        REPO_ROOT / "logs" / "qc_reports" / "lunyu__book-01-xueer__tmx_validation.json",
    ]
    tracked_paths.extend(path for path in optional_paths if path.exists())

    report = {
        "section_id": PILOT_SECTION_ID,
        "counts": counts,
        "many_to_many_alignment_ids": many_to_many_alignment_ids,
        "unmatched_chinese_segment_ids": unmatched_chinese,
        "unmatched_translation_segment_ids": unmatched_translation,
        "checksums": {repo_relative(path): sha256_file(path) for path in tracked_paths},
        "status": "pass" if not unmatched_chinese and not unmatched_translation and many_to_many_alignment_ids else "fail",
    }
    write_json(report_output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a QC report for the Lunyu plus Legge pilot.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file.")
    parser.add_argument("--report-output", default=str(DEFAULT_QC_REPORT), help="Where to write the QC report.")
    args = parser.parse_args()

    report = run_qc(args.db, args.report_output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
