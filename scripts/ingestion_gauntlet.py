from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from ai_review_alignments import FAILING_CLASSIFICATIONS, review_candidate_alignments, summarize_reviews
from bootstrap_work_corpus import bootstrap_all_manifests
from common import (
    AI_REVIEWS_DIR,
    DEFAULT_DB_PATH,
    DEFAULT_WORK_ID,
    REPO_ROOT,
    candidate_ai_review_path,
    candidate_alignment_snapshot_path,
    candidate_corpus_export_paths,
    candidate_qc_report_path,
    candidate_report_path,
    candidate_repair_log_path,
    candidate_section_export_paths,
    candidate_state_path,
    candidate_work_dir,
    connect_db,
    corpus_export_paths,
    load_work_batch_mapping,
    load_sources,
    load_work_manifest,
    manifest_sections,
    repo_relative,
    repair_log_suffix,
    scope_key,
    section_export_paths,
    sha256_file,
    utc_now_iso,
    write_json,
)
from export_corpus import export_corpus, load_exact_alignment_rows, write_tabular_exports, write_tmx
from import_corpus import import_corpus
from qc_corpus import run_alignment_quality_checks, run_qc, run_source_traceability_checks, run_text_integrity_checks
from validate_tmx import validate_tmx_file

CANDIDATE_STATES = {
    "candidate_ingested",
    "candidate_qc_failed",
    "candidate_repaired",
    "candidate_ready_for_promotion",
    "active_proof_of_concept",
    "active_release_ready",
    "metadata_only_blocked",
}


def _require_batch_scope(work_id: str, batch_id: str | None = None) -> None:
    if work_id == "shiji" and not batch_id:
        raise ValueError("Shiji candidate ingestion is batch-only. Provide --batch-id (for example, --batch-id benji).")


def _batch_entry(work_id: str, batch_id: str | None = None) -> dict[str, Any] | None:
    if not batch_id:
        return None
    mapping = load_work_batch_mapping(work_id)
    for entry in mapping.get("batches", []):
        if str(entry.get("batch_id")) == batch_id:
            return dict(entry)
    raise KeyError(f"Unknown batch_id {batch_id!r} for work {work_id!r}.")


def _batch_section_ids(work_id: str, batch_id: str | None = None) -> list[str]:
    entry = _batch_entry(work_id, batch_id)
    if entry is None:
        return [str(section["section_id"]) for section in manifest_sections(work_id)]
    section_ids = [str(section_id) for section_id in entry.get("section_ids", [])]
    if not section_ids:
        section_ids = [
            str(section["section_id"])
            for section in manifest_sections(work_id)
            if str(section.get("batch_id") or "") == batch_id
        ]
    if not section_ids:
        raise KeyError(f"Batch {batch_id!r} for {work_id!r} does not define section_ids.")
    return section_ids


def _scoped_manifest(work_id: str, batch_id: str | None = None) -> dict[str, Any]:
    manifest = load_work_manifest(work_id)
    if not batch_id:
        return manifest
    section_ids = set(_batch_section_ids(work_id, batch_id))
    sections = [section for section in manifest["sections"] if str(section["section_id"]) in section_ids]
    exact_alignment_count = sum(int(section.get("expected_exact_alignment_count", 0) or 0) for section in sections)
    active_sections = [section for section in sections if section.get("tmx_status") == "complete"]
    fallback_sections = [section for section in sections if section.get("fallback_used")]
    scoped = dict(manifest)
    scoped["sections"] = sections
    scoped["summary"] = {
        **dict(manifest.get("summary", {})),
        "section_count": len(sections),
        "complete_sections": len(active_sections),
        "metadata_only_sections": len(sections) - len(active_sections),
        "total_section_count": len(sections),
        "active_exportable_section_count": len(active_sections),
        "active_section_count": len(active_sections),
        "exportable_section_count": len(active_sections),
        "metadata_only_blocked_section_count": len(sections) - len(active_sections),
        "blocked_section_count": len(sections) - len(active_sections),
        "exact_alignment_count": exact_alignment_count,
        "active_exportable_alignment_count": exact_alignment_count,
        "fallback_alignment_count": len(fallback_sections),
        "fallback_section_count": len(fallback_sections),
        "section_group_alignment_record_count": len(active_sections),
        "alignment_record_count": exact_alignment_count + len(active_sections),
    }
    return scoped


def _filter_rows_to_scope(rows: list[dict[str, Any]], work_id: str, batch_id: str | None = None) -> list[dict[str, Any]]:
    if not batch_id:
        return rows
    section_ids = set(_batch_section_ids(work_id, batch_id))
    return [row for row in rows if str(row.get("section_id")) in section_ids]


def _scope_title(work_id: str, batch_id: str | None = None) -> str:
    if not batch_id:
        return work_id
    return f"{work_id} {batch_id}"


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_review_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _candidate_snapshot_paths(work_id: str, batch_id: str | None = None) -> dict[str, Path]:
    root = candidate_work_dir(work_id, batch_id)
    return {
        "manifest": root / "metadata" / f"{scope_key(work_id, batch_id)}.yml",
        "alignment_qc": candidate_alignment_snapshot_path(work_id, batch_id),
        "repair_log": candidate_repair_log_path(work_id, batch_id),
    }


def _active_state_for_manifest(manifest: dict[str, Any]) -> str:
    if str(manifest.get("release_status", "")) == "cleared":
        return "active_release_ready"
    return "active_proof_of_concept"


def _load_candidate_state(work_id: str, batch_id: str | None = None) -> dict[str, Any]:
    path = candidate_state_path(work_id, batch_id)
    if not path.exists():
        return {"work_id": work_id, "batch_id": batch_id, "current_state": None, "history": []}
    return json.loads(path.read_text(encoding="utf-8"))


def update_candidate_state(
    work_id: str,
    state: str,
    *,
    batch_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if state not in CANDIDATE_STATES:
        raise ValueError(f"Unsupported candidate state: {state}")
    payload = _load_candidate_state(work_id, batch_id)
    payload["work_id"] = work_id
    payload["batch_id"] = batch_id
    payload["current_state"] = state
    payload.setdefault("history", []).append(
        {
            "state": state,
            "timestamp": utc_now_iso(),
            "details": details or {},
        }
    )
    write_json(candidate_state_path(work_id, batch_id), payload)
    return payload


def _reset_candidate_workspace(work_id: str, batch_id: str | None = None) -> None:
    root = candidate_work_dir(work_id, batch_id)
    root.mkdir(parents=True, exist_ok=True)
    for name in ("exports", "reports", "repair_logs", "metadata"):
        shutil.rmtree(root / name, ignore_errors=True)


def _copy_if_exists(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _snapshot_candidate_inputs(work_id: str, batch_id: str | None = None) -> dict[str, str]:
    snapshots = _candidate_snapshot_paths(work_id, batch_id)
    manifest_path = REPO_ROOT / "metadata" / "manifests" / f"{work_id}.yml"
    alignment_qc_path = REPO_ROOT / "logs" / "qc_reports" / f"{work_id}__alignment_qc.json"
    repair_log_path = REPO_ROOT / "logs" / "qc_reports" / f"{work_id}__{repair_log_suffix(work_id)}.json"
    if not repair_log_path.exists():
        repair_log_path = REPO_ROOT / "logs" / "qc_reports" / f"{work_id}__ocr_repair_log.json"
    _copy_if_exists(manifest_path, snapshots["manifest"])
    _copy_if_exists(alignment_qc_path, snapshots["alignment_qc"])
    _copy_if_exists(repair_log_path, snapshots["repair_log"])
    return {key: repo_relative(path) for key, path in snapshots.items() if path.exists()}


def write_candidate_exports(
    work_id: str,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    batch_id: str | None = None,
) -> dict[str, Any]:
    root_paths = candidate_corpus_export_paths(work_id, batch_id)
    per_section: list[dict[str, Any]] = []
    for section in _scoped_manifest(work_id, batch_id)["sections"]:
        if section.get("tmx_status", "complete") != "complete":
            continue
        rows = load_exact_alignment_rows(db_path, work_id, section["section_id"])
        paths = candidate_section_export_paths(section["section_id"], work_id, batch_id)
        write_tabular_exports(rows, paths["jsonl"], paths["csv"])
        write_tmx(rows, paths["tmx"], work_id=work_id)
        validation = validate_tmx_file(db_path, paths["tmx"], paths["tmx_validation"], section["section_id"], work_id=work_id)
        per_section.append(
            {
                "section_id": section["section_id"],
                "rows_exported": len(rows),
                "jsonl_output": repo_relative(paths["jsonl"]),
                "csv_output": repo_relative(paths["csv"]),
                "tmx_output": repo_relative(paths["tmx"]),
                "tmx_validation_output": repo_relative(paths["tmx_validation"]),
                "tmx_status": validation["status"],
            }
        )
    section_ids = {section["section_id"] for section in _scoped_manifest(work_id, batch_id)["sections"]}
    corpus_rows = [row for row in load_exact_alignment_rows(db_path, work_id) if row["section_id"] in section_ids]
    write_tabular_exports(corpus_rows, root_paths["jsonl"], root_paths["csv"])
    write_tmx(corpus_rows, root_paths["tmx"], work_id=work_id)
    corpus_validation = validate_tmx_file(db_path, root_paths["tmx"], root_paths["tmx_validation"], work_id=work_id)
    return {
        "work_id": work_id,
        "batch_id": batch_id,
        "rows_exported": len(corpus_rows),
        "section_count": len(per_section),
        "jsonl_output": repo_relative(root_paths["jsonl"]),
        "csv_output": repo_relative(root_paths["csv"]),
        "tmx_output": repo_relative(root_paths["tmx"]),
        "tmx_validation_output": repo_relative(root_paths["tmx_validation"]),
        "sections": per_section,
        "corpus_tmx_status": corpus_validation["status"],
    }


def ingest_candidate(work_id: str, *, skip_fetch: bool = True, batch_id: str | None = None) -> dict[str, Any]:
    _require_batch_scope(work_id, batch_id)
    _reset_candidate_workspace(work_id, batch_id)
    if work_id == "shiji" and batch_id:
        from bootstrap_shiji_corpus import bootstrap_shiji_corpus

        bootstrap_shiji_corpus(skip_fetch=skip_fetch, batch_id=batch_id)
    bootstrap_summary = bootstrap_all_manifests(skip_fetch=skip_fetch)
    bootstrap_work_summary = next(
        work_summary["summary"] for work_summary in bootstrap_summary["works"] if work_summary["work_id"] == work_id
    )
    import_summary = import_corpus(DEFAULT_DB_PATH)
    export_summary = write_candidate_exports(work_id, db_path=DEFAULT_DB_PATH, batch_id=batch_id)
    snapshots = _snapshot_candidate_inputs(work_id, batch_id)
    state = update_candidate_state(
        work_id,
        "candidate_ingested",
        batch_id=batch_id,
        details={
            "bootstrap_summary": bootstrap_work_summary,
            "candidate_export": export_summary,
        },
    )
    return {
        "work_id": work_id,
        "batch_id": batch_id,
        "state": state["current_state"],
        "bootstrap_summary": bootstrap_work_summary,
        "import_summary": import_summary["work_summaries"][work_id]["summary"],
        "candidate_export": export_summary,
        "snapshots": snapshots,
    }


def _candidate_rows_by_section(
    work_id: str,
    batch_id: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    corpus_rows = [
        dict(row)
        for row in _load_review_rows(candidate_corpus_export_paths(work_id, batch_id)["jsonl"])
    ]
    corpus_rows = _filter_rows_to_scope(corpus_rows, work_id, batch_id)
    rows_by_section: dict[str, list[dict[str, Any]]] = {}
    for row in corpus_rows:
        # Ensure legacy or malformed candidate rows include work_id to avoid KeyError in downstream code.
        if "work_id" not in row:
            row["work_id"] = work_id
        rows_by_section.setdefault(str(row["section_id"]), []).append(row)
    return corpus_rows, rows_by_section


def _active_rows(work_id: str, batch_id: str | None = None) -> list[dict[str, Any]]:
    rows = [dict(row) for row in _load_review_rows(corpus_export_paths(work_id)["jsonl"])]
    # Defensive: ensure active export rows include work_id for consumers that expect it.
    for row in rows:
        if "work_id" not in row:
            row["work_id"] = work_id
    return _filter_rows_to_scope(rows, work_id, batch_id)


def compare_candidate_and_active_exports(
    work_id: str,
    *,
    batch_id: str | None = None,
    candidate_qc: dict[str, Any] | None = None,
    active_qc: dict[str, Any] | None = None,
    candidate_rows: list[dict[str, Any]] | None = None,
    active_rows: list[dict[str, Any]] | None = None,
    candidate_alignment_snapshot: dict[str, Any] | None = None,
    active_alignment_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    candidate_report = candidate_qc or _load_json(candidate_qc_report_path(work_id, batch_id))
    active_report = active_qc or _load_json(REPO_ROOT / "logs" / "qc_reports" / f"{work_id}__corpus_qc.json")
    candidate_alignment = candidate_alignment_snapshot or _load_json(candidate_alignment_snapshot_path(work_id, batch_id))
    active_alignment = active_alignment_snapshot or _load_json(REPO_ROOT / "logs" / "qc_reports" / f"{work_id}__alignment_qc.json")
    candidate_export_rows = candidate_rows or _load_review_rows(candidate_corpus_export_paths(work_id, batch_id)["jsonl"])
    candidate_export_rows = _filter_rows_to_scope(candidate_export_rows, work_id, batch_id)
    active_export_rows = active_rows or _active_rows(work_id, batch_id)

    mismatches: list[str] = []
    candidate_section_ids = sorted({str(row["section_id"]) for row in candidate_export_rows})
    active_section_ids = sorted({str(row["section_id"]) for row in active_export_rows})
    if candidate_section_ids != active_section_ids:
        mismatches.append("candidate and active promoted section ids differ")
    if len(candidate_export_rows) != len(active_export_rows):
        mismatches.append("candidate and active exact alignment counts differ")
    if sum(1 for row in candidate_export_rows if row.get("is_coarse_alignment")) != sum(
        1 for row in active_export_rows if row.get("is_coarse_alignment")
    ):
        mismatches.append("candidate and active fallback counts differ")

    candidate_alignment_summary = candidate_alignment.get("summary", {})
    active_alignment_summary = active_alignment.get("summary", {})
    for label, candidate_value, active_value in (
        ("promoted section count", len(candidate_section_ids), len(active_section_ids)),
        ("exact alignment count", len(candidate_export_rows), len(active_export_rows)),
        (
            "fallback count",
            sum(1 for row in candidate_export_rows if row.get("is_coarse_alignment")),
            sum(1 for row in active_export_rows if row.get("is_coarse_alignment")),
        ),
        (
            "OCR issue count",
            int(candidate_alignment_summary.get("remaining_corruption_issue_count", 0)),
            int(active_alignment_summary.get("remaining_corruption_issue_count", 0)),
        ),
        (
            "leakage issue count",
            int(candidate_alignment_summary.get("remaining_leakage_issue_count", 0)),
            int(active_alignment_summary.get("remaining_leakage_issue_count", 0)),
        ),
        (
            "drift issue count",
            int(candidate_alignment_summary.get("remaining_drift_issue_count", 0)),
            int(active_alignment_summary.get("remaining_drift_issue_count", 0)),
        ),
        (
            "witness-quality issue count",
            int(candidate_alignment_summary.get("remaining_witness_quality_issue_count", 0)),
            int(active_alignment_summary.get("remaining_witness_quality_issue_count", 0)),
        ),
    ):
        if candidate_value != active_value:
            mismatches.append(f"candidate and active {label} differ ({candidate_value} != {active_value})")

    for key in ("hard_failure_count",):
        if int(candidate_report.get(key, 0)) != int(active_report.get(key, 0)):
            mismatches.append(f"candidate and active corpus QC {key} differ")

    if batch_id is None:
        for candidate_path, active_path in (
            (candidate_corpus_export_paths(work_id)["jsonl"], corpus_export_paths(work_id)["jsonl"]),
            (candidate_corpus_export_paths(work_id)["csv"], corpus_export_paths(work_id)["csv"]),
            (candidate_corpus_export_paths(work_id)["tmx"], corpus_export_paths(work_id)["tmx"]),
        ):
            if candidate_path.exists() and active_path.exists() and sha256_file(candidate_path) != sha256_file(active_path):
                mismatches.append(f"candidate and active corpus export differ for {candidate_path.suffix.lstrip('.')}")
    for section_id in candidate_section_ids:
        candidate_paths = candidate_section_export_paths(section_id, work_id, batch_id)
        active_paths = section_export_paths(section_id, work_id)
        for key in ("jsonl", "csv", "tmx"):
            if candidate_paths[key].exists() and active_paths[key].exists() and sha256_file(candidate_paths[key]) != sha256_file(active_paths[key]):
                mismatches.append(f"candidate and active section export differ for {section_id} ({key})")

    return {
        "work_id": work_id,
        "batch_id": batch_id,
        "matches": not mismatches,
        "mismatches": sorted(set(mismatches)),
        "candidate_section_count": len(candidate_section_ids),
        "active_section_count": len(active_section_ids),
        "candidate_exact_alignment_count": len(candidate_export_rows),
        "active_exact_alignment_count": len(active_export_rows),
        "candidate_fallback_count": sum(1 for row in candidate_export_rows if row.get("is_coarse_alignment")),
        "active_fallback_count": sum(1 for row in active_export_rows if row.get("is_coarse_alignment")),
    }


def run_candidate_qc(
    work_id: str,
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    batch_id: str | None = None,
) -> dict[str, Any]:
    _require_batch_scope(work_id, batch_id)
    manifest = _scoped_manifest(work_id, batch_id)
    section_ids = [section["section_id"] for section in manifest["sections"]]
    corpus_rows, rows_by_section = _candidate_rows_by_section(work_id, batch_id)
    placeholders = ",".join("?" for _ in section_ids) or "''"
    with connect_db(db_path) as connection:
        counts = {
            "works": connection.execute("SELECT COUNT(*) FROM works WHERE work_id = ?", (work_id,)).fetchone()[0],
            "sections": connection.execute(
                f"SELECT COUNT(*) FROM sections WHERE work_id = ? AND section_id IN ({placeholders})",
                (work_id, *section_ids),
            ).fetchone()[0],
            "persons": connection.execute("SELECT COUNT(*) FROM persons").fetchone()[0],
            "sources": connection.execute(
                f"SELECT COUNT(*) FROM sources WHERE work_id = ? AND section_id IN ({placeholders})",
                (work_id, *section_ids),
            ).fetchone()[0],
            "segments": connection.execute(
                f"SELECT COUNT(*) FROM segments WHERE work_id = ? AND section_id IN ({placeholders})",
                (work_id, *section_ids),
            ).fetchone()[0],
            "alignments": connection.execute(
                f"SELECT COUNT(*) FROM alignments WHERE work_id = ? AND section_id IN ({placeholders})",
                (work_id, *section_ids),
            ).fetchone()[0],
            "exact_alignment_records": connection.execute(
                f"SELECT COUNT(*) FROM alignments WHERE work_id = ? AND section_id IN ({placeholders}) AND alignment_type = 'exact_or_near_exact'",
                (work_id, *section_ids),
            ).fetchone()[0],
            "section_group_alignment_records": connection.execute(
                f"SELECT COUNT(*) FROM alignments WHERE work_id = ? AND section_id IN ({placeholders}) AND alignment_type = 'section_group'",
                (work_id, *section_ids),
            ).fetchone()[0],
        }
        section_reports: list[dict[str, Any]] = []
        overall_status = "pass"
        for section in manifest["sections"]:
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
            chinese_segments = {row["segment_id"] for row in segment_rows if row["source_id"] == source_ids.get("source_id")}
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
            exact_export_count = len(rows_by_section.get(section["section_id"], []))
            status = "pass"
            is_non_exportable = section.get("tmx_status") != "complete"
            requires_exact_alignment = not is_non_exportable and section.get("alignment_status", "complete") == "complete"
            if (
                exact_export_count != section.get("expected_exact_alignment_count", 0)
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
                    "exact_alignment_count": exact_export_count,
                    "grouped_alignment_count": grouped_alignment_count,
                    "unmatched_chinese_segment_ids": unmatched_chinese,
                    "unmatched_translation_segment_ids": unmatched_translation,
                }
            )
    text_integrity = run_text_integrity_checks(work_id, rows=corpus_rows)
    alignment_quality = run_alignment_quality_checks(work_id, rows=corpus_rows)
    source_traceability = run_source_traceability_checks(work_id, section_ids=section_ids)
    count_disagreement_errors: list[str] = []
    if manifest["summary"]["exact_alignment_count"] != len(corpus_rows):
        count_disagreement_errors.append(
            f"manifest exact_alignment_count {manifest['summary']['exact_alignment_count']} != candidate export rows {len(corpus_rows)}"
        )
    if manifest["summary"]["alignment_record_count"] != counts["alignments"]:
        count_disagreement_errors.append(
            f"manifest alignment_record_count {manifest['summary']['alignment_record_count']} != sqlite alignment count {counts['alignments']}"
        )
    if manifest["summary"]["section_group_alignment_record_count"] != counts["section_group_alignment_records"]:
        count_disagreement_errors.append(
            "manifest section_group_alignment_record_count "
            f"{manifest['summary']['section_group_alignment_record_count']} != sqlite section_group count {counts['section_group_alignment_records']}"
        )
    candidate_paths: list[Path] = []
    for section in manifest["sections"]:
        if section.get("tmx_status") != "complete":
            continue
        candidate_paths.extend(
            path for path in candidate_section_export_paths(section["section_id"], work_id, batch_id).values() if path.exists()
        )
    candidate_paths.extend(path for path in candidate_corpus_export_paths(work_id, batch_id).values() if path.exists())
    snapshot_paths = [path for path in _candidate_snapshot_paths(work_id, batch_id).values() if path.exists()]
    report = {
        "status": overall_status,
        "work_id": work_id,
        "batch_id": batch_id,
        "candidate_export_root": repo_relative(candidate_work_dir(work_id, batch_id)),
        "manifest_summary": manifest["summary"],
        "counts": counts,
        "sections": section_reports,
        "text_integrity": text_integrity,
        "alignment_quality": alignment_quality,
        "source_traceability": source_traceability,
        "count_disagreement_errors": count_disagreement_errors,
        "review_required_fallback_alignment_ids": sorted(
            str(row["alignment_id"]) for row in corpus_rows if row.get("is_coarse_alignment")
        ),
        "checksums": {
            **{repo_relative(path): sha256_file(path) for path in candidate_paths},
            **{repo_relative(path): sha256_file(path) for path in snapshot_paths},
        },
    }
    report["deterministic_issue_count"] = (
        len(count_disagreement_errors)
        + int(text_integrity["hard_failure_count"])
        + int(alignment_quality["hard_failure_count"])
        + int(source_traceability["hard_failure_count"])
    )
    report["hard_failure_count"] = report["deterministic_issue_count"]
    if report["hard_failure_count"]:
        report["status"] = "fail"
        update_candidate_state(
            work_id,
            "candidate_qc_failed",
            batch_id=batch_id,
            details={"hard_failure_count": report["hard_failure_count"]},
        )
    write_json(candidate_qc_report_path(work_id, batch_id), report)
    return report


def run_candidate_ai_review(work_id: str, *, batch_id: str | None = None) -> dict[str, Any]:
    _require_batch_scope(work_id, batch_id)
    summary = review_candidate_alignments(
        work_id,
        input_jsonl=candidate_corpus_export_paths(work_id, batch_id)["jsonl"],
        output_path=candidate_ai_review_path(work_id, batch_id),
        qc_report_path=candidate_qc_report_path(work_id, batch_id),
        repair_log_path=candidate_repair_log_path(work_id, batch_id),
    )
    if summary["failed_high_risk_alignment_count"]:
        update_candidate_state(
            work_id,
            "candidate_qc_failed",
            batch_id=batch_id,
            details={"failed_high_risk_alignment_count": summary["failed_high_risk_alignment_count"]},
        )
    return summary


def refine_candidate(work_id: str, *, skip_fetch: bool = True, batch_id: str | None = None) -> dict[str, Any]:
    _require_batch_scope(work_id, batch_id)
    summary = ingest_candidate(work_id, skip_fetch=skip_fetch, batch_id=batch_id)
    update_candidate_state(
        work_id,
        "candidate_repaired",
        batch_id=batch_id,
        details={"candidate_export_rows": summary["candidate_export"]["rows_exported"]},
    )
    return summary


def evaluate_promotion_gates(
    work_id: str,
    *,
    batch_id: str | None = None,
    candidate_qc: dict[str, Any] | None = None,
    ai_reviews: list[dict[str, Any]] | None = None,
    alignment_snapshot: dict[str, Any] | None = None,
    repair_log: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    candidate_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    _require_batch_scope(work_id, batch_id)
    qc_report = candidate_qc or _load_json(candidate_qc_report_path(work_id, batch_id))
    review_rows = ai_reviews or _load_review_rows(candidate_ai_review_path(work_id, batch_id))
    alignment_payload = alignment_snapshot or _load_json(candidate_alignment_snapshot_path(work_id, batch_id))
    repair_payload = repair_log or _load_json(candidate_repair_log_path(work_id, batch_id))
    current_manifest = manifest or _scoped_manifest(work_id, batch_id)
    rows = candidate_rows or _load_review_rows(candidate_corpus_export_paths(work_id, batch_id)["jsonl"])
    rows = _filter_rows_to_scope(rows, work_id, batch_id)
    review_summary = summarize_reviews(review_rows)
    blockers: list[str] = []
    if not rows:
        blockers.append("candidate export is empty")
    if int(qc_report.get("hard_failure_count", 0)):
        blockers.append(f"deterministic candidate QC has {qc_report['hard_failure_count']} hard failures")
    alignment_summary = alignment_payload.get("summary", {})
    if int(alignment_summary.get("remaining_corruption_issue_count", 0)):
        blockers.append("remaining OCR corruption issues are nonzero")
    if int(alignment_summary.get("remaining_leakage_issue_count", 0)):
        blockers.append("remaining note/commentary leakage issues are nonzero")
    if int(alignment_summary.get("remaining_drift_issue_count", 0)):
        blockers.append("remaining alignment drift issues are nonzero")
    if int(alignment_summary.get("remaining_witness_quality_issue_count", 0)):
        blockers.append("remaining Shiji witness-quality issues are nonzero")
    if review_summary["failed_high_risk_alignment_count"]:
        blockers.append(
            f"alignment review found {review_summary['failed_high_risk_alignment_count']} failed high-risk alignments"
        )
    fallback_alignment_ids = sorted(str(row["alignment_id"]) for row in rows if row.get("is_coarse_alignment"))
    reviewed_fallback_alignment_ids = {
        str(review["alignment_id"])
        for review in review_rows
        if str(review.get("classification")) in {"fallback_justified", "too_coarse_but_usable"}
    }
    missing_fallback_reviews = [
        alignment_id for alignment_id in fallback_alignment_ids if alignment_id not in reviewed_fallback_alignment_ids
    ]
    if missing_fallback_reviews:
        blockers.append(f"fallback alignments lack reviewed justification: {missing_fallback_reviews}")
    if qc_report.get("count_disagreement_errors"):
        blockers.extend(str(error) for error in qc_report["count_disagreement_errors"])
    if current_manifest["summary"]["exact_alignment_count"] != len(rows):
        blockers.append("manifest/export exact alignment counts disagree")
    if current_manifest["summary"]["alignment_record_count"] != int(qc_report.get("counts", {}).get("alignments", 0)):
        blockers.append("manifest/qc total alignment counts disagree")
    if current_manifest["summary"]["section_group_alignment_record_count"] != int(
        qc_report.get("counts", {}).get("section_group_alignment_records", 0)
    ):
        blockers.append("manifest/qc section_group alignment counts disagree")
    if qc_report.get("source_traceability", {}).get("hard_failure_count"):
        blockers.append("candidate source provenance metadata is incomplete")
    if qc_report.get("alignment_quality", {}).get("line_order_issues"):
        blockers.append("candidate alignment review still has line-order issues")
    state = "candidate_ready_for_promotion" if not blockers else (
        "metadata_only_blocked" if current_manifest["summary"]["active_section_count"] == 0 else "candidate_qc_failed"
    )
    return {
        "work_id": work_id,
        "batch_id": batch_id,
        "can_promote": not blockers,
        "next_state": state,
        "blockers": blockers,
        "failed_high_risk_alignment_count": review_summary["failed_high_risk_alignment_count"],
        "reviewed_fallback_alignment_count": review_summary["reviewed_fallback_alignment_count"],
        "automatic_repairs_applied": int(repair_payload.get("summary", {}).get("automatic_correction_count", 0)),
        "curated_repairs_applied": int(repair_payload.get("summary", {}).get("curated_correction_count", 0)),
    }


def _copy_candidate_exports_to_active(work_id: str, batch_id: str | None = None) -> list[str]:
    """Copy candidate exports into the active export paths.

    For batch promotions, regenerate the corpus-level exports first (so corpus-level
    artifacts exist), then overwrite per-section active exports with the candidate
    per-section exports. This ensures per-section active files match the candidate
    while also keeping a regenerated corpus-level snapshot.

    Safety: never copy candidate per-section exports into the active tree for
    sections that the *active* manifest marks as metadata-only (tmx_status != 'complete').
    """
    copied: list[str] = []
    # Load the active manifest to guard against copying metadata-only sections
    active_manifest = load_work_manifest(work_id)
    active_sections_map = {str(s["section_id"]): s for s in active_manifest.get("sections", [])}

    if batch_id is None:
        # Full-corpus promotion: copy candidate corpus and per-section files directly
        for section in _scoped_manifest(work_id, batch_id)["sections"]:
            section_id = section["section_id"]
            active_section = active_sections_map.get(section_id, {})
            if active_section.get("tmx_status") != "complete":
                # Skip copying per-section exports for sections that are metadata-only in the active manifest
                continue
            candidate_paths = candidate_section_export_paths(section_id, work_id, batch_id)
            active_paths = section_export_paths(section_id, work_id)
            for key in ("jsonl", "csv", "tmx"):
                src = candidate_paths[key]
                if not src.exists():
                    continue
                shutil.copy2(src, active_paths[key])
                copied.append(repo_relative(active_paths[key]))
        candidate_corpus_paths = candidate_corpus_export_paths(work_id, batch_id)
        active_corpus_paths = corpus_export_paths(work_id)
        for key in ("jsonl", "csv", "tmx"):
            src = candidate_corpus_paths[key]
            if not src.exists():
                continue
            shutil.copy2(src, active_corpus_paths[key])
            copied.append(repo_relative(active_corpus_paths[key]))
    else:
        # Batch promotion: regenerate active corpus artifacts first, then overwrite
        # per-section exports with the approved candidate per-section files.
        active_export = export_corpus(DEFAULT_DB_PATH, work_id=work_id)
        for section in _scoped_manifest(work_id, batch_id)["sections"]:
            section_id = section["section_id"]
            active_section = active_sections_map.get(section_id, {})
            if active_section.get("tmx_status") != "complete":
                continue
            candidate_paths = candidate_section_export_paths(section_id, work_id, batch_id)
            active_paths = section_export_paths(section_id, work_id)
            for key in ("jsonl", "csv", "tmx"):
                src = candidate_paths[key]
                if not src.exists():
                    continue
                shutil.copy2(src, active_paths[key])
                copied.append(repo_relative(active_paths[key]))
        # Include regenerated corpus-level exports in the list for bookkeeping
        copied.append(active_export["jsonl_output"])
        copied.append(active_export["csv_output"])
        copied.append(active_export["tmx_output"])
    return copied


def promote_candidate(work_id: str, *, batch_id: str | None = None) -> dict[str, Any]:
    _require_batch_scope(work_id, batch_id)
    gate_summary = evaluate_promotion_gates(work_id, batch_id=batch_id)
    if not gate_summary["can_promote"]:
        update_candidate_state(work_id, gate_summary["next_state"], batch_id=batch_id, details={"blockers": gate_summary["blockers"]})
        raise ValueError("; ".join(gate_summary["blockers"]))
    copied_paths = _copy_candidate_exports_to_active(work_id, batch_id)
    active_qc = run_qc(DEFAULT_DB_PATH, work_id=work_id)
    comparison = compare_candidate_and_active_exports(
        work_id,
        batch_id=batch_id,
        candidate_qc=_load_json(candidate_qc_report_path(work_id, batch_id)),
        active_qc=active_qc,
    )
    if not comparison["matches"]:
        update_candidate_state(work_id, "candidate_qc_failed", batch_id=batch_id, details={"blockers": comparison["mismatches"]})
        raise ValueError("; ".join(comparison["mismatches"]))
    state = _active_state_for_manifest(load_work_manifest(work_id))
    update_candidate_state(work_id, state, batch_id=batch_id, details={"copied_paths": copied_paths, "comparison": comparison})
    return {"work_id": work_id, "batch_id": batch_id, "state": state, "copied_paths": copied_paths, "comparison": comparison}


def write_candidate_report(work_id: str, *, batch_id: str | None = None) -> dict[str, Any]:
    _require_batch_scope(work_id, batch_id)
    state = _load_candidate_state(work_id, batch_id)
    manifest = _scoped_manifest(work_id, batch_id)
    candidate_qc = _load_json(candidate_qc_report_path(work_id, batch_id))
    ai_reviews = _load_review_rows(candidate_ai_review_path(work_id, batch_id))
    ai_summary = summarize_reviews(ai_reviews)
    alignment_snapshot = _load_json(candidate_alignment_snapshot_path(work_id, batch_id))
    repair_log = _load_json(candidate_repair_log_path(work_id, batch_id))
    active_qc = _load_json(REPO_ROOT / "logs" / "qc_reports" / f"{work_id}__corpus_qc.json")
    active_alignment = _load_json(REPO_ROOT / "logs" / "qc_reports" / f"{work_id}__alignment_qc.json")
    gate_summary = evaluate_promotion_gates(
        work_id,
        batch_id=batch_id,
        candidate_qc=candidate_qc,
        ai_reviews=ai_reviews,
        alignment_snapshot=alignment_snapshot,
        repair_log=repair_log,
    )
    active_comparison = compare_candidate_and_active_exports(
        work_id,
        batch_id=batch_id,
        candidate_qc=candidate_qc,
        active_qc=active_qc,
        candidate_alignment_snapshot=alignment_snapshot,
        active_alignment_snapshot=active_alignment,
    )
    title = _scope_title(work_id, batch_id)
    lines = [
        f"# {title} candidate report",
        "",
        f"- Work id: {work_id}",
        f"- Batch id: {batch_id}" if batch_id else "- Batch id: none",
        f"- Current state: {state.get('current_state')}",
        f"- Candidate export root: `{repo_relative(candidate_work_dir(work_id, batch_id))}`",
        f"- Monolithic promotion occurred: {work_id == 'shiji' and batch_id is None}",
        f"- Deterministic QC status: {candidate_qc.get('status', 'missing')}",
        f"- Deterministic QC hard failures: {candidate_qc.get('hard_failure_count', 0)}",
        f"- Deterministic QC issue count: {candidate_qc.get('deterministic_issue_count', 0)}",
        f"- Alignment review method: heuristic high-risk review (entity sequence, succession formula, witness quality, and anchor order; no remote LLM reviewer used)",
        f"- Alignment review count: {ai_summary['review_count']}",
        f"- Alignment review failed high-risk alignments: {ai_summary['failed_high_risk_alignment_count']}",
        f"- Reviewed fallback alignments: {ai_summary['reviewed_fallback_alignment_count']}",
        f"- Named-entity drift reviews run: {ai_summary.get('review_count', 0)}",
        f"- Named-entity drift issues detected: {alignment_snapshot.get('summary', {}).get('drift_issue_count_before_repair', 0)}",
        f"- Named-entity drift issues repaired: {alignment_snapshot.get('summary', {}).get('repaired_drift_issue_count', 0)}",
        f"- Named-entity drift issues remaining: {alignment_snapshot.get('summary', {}).get('remaining_drift_issue_count', 0)}",
        f"- Shiji 003 succession sequence passed entity-order validation: {alignment_snapshot.get('summary', {}).get('entity_sequence_validation_passed', False)}",
        f"- Shiji witness-quality issues detected: {alignment_snapshot.get('summary', {}).get('pre_repair_witness_quality_issue_count', 0)}",
        f"- Shiji witness-quality issues repaired: {alignment_snapshot.get('summary', {}).get('repaired_witness_quality_issue_count', 0)}",
        f"- Shiji witness-quality issues remaining: {alignment_snapshot.get('summary', {}).get('remaining_witness_quality_issue_count', 0)}",
        f"- Name-gloss handling: {alignment_snapshot.get('summary', {}).get('witness_gloss_handling', 'not_reported')}",
        f"- Automatic repairs applied: {repair_log.get('summary', {}).get('automatic_correction_count', 0)}",
        f"- Curated repairs applied: {repair_log.get('summary', {}).get('curated_correction_count', 0)}",
        f"- Remaining OCR issues: {alignment_snapshot.get('summary', {}).get('remaining_corruption_issue_count', 0)}",
        f"- Remaining leakage issues: {alignment_snapshot.get('summary', {}).get('remaining_leakage_issue_count', 0)}",
        f"- Remaining drift issues: {alignment_snapshot.get('summary', {}).get('remaining_drift_issue_count', 0)}",
        f"- Promotion ready: {gate_summary['can_promote']}",
        f"- Promotion target state: {gate_summary['next_state']}",
        f"- Active corpus QC status: {active_qc.get('status', 'missing')}",
        f"- Candidate/active export agreement: {active_comparison['matches']}",
        "",
        "## Section status",
        "",
    ]
    for section in manifest["sections"]:
        if section.get("export_status") == "active":
            lines.append(f"- active `{section['section_id']}`")
        else:
            lines.append(f"- metadata-only `{section['section_id']}`: {section.get('blocker_note', section.get('fallback_reason', 'blocked'))}")
    lines.extend([
        "",
        "## Alignment review classifications",
        "",
    ])
    for classification, count in sorted(ai_summary["classification_counts"].items()):
        lines.append(f"- `{classification}`: {count}")
    lines.extend(["", "## Promotion blockers", ""])
    if gate_summary["blockers"]:
        lines.extend(f"- {blocker}" for blocker in gate_summary["blockers"])
    else:
        lines.append("- None")
    lines.extend(["", "## Candidate vs active agreement", ""])
    if active_comparison["mismatches"]:
        lines.extend(f"- {mismatch}" for mismatch in active_comparison["mismatches"])
    else:
        lines.append("- Candidate and active promoted exports match on counts and file content.")
    path = candidate_report_path(work_id, batch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"work_id": work_id, "batch_id": batch_id, "report_path": repo_relative(path), "can_promote": gate_summary["can_promote"]}


def run_ingestion_gauntlet(work_id: str, *, skip_fetch: bool = True, batch_id: str | None = None) -> dict[str, Any]:
    _require_batch_scope(work_id, batch_id)
    ingest_summary = ingest_candidate(work_id, skip_fetch=skip_fetch, batch_id=batch_id)
    candidate_qc = run_candidate_qc(work_id, batch_id=batch_id)
    ai_summary = run_candidate_ai_review(work_id, batch_id=batch_id)
    gate_summary = evaluate_promotion_gates(work_id, batch_id=batch_id)
    repaired = False
    if not gate_summary["can_promote"]:
        refine_candidate(work_id, skip_fetch=skip_fetch, batch_id=batch_id)
        repaired = True
        candidate_qc = run_candidate_qc(work_id, batch_id=batch_id)
        ai_summary = run_candidate_ai_review(work_id, batch_id=batch_id)
        gate_summary = evaluate_promotion_gates(work_id, batch_id=batch_id)
    if gate_summary["can_promote"]:
        promote_summary = promote_candidate(work_id, batch_id=batch_id)
    else:
        update_candidate_state(work_id, gate_summary["next_state"], batch_id=batch_id, details={"blockers": gate_summary["blockers"]})
        promote_summary = {"work_id": work_id, "batch_id": batch_id, "state": gate_summary["next_state"], "copied_paths": []}
    report_summary = write_candidate_report(work_id, batch_id=batch_id)
    return {
        "work_id": work_id,
        "batch_id": batch_id,
        "ingest": ingest_summary,
        "candidate_qc": {
            "status": candidate_qc["status"],
            "hard_failure_count": candidate_qc["hard_failure_count"],
            "deterministic_issue_count": candidate_qc["deterministic_issue_count"],
        },
        "ai_review": ai_summary,
        "repaired": repaired,
        "promotion_gate": gate_summary,
        "promotion": promote_summary,
        "candidate_report": report_summary,
        "current_state": _load_candidate_state(work_id, batch_id).get("current_state"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the candidate ingestion gauntlet for a work.")
    parser.add_argument("command", choices=("ingest", "qc", "ai-review", "refine", "promote", "run"))
    parser.add_argument("--work-id", default=DEFAULT_WORK_ID, help="Work identifier to process.")
    parser.add_argument("--batch-id", default=None, help="Optional batch identifier for batch-scoped candidate runs.")
    parser.add_argument("--skip-fetch", action="store_true", help="Reuse local captures instead of refetching.")
    args = parser.parse_args()

    if args.command == "ingest":
        result = ingest_candidate(args.work_id, skip_fetch=args.skip_fetch, batch_id=args.batch_id)
    elif args.command == "qc":
        result = run_candidate_qc(args.work_id, batch_id=args.batch_id)
    elif args.command == "ai-review":
        result = run_candidate_ai_review(args.work_id, batch_id=args.batch_id)
    elif args.command == "refine":
        result = refine_candidate(args.work_id, skip_fetch=args.skip_fetch, batch_id=args.batch_id)
    elif args.command == "promote":
        result = promote_candidate(args.work_id, batch_id=args.batch_id)
    else:
        result = run_ingestion_gauntlet(args.work_id, skip_fetch=args.skip_fetch, batch_id=args.batch_id)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
