from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from chinesenotes_alignment import find_anchor_drift_issues, load_alignment_anchor_maps
from common import (
    DEFAULT_WORK_ID,
    candidate_ai_review_path,
    candidate_corpus_export_paths,
    candidate_qc_report_path,
    candidate_repair_log_path,
    read_jsonl,
    write_jsonl,
)
from liji_quality import detect_liji_leakage_issues, detect_liji_ocr_issues
from mozi_ocr import detect_mozi_leakage_issues, detect_mozi_ocr_issues
from qc_corpus import _severe_ocr_issues

REPO_ROOT = Path(__file__).resolve().parent.parent
MOZI_ALIGNMENT_ANCHORS_PATH = REPO_ROOT / "metadata" / "mozi_alignment_anchors.yml"
FAILING_CLASSIFICATIONS = {"fail", "needs_regrouping", "note_leakage", "ocr_issue", "wrong_section", "semantic_drift"}
PASSING_CLASSIFICATIONS = {"pass", "too_coarse_but_usable", "fallback_justified"}


def _load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _english_word_count(text: str) -> int:
    return sum(1 for token in text.replace("’", "'").split() if any(character.isalpha() for character in token))


def _excerpt(text: str, *, limit: int = 180) -> str:
    normalized = " ".join(str(text).split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}…"


def _risk_alignment_ids(qc_report: dict[str, Any]) -> set[str]:
    if not qc_report:
        return set()
    alignment_quality = qc_report.get("alignment_quality", {})
    text_integrity = qc_report.get("text_integrity", {})
    risk_ids: set[str] = set()
    for key in (
        "false_precision_multi_clause_targets",
        "question_punctuation_mismatches",
        "suspicious_length_imbalance_rows",
        "non_grouped_segmentation_mismatch_rows",
        "translation_with_ocr_corruption_rows",
        "translation_with_truncated_fragment_rows",
        "translation_with_known_bad_forms_rows",
    ):
        for alignment_id in alignment_quality.get(key, []) + text_integrity.get(key, []):
            risk_ids.add(str(alignment_id))
    return risk_ids


def _sections_with_repairs(repair_log: dict[str, Any]) -> set[str]:
    return {
        str(repair["section_id"])
        for repair in repair_log.get("repairs", [])
        if repair.get("section_id")
    }


def _suspicious_length_ratio(row: dict[str, Any]) -> bool:
    chinese_text = str(row.get("chinese_text", ""))
    translation_text = str(row.get("translation_text", ""))
    chinese_chars = max(1, sum(1 for character in chinese_text if "\u3400" <= character <= "\u9fff"))
    english_words = max(1, _english_word_count(translation_text))
    ratio = english_words / chinese_chars
    source_segment_count = int(row.get("source_segment_count", 0) or 0)
    target_segment_count = int(row.get("target_segment_count", 0) or 0)
    return (
        (source_segment_count == 1 or target_segment_count == 1)
        and abs(target_segment_count - source_segment_count) >= 4
        and (ratio > 1.4 or ratio < 0.02)
    )


def _rows_by_section(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["section_id"]), []).append(row)
    for section_rows in grouped.values():
        section_rows.sort(key=lambda row: int(row.get("order", 0) or 0))
    return grouped


def _anchor_issue_map(work_id: str, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    if work_id != "mozi":
        return {}
    anchor_maps = load_alignment_anchor_maps(MOZI_ALIGNMENT_ANCHORS_PATH)
    issues_by_alignment_id: dict[str, list[dict[str, Any]]] = {}
    for section_id, section_rows in _rows_by_section(rows).items():
        anchor_map = anchor_maps.get(section_id)
        if not anchor_map:
            continue
        issues = find_anchor_drift_issues(section_rows, list(anchor_map.get("anchors", [])))
        for issue in issues:
            candidate_ids: list[str] = []
            candidate_ids.extend(str(alignment_id) for alignment_id in issue.get("matching_alignment_ids", []) if alignment_id)
            for key in ("source_alignment_id", "target_alignment_id"):
                if issue.get(key):
                    candidate_ids.append(str(issue[key]))
            for alignment_id in sorted(set(candidate_ids)):
                issues_by_alignment_id.setdefault(alignment_id, []).append(issue)
    return issues_by_alignment_id


def _row_anchor_orders(work_id: str, rows: list[dict[str, Any]]) -> dict[str, dict[str, list[int]]]:
    if work_id != "mozi":
        return {}
    anchor_maps = load_alignment_anchor_maps(MOZI_ALIGNMENT_ANCHORS_PATH)
    by_alignment_id: dict[str, dict[str, list[int]]] = {}
    for row in rows:
        section_id = str(row["section_id"])
        anchor_map = anchor_maps.get(section_id)
        if not anchor_map:
            continue
        chinese_text = str(row.get("chinese_text", ""))
        translation_text = str(row.get("translation_text", ""))
        source_orders: list[int] = []
        target_orders: list[int] = []
        for anchor in anchor_map.get("anchors", []):
            expected_order = int(anchor["expected_order"])
            source_terms = list(anchor.get("source_required_terms") or [])
            target_terms = list(anchor.get("target_required_terms") or [])
            if source_terms and all(term in chinese_text for term in source_terms):
                source_orders.append(expected_order)
            if target_terms and all(term.lower() in translation_text.lower() for term in target_terms):
                target_orders.append(expected_order)
        by_alignment_id[str(row["alignment_id"])] = {
            "source_orders": source_orders,
            "target_orders": target_orders,
        }
    return by_alignment_id


def _candidate_sample_alignment_ids(
    rows: list[dict[str, Any]],
    *,
    risk_alignment_ids: set[str],
    reviewed_sections: set[str],
    sample_size: int,
    seed: int,
) -> set[str]:
    rows_by_section = _rows_by_section(rows)
    selected_ids: set[str] = set()
    for section_rows in rows_by_section.values():
        if not section_rows:
            continue
        selected_ids.add(str(section_rows[0]["alignment_id"]))
        selected_ids.add(str(section_rows[-1]["alignment_id"]))
    for row in rows:
        alignment_id = str(row["alignment_id"])
        section_id = str(row["section_id"])
        if section_id in reviewed_sections:
            selected_ids.add(alignment_id)
        if row.get("is_coarse_alignment"):
            selected_ids.add(alignment_id)
        if alignment_id in risk_alignment_ids:
            selected_ids.add(alignment_id)
        if _suspicious_length_ratio(row):
            selected_ids.add(alignment_id)
    remaining = [str(row["alignment_id"]) for row in rows if str(row["alignment_id"]) not in selected_ids]
    if remaining:
        rng = random.Random(seed)
        selected_ids.update(rng.sample(remaining, min(sample_size, len(remaining))))
    return selected_ids


def classify_alignment_review(
    row: dict[str, Any],
    *,
    risk_alignment_ids: set[str],
    repaired_sections: set[str],
    priority_sections: set[str],
    anchor_issue_map: dict[str, list[dict[str, Any]]],
    row_anchor_orders: dict[str, dict[str, list[int]]],
) -> dict[str, Any]:
    alignment_id = str(row["alignment_id"])
    section_id = str(row["section_id"])
    translation_text = str(row.get("translation_text", ""))
    risk_reasons: list[str] = []
    if row.get("is_coarse_alignment"):
        risk_reasons.append("coarse_fallback")
    if alignment_id in risk_alignment_ids:
        risk_reasons.append("deterministic_qc_flag")
    if _suspicious_length_ratio(row):
        risk_reasons.append("suspicious_length_ratio")
    if section_id in repaired_sections:
        risk_reasons.append("section_with_repairs")
    if section_id in priority_sections:
        risk_reasons.append("priority_section_review")
    leakage_issues: list[dict[str, str]] = []
    ocr_issues: list[dict[str, str]] = []
    if section_id.startswith("mozi-"):
        leakage_issues = detect_mozi_leakage_issues(translation_text)
        ocr_issues = detect_mozi_ocr_issues(translation_text)
    elif section_id.startswith("liji-"):
        leakage_issues = detect_liji_leakage_issues(translation_text)
        ocr_issues = detect_liji_ocr_issues(translation_text)
    severe_issues = _severe_ocr_issues(translation_text) if section_id.startswith("mozi-") else []
    anchor_issues = anchor_issue_map.get(alignment_id, [])
    for issue in anchor_issues:
        risk_reasons.append(f"anchor:{issue['anchor_id']}:{issue['issue']}")

    anchor_orders = row_anchor_orders.get(alignment_id, {"source_orders": [], "target_orders": []})
    if anchor_orders["source_orders"] and anchor_orders["target_orders"]:
        source_min = min(anchor_orders["source_orders"])
        source_max = max(anchor_orders["source_orders"])
        target_min = min(anchor_orders["target_orders"])
        target_max = max(anchor_orders["target_orders"])
        if target_min < source_min or target_max > source_max:
            risk_reasons.append(
                f"anchor_range_mismatch:source={anchor_orders['source_orders']}:target={anchor_orders['target_orders']}"
            )

    classification = "pass"
    repair_suggestion = "No repair needed."
    if leakage_issues:
        classification = "note_leakage"
        repair_suggestion = "Separate footnotes/commentary from the translation stream, then regroup and re-export the section."
    elif ocr_issues or severe_issues:
        classification = "ocr_issue"
        repair_suggestion = "Apply deterministic OCR repairs to the flagged tokens and regenerate the candidate export."
    elif anchor_issues or any(reason.startswith("anchor_range_mismatch:") for reason in risk_reasons):
        classification = "semantic_drift"
        repair_suggestion = "Regroup the affected source and target units or apply a curated override that restores anchor order."
    elif row.get("is_coarse_alignment"):
        coarse_reason = str(row.get("coarse_alignment_reason", "") or "")
        if coarse_reason:
            classification = "fallback_justified"
            repair_suggestion = "Retain the fallback, but keep the recorded justification with the promotion report."
        else:
            classification = "too_coarse_but_usable"
            repair_suggestion = "Record an explicit fallback justification before promotion."
    elif alignment_id in risk_alignment_ids:
        classification = "needs_regrouping"
        repair_suggestion = "Regroup the alignment around clause boundaries and re-run deterministic QC."

    high_risk = bool(risk_reasons) or classification in FAILING_CLASSIFICATIONS or bool(row.get("is_coarse_alignment"))
    if classification == "ocr_issue":
        explanation = (
            f"Flagged for OCR corruption because the English excerpt still shows "
            f"{', '.join(sorted({*(issue['issue_type'] for issue in ocr_issues), *severe_issues}))}."
        )
    elif classification == "note_leakage":
        explanation = (
            f"Flagged for note leakage because the English excerpt still shows "
            f"{', '.join(sorted({issue['issue_type'] for issue in leakage_issues}))}."
        )
    elif classification == "semantic_drift":
        anchor_summary = ", ".join(sorted(set(risk_reasons))) or "anchor ordering drift"
        explanation = f"Flagged for semantic drift because the source/target anchor cues do not stay in the same order ({anchor_summary})."
    elif classification == "fallback_justified":
        explanation = (
            "Reviewed chapter-level fallback passed: no obvious OCR corruption, note leakage, or drift remains, "
            f"and finer grouping is still unsafe because {str(row.get('coarse_alignment_reason') or '').strip()}."
        )
    elif classification == "too_coarse_but_usable":
        explanation = "The fallback text itself looks coherent, but promotion still needs an explicit recorded reason for why finer grouping is unsafe."
    elif classification == "needs_regrouping":
        explanation = (
            f"Flagged for regrouping because deterministic QC still marked this alignment high-risk "
            f"({', '.join(sorted(set(risk_reasons)))})."
        )
    else:
        review_basis = ", ".join(sorted(set(risk_reasons))) if risk_reasons else "deterministic sample"
        explanation = (
            f"Reviewed because this alignment is high-risk by {review_basis}. "
            "No obvious OCR corruption, note leakage, or anchor drift is visible in the inspected excerpts."
        )
    return {
        "work_id": str(row["work_id"]),
        "section_id": section_id,
        "alignment_id": alignment_id,
        "classification": classification,
        "review_method": "heuristic_rule_based",
        "high_risk": high_risk,
        "risk_reasons": sorted(set(risk_reasons)),
        "high_risk_reason_summary": ", ".join(sorted(set(risk_reasons))) if risk_reasons else "deterministic sample",
        "review_explanation": explanation,
        "repair_suggestion": repair_suggestion,
        "chinese_excerpt": _excerpt(str(row.get("chinese_text", ""))),
        "translation_excerpt": _excerpt(translation_text),
        "source_segment_count": int(row.get("source_segment_count", 0) or 0),
        "target_segment_count": int(row.get("target_segment_count", 0) or 0),
        "is_coarse_alignment": bool(row.get("is_coarse_alignment")),
        "coarse_alignment_reason": row.get("coarse_alignment_reason"),
        "detected_ocr_issue_types": sorted(
            {
                *(str(issue["issue_type"]) for issue in leakage_issues),
                *(str(issue["issue_type"]) for issue in ocr_issues),
                *severe_issues,
            }
        ),
    }


def review_alignment_rows(
    work_id: str,
    rows: list[dict[str, Any]],
    *,
    qc_report: dict[str, Any] | None = None,
    repair_log: dict[str, Any] | None = None,
    sample_size: int = 12,
    seed: int = 17,
) -> list[dict[str, Any]]:
    qc_payload = qc_report or {}
    repair_payload = repair_log or {}
    risk_alignment_ids = _risk_alignment_ids(qc_payload)
    repaired_sections = _sections_with_repairs(repair_payload)
    anchor_issue_map = _anchor_issue_map(work_id, rows)
    row_anchor_orders = _row_anchor_orders(work_id, rows)
    reviewed_sections = set(repaired_sections)
    if work_id == "mozi":
        reviewed_sections.update({"mozi-001-make-close-the-scholars", "mozi-003-that-which-is-affectable"})
    if work_id == "liji":
        reviewed_sections.update(
            {
                "liji-001-summary-of-the-rules-of-propriety-part-1",
                "liji-003-tan-gong-i",
                "liji-015-record-of-small-matters-in-the-dress-of",
                "liji-019-record-of-music",
                "liji-031-the-state-of-equilibrium-and-harmony",
                "liji-042-the-great-learning",
            }
        )
    if work_id == "shiji":
        reviewed_sections.update({str(row["section_id"]) for row in rows})
    selected_ids = _candidate_sample_alignment_ids(
        rows,
        risk_alignment_ids=risk_alignment_ids | set(anchor_issue_map),
        reviewed_sections=reviewed_sections,
        sample_size=sample_size,
        seed=seed,
    )
    reviews: list[dict[str, Any]] = []
    for row in rows:
        alignment_id = str(row["alignment_id"])
        if alignment_id not in selected_ids:
            continue
        reviews.append(
            classify_alignment_review(
                row,
                risk_alignment_ids=risk_alignment_ids,
                repaired_sections=repaired_sections,
                priority_sections=reviewed_sections,
                anchor_issue_map=anchor_issue_map,
                row_anchor_orders=row_anchor_orders,
            )
        )
    return reviews


def summarize_reviews(reviews: list[dict[str, Any]]) -> dict[str, Any]:
    classification_counts: dict[str, int] = {}
    failed_high_risk = 0
    reviewed_fallbacks = 0
    for review in reviews:
        classification = str(review["classification"])
        classification_counts[classification] = classification_counts.get(classification, 0) + 1
        if classification in {"fallback_justified", "too_coarse_but_usable"}:
            reviewed_fallbacks += 1
        if review["high_risk"] and classification in FAILING_CLASSIFICATIONS:
            failed_high_risk += 1
    return {
        "review_method": "heuristic_rule_based",
        "heuristic_only": True,
        "review_count": len(reviews),
        "classification_counts": classification_counts,
        "failed_high_risk_alignment_count": failed_high_risk,
        "reviewed_fallback_alignment_count": reviewed_fallbacks,
    }


def review_candidate_alignments(
    work_id: str,
    *,
    input_jsonl: Path | None = None,
    output_path: Path | None = None,
    qc_report_path: Path | None = None,
    repair_log_path: Path | None = None,
    sample_size: int = 12,
    seed: int = 17,
) -> dict[str, Any]:
    input_path = input_jsonl or candidate_corpus_export_paths(work_id)["jsonl"]
    output = output_path or candidate_ai_review_path(work_id)
    rows = read_jsonl(input_path)
    qc_report = _load_json(qc_report_path or candidate_qc_report_path(work_id))
    repair_log = _load_json(repair_log_path or candidate_repair_log_path(work_id))
    reviews = review_alignment_rows(
        work_id,
        rows,
        qc_report=qc_report,
        repair_log=repair_log,
        sample_size=sample_size,
        seed=seed,
    )
    write_jsonl(output, reviews)
    summary = summarize_reviews(reviews)
    return {
        "work_id": work_id,
        "input_jsonl": str(input_path),
        "output_path": str(output),
        **summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Review candidate alignments and emit machine-readable semantic review results.")
    parser.add_argument("--work-id", default=DEFAULT_WORK_ID, help="Work identifier to review.")
    parser.add_argument("--input-jsonl", default=None, help="Candidate JSONL export to review.")
    parser.add_argument("--output", default=None, help="Where to write the alignment review JSONL.")
    parser.add_argument("--qc-report", default=None, help="Candidate QC report JSON.")
    parser.add_argument("--repair-log", default=None, help="Candidate OCR repair log JSON.")
    parser.add_argument("--sample-size", type=int, default=12, help="Number of otherwise clean sampled alignments to review.")
    parser.add_argument("--seed", type=int, default=17, help="Deterministic seed for the clean-alignment sample.")
    args = parser.parse_args()
    summary = review_candidate_alignments(
        args.work_id,
        input_jsonl=Path(args.input_jsonl) if args.input_jsonl else None,
        output_path=Path(args.output) if args.output else None,
        qc_report_path=Path(args.qc_report) if args.qc_report else None,
        repair_log_path=Path(args.repair_log) if args.repair_log else None,
        sample_size=args.sample_size,
        seed=args.seed,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
