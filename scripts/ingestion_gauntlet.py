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
    load_sources,
    load_work_manifest,
    manifest_sections,
    repo_relative,
    section_export_paths,
    sha256_file,
    utc_now_iso,
    write_json,
)
from export_corpus import load_exact_alignment_rows, write_tabular_exports, write_tmx
from import_corpus import import_corpus
from qc_corpus import run_alignment_quality_checks, run_source_traceability_checks, run_text_integrity_checks
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


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_review_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None or not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _candidate_snapshot_paths(work_id: str) -> dict[str, Path]:
    root = candidate_work_dir(work_id)
    return {
        "manifest": root / "metadata" / f"{work_id}.yml",
        "alignment_qc": candidate_alignment_snapshot_path(work_id),
        "repair_log": candidate_repair_log_path(work_id),
    }


def _active_state_for_manifest(manifest: dict[str, Any]) -> str:
    if str(manifest.get("release_status", "")) == "cleared":
        return "active_release_ready"
    return "active_proof_of_concept"


def _load_candidate_state(work_id: str) -> dict[str, Any]:
    path = candidate_state_path(work_id)
    if not path.exists():
        return {"work_id": work_id, "current_state": None, "history": []}
    return json.loads(path.read_text(encoding="utf-8"))


def update_candidate_state(work_id: str, state: str, *, details: dict[str, Any] | None = None) -> dict[str, Any]:
    if state not in CANDIDATE_STATES:
        raise ValueError(f"Unsupported candidate state: {state}")
    payload = _load_candidate_state(work_id)
    payload["work_id"] = work_id
    payload["current_state"] = state
    payload.setdefault("history", []).append(
        {
            "state": state,
            "timestamp": utc_now_iso(),
            "details": details or {},
        }
    )
    write_json(candidate_state_path(work_id), payload)
    return payload


def _reset_candidate_workspace(work_id: str) -> None:
    root = candidate_work_dir(work_id)
    root.mkdir(parents=True, exist_ok=True)
    for name in ("exports", "reports", "repair_logs", "metadata"):
        shutil.rmtree(root / name, ignore_errors=True)


def _copy_if_exists(source: Path, destination: Path) -> None:
    if not source.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _snapshot_candidate_inputs(work_id: str) -> dict[str, str]:
    snapshots = _candidate_snapshot_paths(work_id)
    manifest_path = REPO_ROOT / "metadata" / "manifests" / f"{work_id}.yml"
    alignment_qc_path = REPO_ROOT / "logs" / "qc_reports" / f"{work_id}__alignment_qc.json"
    repair_log_path = REPO_ROOT / "logs" / "qc_reports" / f"{work_id}__ocr_repair_log.json"
    _copy_if_exists(manifest_path, snapshots["manifest"])
    _copy_if_exists(alignment_qc_path, snapshots["alignment_qc"])
    _copy_if_exists(repair_log_path, snapshots["repair_log"])
    return {key: repo_relative(path) for key, path in snapshots.items() if path.exists()}


def write_candidate_exports(work_id: str, *, db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, Any]:
    root_paths = candidate_corpus_export_paths(work_id)
    per_section: list[dict[str, Any]] = []
    for section in manifest_sections(work_id):
        if section.get("tmx_status", "complete") != "complete":
            continue
        rows = load_exact_alignment_rows(db_path, work_id, section["section_id"])
        paths = candidate_section_export_paths(section["section_id"], work_id)
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
    corpus_rows = load_exact_alignment_rows(db_path, work_id)
    write_tabular_exports(corpus_rows, root_paths["jsonl"], root_paths["csv"])
    write_tmx(corpus_rows, root_paths["tmx"], work_id=work_id)
    corpus_validation = validate_tmx_file(db_path, root_paths["tmx"], root_paths["tmx_validation"], work_id=work_id)
    return {
        "work_id": work_id,
        "rows_exported": len(corpus_rows),
        "section_count": len(per_section),
        "jsonl_output": repo_relative(root_paths["jsonl"]),
        "csv_output": repo_relative(root_paths["csv"]),
        "tmx_output": repo_relative(root_paths["tmx"]),
        "tmx_validation_output": repo_relative(root_paths["tmx_validation"]),
        "sections": per_section,
        "corpus_tmx_status": corpus_validation["status"],
    }


def ingest_candidate(work_id: str, *, skip_fetch: bool = True) -> dict[str, Any]:
    _reset_candidate_workspace(work_id)
    bootstrap_summary = bootstrap_all_manifests(skip_fetch=skip_fetch)
    bootstrap_work_summary = next(
        work_summary["summary"] for work_summary in bootstrap_summary["works"] if work_summary["work_id"] == work_id
    )
    import_summary = import_corpus(DEFAULT_DB_PATH)
    export_summary = write_candidate_exports(work_id, db_path=DEFAULT_DB_PATH)
    snapshots = _snapshot_candidate_inputs(work_id)
    state = update_candidate_state(
        work_id,
        "candidate_ingested",
        details={
            "bootstrap_summary": bootstrap_work_summary,
            "candidate_export": export_summary,
        },
    )
    return {
        "work_id": work_id,
        "state": state["current_state"],
        "bootstrap_summary": bootstrap_work_summary,
        "import_summary": import_summary["work_summaries"][work_id]["summary"],
        "candidate_export": export_summary,
        "snapshots": snapshots,
    }


def _candidate_rows_by_section(work_id: str) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    corpus_rows = [
        dict(row)
        for row in _load_review_rows(candidate_corpus_export_paths(work_id)["jsonl"])
    ]
    rows_by_section: dict[str, list[dict[str, Any]]] = {}
    for row in corpus_rows:
        rows_by_section.setdefault(str(row["section_id"]), []).append(row)
    return corpus_rows, rows_by_section


def run_candidate_qc(work_id: str, *, db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, Any]:
    manifest = load_work_manifest(work_id)
    corpus_rows, rows_by_section = _candidate_rows_by_section(work_id)
    with connect_db(db_path) as connection:
        counts = {
            "works": connection.execute("SELECT COUNT(*) FROM works WHERE work_id = ?", (work_id,)).fetchone()[0],
            "sections": connection.execute("SELECT COUNT(*) FROM sections WHERE work_id = ?", (work_id,)).fetchone()[0],
            "persons": connection.execute("SELECT COUNT(*) FROM persons").fetchone()[0],
            "sources": connection.execute("SELECT COUNT(*) FROM sources WHERE work_id = ?", (work_id,)).fetchone()[0],
            "segments": connection.execute("SELECT COUNT(*) FROM segments WHERE work_id = ?", (work_id,)).fetchone()[0],
            "alignments": connection.execute("SELECT COUNT(*) FROM alignments WHERE work_id = ?", (work_id,)).fetchone()[0],
            "exact_alignment_records": connection.execute(
                "SELECT COUNT(*) FROM alignments WHERE work_id = ? AND alignment_type = 'exact_or_near_exact'",
                (work_id,),
            ).fetchone()[0],
            "section_group_alignment_records": connection.execute(
                "SELECT COUNT(*) FROM alignments WHERE work_id = ? AND alignment_type = 'section_group'",
                (work_id,),
            ).fetchone()[0],
        }
        section_reports: list[dict[str, Any]] = []
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
    source_traceability = run_source_traceability_checks(work_id)
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
    for section in manifest_sections(work_id):
        if section.get("tmx_status") != "complete":
            continue
        candidate_paths.extend(path for path in candidate_section_export_paths(section["section_id"], work_id).values() if path.exists())
    candidate_paths.extend(path for path in candidate_corpus_export_paths(work_id).values() if path.exists())
    snapshot_paths = [path for path in _candidate_snapshot_paths(work_id).values() if path.exists()]
    report = {
        "status": overall_status,
        "work_id": work_id,
        "candidate_export_root": repo_relative(candidate_work_dir(work_id)),
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
            details={"hard_failure_count": report["hard_failure_count"]},
        )
    write_json(candidate_qc_report_path(work_id), report)
    return report


def run_candidate_ai_review(work_id: str) -> dict[str, Any]:
    summary = review_candidate_alignments(work_id)
    if summary["failed_high_risk_alignment_count"]:
        update_candidate_state(
            work_id,
            "candidate_qc_failed",
            details={"failed_high_risk_alignment_count": summary["failed_high_risk_alignment_count"]},
        )
    return summary


def refine_candidate(work_id: str, *, skip_fetch: bool = True) -> dict[str, Any]:
    summary = ingest_candidate(work_id, skip_fetch=skip_fetch)
    update_candidate_state(
        work_id,
        "candidate_repaired",
        details={"candidate_export_rows": summary["candidate_export"]["rows_exported"]},
    )
    return summary


def evaluate_promotion_gates(
    work_id: str,
    *,
    candidate_qc: dict[str, Any] | None = None,
    ai_reviews: list[dict[str, Any]] | None = None,
    alignment_snapshot: dict[str, Any] | None = None,
    repair_log: dict[str, Any] | None = None,
    manifest: dict[str, Any] | None = None,
    candidate_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    qc_report = candidate_qc or _load_json(candidate_qc_report_path(work_id))
    review_rows = ai_reviews or _load_review_rows(candidate_ai_review_path(work_id))
    alignment_payload = alignment_snapshot or _load_json(candidate_alignment_snapshot_path(work_id))
    repair_payload = repair_log or _load_json(candidate_repair_log_path(work_id))
    current_manifest = manifest or load_work_manifest(work_id)
    rows = candidate_rows or _load_review_rows(candidate_corpus_export_paths(work_id)["jsonl"])
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
    if review_summary["failed_high_risk_alignment_count"]:
        blockers.append(f"AI review found {review_summary['failed_high_risk_alignment_count']} failed high-risk alignments")
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
        "can_promote": not blockers,
        "next_state": state,
        "blockers": blockers,
        "failed_high_risk_alignment_count": review_summary["failed_high_risk_alignment_count"],
        "reviewed_fallback_alignment_count": review_summary["reviewed_fallback_alignment_count"],
        "automatic_repairs_applied": int(repair_payload.get("summary", {}).get("automatic_correction_count", 0)),
        "curated_repairs_applied": int(repair_payload.get("summary", {}).get("curated_correction_count", 0)),
    }


def _copy_candidate_exports_to_active(work_id: str) -> list[str]:
    copied: list[str] = []
    for section in manifest_sections(work_id):
        if section.get("tmx_status") != "complete":
            continue
        candidate_paths = candidate_section_export_paths(section["section_id"], work_id)
        active_paths = section_export_paths(section["section_id"], work_id)
        for key in ("jsonl", "csv", "tmx"):
            shutil.copy2(candidate_paths[key], active_paths[key])
            copied.append(repo_relative(active_paths[key]))
    candidate_corpus_paths = candidate_corpus_export_paths(work_id)
    active_corpus_paths = corpus_export_paths(work_id)
    for key in ("jsonl", "csv", "tmx"):
        shutil.copy2(candidate_corpus_paths[key], active_corpus_paths[key])
        copied.append(repo_relative(active_corpus_paths[key]))
    return copied


def promote_candidate(work_id: str) -> dict[str, Any]:
    gate_summary = evaluate_promotion_gates(work_id)
    if not gate_summary["can_promote"]:
        update_candidate_state(work_id, gate_summary["next_state"], details={"blockers": gate_summary["blockers"]})
        raise ValueError("; ".join(gate_summary["blockers"]))
    copied_paths = _copy_candidate_exports_to_active(work_id)
    state = _active_state_for_manifest(load_work_manifest(work_id))
    update_candidate_state(work_id, state, details={"copied_paths": copied_paths})
    return {"work_id": work_id, "state": state, "copied_paths": copied_paths}


def write_candidate_report(work_id: str) -> dict[str, Any]:
    state = _load_candidate_state(work_id)
    candidate_qc = _load_json(candidate_qc_report_path(work_id))
    ai_reviews = _load_review_rows(candidate_ai_review_path(work_id))
    ai_summary = summarize_reviews(ai_reviews)
    alignment_snapshot = _load_json(candidate_alignment_snapshot_path(work_id))
    repair_log = _load_json(candidate_repair_log_path(work_id))
    gate_summary = evaluate_promotion_gates(
        work_id,
        candidate_qc=candidate_qc,
        ai_reviews=ai_reviews,
        alignment_snapshot=alignment_snapshot,
        repair_log=repair_log,
    )
    lines = [
        f"# {work_id} candidate report",
        "",
        f"- Current state: {state.get('current_state')}",
        f"- Candidate export root: `{repo_relative(candidate_work_dir(work_id))}`",
        f"- Deterministic QC status: {candidate_qc.get('status', 'missing')}",
        f"- Deterministic QC hard failures: {candidate_qc.get('hard_failure_count', 0)}",
        f"- Deterministic QC issue count: {candidate_qc.get('deterministic_issue_count', 0)}",
        f"- AI review count: {ai_summary['review_count']}",
        f"- AI failed high-risk alignments: {ai_summary['failed_high_risk_alignment_count']}",
        f"- Reviewed fallback alignments: {ai_summary['reviewed_fallback_alignment_count']}",
        f"- Automatic repairs applied: {repair_log.get('summary', {}).get('automatic_correction_count', 0)}",
        f"- Curated repairs applied: {repair_log.get('summary', {}).get('curated_correction_count', 0)}",
        f"- Remaining OCR issues: {alignment_snapshot.get('summary', {}).get('remaining_corruption_issue_count', 0)}",
        f"- Remaining leakage issues: {alignment_snapshot.get('summary', {}).get('remaining_leakage_issue_count', 0)}",
        f"- Remaining drift issues: {alignment_snapshot.get('summary', {}).get('remaining_drift_issue_count', 0)}",
        f"- Promotion ready: {gate_summary['can_promote']}",
        "",
        "## AI review classifications",
        "",
    ]
    for classification, count in sorted(ai_summary["classification_counts"].items()):
        lines.append(f"- `{classification}`: {count}")
    lines.extend(["", "## Promotion blockers", ""])
    if gate_summary["blockers"]:
        lines.extend(f"- {blocker}" for blocker in gate_summary["blockers"])
    else:
        lines.append("- None")
    path = candidate_report_path(work_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"work_id": work_id, "report_path": repo_relative(path), "can_promote": gate_summary["can_promote"]}


def run_ingestion_gauntlet(work_id: str, *, skip_fetch: bool = True) -> dict[str, Any]:
    ingest_summary = ingest_candidate(work_id, skip_fetch=skip_fetch)
    candidate_qc = run_candidate_qc(work_id)
    ai_summary = run_candidate_ai_review(work_id)
    gate_summary = evaluate_promotion_gates(work_id)
    repaired = False
    if not gate_summary["can_promote"]:
        refine_candidate(work_id, skip_fetch=skip_fetch)
        repaired = True
        candidate_qc = run_candidate_qc(work_id)
        ai_summary = run_candidate_ai_review(work_id)
        gate_summary = evaluate_promotion_gates(work_id)
    if gate_summary["can_promote"]:
        promote_summary = promote_candidate(work_id)
    else:
        update_candidate_state(work_id, gate_summary["next_state"], details={"blockers": gate_summary["blockers"]})
        promote_summary = {"work_id": work_id, "state": gate_summary["next_state"], "copied_paths": []}
    report_summary = write_candidate_report(work_id)
    return {
        "work_id": work_id,
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
        "current_state": _load_candidate_state(work_id).get("current_state"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the candidate ingestion gauntlet for a work.")
    parser.add_argument("command", choices=("ingest", "qc", "ai-review", "refine", "promote", "run"))
    parser.add_argument("--work-id", default=DEFAULT_WORK_ID, help="Work identifier to process.")
    parser.add_argument("--skip-fetch", action="store_true", help="Reuse local captures instead of refetching.")
    args = parser.parse_args()

    if args.command == "ingest":
        result = ingest_candidate(args.work_id, skip_fetch=args.skip_fetch)
    elif args.command == "qc":
        result = run_candidate_qc(args.work_id)
    elif args.command == "ai-review":
        result = run_candidate_ai_review(args.work_id)
    elif args.command == "refine":
        result = refine_candidate(args.work_id, skip_fetch=args.skip_fetch)
    elif args.command == "promote":
        result = promote_candidate(args.work_id)
    else:
        result = run_ingestion_gauntlet(args.work_id, skip_fetch=args.skip_fetch)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
