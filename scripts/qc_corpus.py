from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from chinesenotes_alignment import find_anchor_drift_issues, load_alignment_anchor_maps
from common import (
    DEFAULT_DB_PATH,
    DEFAULT_WORK_ID,
    REPO_ROOT,
    connect_db,
    corpus_export_paths,
    load_work_manifest,
    manifest_sections,
    read_jsonl,
    repo_relative,
    section_export_paths,
    sha256_file,
    write_json,
)
from text_quality import (
    detect_probable_ocr_corruption,
    has_probable_leading_fragment,
    has_probable_trailing_fragment,
)

CJK_RE = re.compile(r"[\u3400-\u9fff]")
PARENTHETICAL_HEADING_RE = re.compile(r"^\([^()]{1,120}\)$")
GENERIC_NOTICE_MARKERS = (
    "english translation:",
    "wikisource, accessed",
    "public domain worldwide",
    "this work was published before january 1, 1923",
    "creative commons",
)
LAOZI_COMMENTARY_MARKERS = ("〈", "〉", "編者按", "河上", "注釋")
LAOZI_NOTICE_MARKERS = (
    "english translation:",
    "chinese text:",
    "public domain worldwide",
    "this work was published before january 1, 1923",
    "english translations",
    "legge 1891",
)
ENGLISH_CLAUSE_MARKER_RE = re.compile(r"[.;?!:]")
STRUCTURAL_HEADING_RE = re.compile(r"^(?:Book|PART|Section)\b")
KNOWN_SHANGSHU_BAD_FORMS = (
    "inteuigent",
    "without-effprt",
    "cour- te-qus",
    "rea,ched",
    "black-liaired",
    "1 can",
)
SHANGSHU_ALIGNMENT_ANCHORS_PATH = REPO_ROOT / "metadata" / "shangshu_alignment_anchors.yml"
YIJING_COMMENTARY_MARKERS = (
    "the superior man, in accordance with this",
    "what is the meaning of the words under",
    "the trigram representing",
    "this shows",
)
YIJING_NOTICE_MARKERS = (
    "english translation:",
    "public domain",
    "legge 1882",
)
YIJING_CANONICAL_ORDER = ("judgment", "first", "second", "third", "fourth", "fifth", "top", "use")
YIJING_USE_LINE_SECTION_IDS = {"yijing-001-qian", "yijing-002-kun"}


def _yijing_line_position_from_chinese(source_text: str) -> str | None:
    if source_text.startswith(("初九", "初六")):
        return "first"
    if source_text.startswith(("九二", "六二")):
        return "second"
    if source_text.startswith(("九三", "六三")):
        return "third"
    if source_text.startswith(("九四", "六四")):
        return "fourth"
    if source_text.startswith(("九五", "六五")):
        return "fifth"
    if source_text.startswith(("上九", "上六")):
        return "top"
    if source_text.startswith(("用九", "用六")):
        return "use"
    return None


def _yijing_line_position_from_translation(translation_text: str) -> str | None:
    lowered = " ".join(translation_text.casefold().split())
    prefix = lowered[:80]
    if "use of the number" in lowered:
        return "use"
    if "topmost" in prefix or "the sixth" in prefix or "in the sixth" in prefix:
        return "top"
    if "fifth" in prefix:
        return "fifth"
    if "fourth" in prefix:
        return "fourth"
    if "third" in prefix:
        return "third"
    if "second" in prefix:
        return "second"
    if "first" in prefix or "lowest" in prefix:
        return "first"
    return None


def _yijing_expected_order(section_id: str) -> list[str]:
    order = list(YIJING_CANONICAL_ORDER[:7])
    if section_id in YIJING_USE_LINE_SECTION_IDS:
        order.append("use")
    return order


def run_alignment_quality_checks(work_id: str) -> dict[str, object]:
    export_path = corpus_export_paths(work_id)["jsonl"]
    rows = read_jsonl(export_path) if export_path.exists() else []
    issues = {
        "false_precision_multi_clause_targets": [],
        "question_punctuation_mismatches": [],
        "suspicious_length_imbalance_rows": [],
        "non_grouped_segmentation_mismatch_rows": [],
        "alignment_drift_issues": [],
        "line_order_issues": [],
    }
    if work_id not in {"laozi", "shangshu", "yijing"}:
        return {**issues, "hard_failure_count": 0}
    for row in rows:
        source_text = str(row.get("chinese_text", "")).strip()
        translation_text = str(row.get("translation_text", "")).strip()
        normalized_translation = re.sub(r"^\d+\.\s*", "", translation_text)
        source_segment_count = int(row.get("source_segment_count", 0) or 0)
        target_segment_count = int(row.get("target_segment_count", 0) or 0)
        alignment_granularity = str(row.get("alignment_granularity", "") or "")
        if work_id in {"laozi", "shangshu"} and (
            source_segment_count == 1
            and target_segment_count == 1
            and len(ENGLISH_CLAUSE_MARKER_RE.findall(normalized_translation))
            >= (2 if work_id == "laozi" else (3 if work_id == "shangshu" else 4))
            and len(re.findall(r"[。；！？]", source_text)) <= 1
            and len(re.findall(r"[A-Za-z']+", normalized_translation)) >= 16
            and len(CJK_RE.findall(source_text)) <= (12 if work_id == "laozi" else (16 if work_id == "shangshu" else 20))
        ):
            issues["false_precision_multi_clause_targets"].append(str(row["alignment_id"]))
        if work_id in {"laozi", "shangshu"} and source_segment_count == 1 and target_segment_count == 1 and (
            source_text.endswith(("?", "？")) != translation_text.endswith("?")
        ):
            issues["question_punctuation_mismatches"].append(str(row["alignment_id"]))
        if work_id in {"laozi", "shangshu"} and (
            source_segment_count == 1
            and target_segment_count == 1
            and len(re.findall(r"[A-Za-z']+", translation_text)) >= (28 if work_id == "laozi" else (40 if work_id == "shangshu" else 50))
            and len(CJK_RE.findall(source_text)) <= (8 if work_id == "laozi" else (18 if work_id == "shangshu" else 24))
        ):
            issues["suspicious_length_imbalance_rows"].append(str(row["alignment_id"]))
        if alignment_granularity != "grouped" and source_segment_count != target_segment_count:
            issues["non_grouped_segmentation_mismatch_rows"].append(str(row["alignment_id"]))
    if work_id == "shangshu":
        anchor_maps = load_alignment_anchor_maps(SHANGSHU_ALIGNMENT_ANCHORS_PATH)
        rows_by_section: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            rows_by_section.setdefault(str(row["section_id"]), []).append(row)
        for section_id, section_rows in rows_by_section.items():
            anchor_map = anchor_maps.get(section_id)
            if not anchor_map:
                continue
            section_issues = find_anchor_drift_issues(section_rows, list(anchor_map.get("anchors", [])))
            for issue in section_issues:
                issues["alignment_drift_issues"].append(
                    f"{section_id}:{issue['anchor_id']}:{issue['issue']}"
                )
    if work_id == "yijing":
        rows_by_section: dict[str, list[dict[str, object]]] = {}
        for row in rows:
            source_text = str(row.get("chinese_text", "")).strip()
            translation_text = str(row.get("translation_text", "")).strip()
            section_id = str(row["section_id"])
            rows_by_section.setdefault(section_id, []).append(row)
            source_position = _yijing_line_position_from_chinese(source_text)
            if source_position is None:
                continue
            target_position = _yijing_line_position_from_translation(translation_text)
            if source_position != target_position:
                issues["alignment_drift_issues"].append(
                    f"{row['section_id']}:{row['alignment_id']}:line_position_mismatch:{source_position}->{target_position or 'none'}"
                )
        for section_id, section_rows in rows_by_section.items():
            ordered_rows = sorted(section_rows, key=lambda row: int(row.get("order", 0) or 0))
            observed_order: list[str] = []
            for row in ordered_rows:
                source_position = _yijing_line_position_from_chinese(str(row.get("chinese_text", "")).strip())
                observed_order.append("judgment" if source_position is None else source_position)
            expected_order = _yijing_expected_order(section_id)
            if observed_order != expected_order:
                issues["line_order_issues"].append(
                    f"{section_id}:expected={'/'.join(expected_order)}:observed={'/'.join(observed_order)}"
                )
    hard_failure_count = sum(1 for value in issues.values() if value)
    return {**issues, "hard_failure_count": hard_failure_count}


def run_text_integrity_checks(work_id: str) -> dict[str, object]:
    export_path = corpus_export_paths(work_id)["jsonl"]
    rows = read_jsonl(export_path) if export_path.exists() else []
    issues = {
        "empty_source_sections": set(),
        "empty_translation_sections": set(),
        "translation_with_chinese_sections": set(),
        "translation_with_notice_sections": set(),
        "translation_with_commentary_sections": set(),
        "translation_with_heading_sections": set(),
        "translation_with_ocr_corruption_rows": [],
        "translation_with_truncated_fragment_rows": [],
        "translation_with_known_bad_forms_rows": [],
    }
    for index, row in enumerate(rows):
        section_id = str(row["section_id"])
        alignment_id = str(row["alignment_id"])
        source_text = str(row.get("chinese_text", "")).strip()
        translation_text = str(row.get("translation_text", "")).strip()
        lowered = translation_text.lower()
        if not source_text:
            issues["empty_source_sections"].add(section_id)
        if not translation_text:
            issues["empty_translation_sections"].add(section_id)
        if CJK_RE.search(translation_text):
            issues["translation_with_chinese_sections"].add(section_id)
        if any(marker in lowered for marker in GENERIC_NOTICE_MARKERS):
            issues["translation_with_notice_sections"].add(section_id)
        if STRUCTURAL_HEADING_RE.match(translation_text):
            issues["translation_with_heading_sections"].add(section_id)
        if work_id == "laozi":
            if any(marker in translation_text for marker in LAOZI_COMMENTARY_MARKERS):
                issues["translation_with_commentary_sections"].add(section_id)
            if any(marker in lowered for marker in LAOZI_NOTICE_MARKERS):
                issues["translation_with_notice_sections"].add(section_id)
            if PARENTHETICAL_HEADING_RE.fullmatch(translation_text):
                issues["translation_with_heading_sections"].add(section_id)
        if work_id == "shangshu":
            if detect_probable_ocr_corruption(translation_text):
                issues["translation_with_ocr_corruption_rows"].append(alignment_id)
            if any(marker in lowered for marker in KNOWN_SHANGSHU_BAD_FORMS):
                issues["translation_with_known_bad_forms_rows"].append(alignment_id)
            next_row = rows[index + 1] if index + 1 < len(rows) else None
            if (
                next_row
                and str(next_row["section_id"]) == section_id
                and has_probable_trailing_fragment(translation_text)
                and has_probable_leading_fragment(str(next_row.get("translation_text", "")).strip())
            ):
                issues["translation_with_truncated_fragment_rows"].append(alignment_id)
        if work_id == "yijing":
            if detect_probable_ocr_corruption(translation_text):
                issues["translation_with_ocr_corruption_rows"].append(alignment_id)
            if any(marker in lowered for marker in YIJING_NOTICE_MARKERS):
                issues["translation_with_notice_sections"].add(section_id)
            if any(marker in lowered for marker in YIJING_COMMENTARY_MARKERS):
                issues["translation_with_commentary_sections"].add(section_id)
    issue_lists = {key: sorted(value) for key, value in issues.items()}
    hard_failure_count = sum(1 for value in issue_lists.values() if value)
    return {
        **issue_lists,
        "hard_failure_count": hard_failure_count,
    }


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
            is_non_exportable = section.get("tmx_status") != "complete"
            requires_exact_alignment = not is_non_exportable and section.get("alignment_status", "complete") == "complete"
            if (
                len(exact_alignment_rows) != section.get("expected_exact_alignment_count", 0)
                or (not is_non_exportable and grouped_alignment_count != 1)
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
    text_integrity = run_text_integrity_checks(work_id)
    report["text_integrity"] = text_integrity
    alignment_quality = run_alignment_quality_checks(work_id)
    report["alignment_quality"] = alignment_quality
    report["hard_failure_count"] = int(text_integrity["hard_failure_count"]) + int(alignment_quality["hard_failure_count"])
    if report["hard_failure_count"]:
        report["status"] = "fail"
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
