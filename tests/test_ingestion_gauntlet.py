from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from ai_review_alignments import review_alignment_rows
from common import (
    candidate_ai_review_path,
    candidate_corpus_export_paths,
    candidate_qc_report_path,
    candidate_report_path,
    corpus_export_paths,
)
from ingestion_gauntlet import evaluate_promotion_gates


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class IngestionGauntletTest(unittest.TestCase):
    def test_candidate_outputs_are_separate_from_active_exports(self) -> None:
        active_paths = corpus_export_paths("mozi")
        candidate_paths = candidate_corpus_export_paths("mozi")

        self.assertNotEqual(candidate_paths["jsonl"], active_paths["jsonl"])
        self.assertNotEqual(candidate_paths["csv"], active_paths["csv"])
        self.assertNotEqual(candidate_paths["tmx"], active_paths["tmx"])
        self.assertIn("/corpus/candidates/mozi/", str(candidate_paths["jsonl"]))
        self.assertEqual(candidate_qc_report_path("mozi").name, "mozi__candidate_qc.json")
        self.assertEqual(candidate_ai_review_path("mozi").name, "mozi__alignment_review.jsonl")
        self.assertEqual(candidate_report_path("mozi").name, "mozi_candidate_report.md")

    def test_promotion_fails_if_candidate_qc_has_hard_failures(self) -> None:
        gate = evaluate_promotion_gates(
            "fixture-work",
            candidate_qc={
                "hard_failure_count": 2,
                "counts": {"alignments": 2, "section_group_alignment_records": 1},
                "source_traceability": {"hard_failure_count": 0},
                "alignment_quality": {"line_order_issues": []},
                "count_disagreement_errors": [],
            },
            ai_reviews=[
                {"alignment_id": "fixture-work__align-0001", "classification": "fallback_justified", "high_risk": True}
            ],
            alignment_snapshot={"summary": {"remaining_corruption_issue_count": 0, "remaining_leakage_issue_count": 0, "remaining_drift_issue_count": 0}},
            repair_log={"summary": {"automatic_correction_count": 0, "curated_correction_count": 0}},
            manifest={"summary": {"exact_alignment_count": 1, "alignment_record_count": 2, "section_group_alignment_record_count": 1, "active_section_count": 1}, "release_status": "not_cleared"},
            candidate_rows=[{"alignment_id": "fixture-work__align-0001", "is_coarse_alignment": True, "coarse_alignment_reason": "Reviewed fallback"}],
        )
        self.assertFalse(gate["can_promote"])
        self.assertTrue(any("deterministic candidate QC" in blocker for blocker in gate["blockers"]))

    def test_promotion_fails_if_ai_review_has_failed_high_risk_alignments(self) -> None:
        gate = evaluate_promotion_gates(
            "fixture-work",
            candidate_qc={
                "hard_failure_count": 0,
                "counts": {"alignments": 2, "section_group_alignment_records": 1},
                "source_traceability": {"hard_failure_count": 0},
                "alignment_quality": {"line_order_issues": []},
                "count_disagreement_errors": [],
            },
            ai_reviews=[
                {"alignment_id": "fixture-work__align-0001", "classification": "semantic_drift", "high_risk": True}
            ],
            alignment_snapshot={"summary": {"remaining_corruption_issue_count": 0, "remaining_leakage_issue_count": 0, "remaining_drift_issue_count": 0}},
            repair_log={"summary": {"automatic_correction_count": 0, "curated_correction_count": 0}},
            manifest={"summary": {"exact_alignment_count": 1, "alignment_record_count": 2, "section_group_alignment_record_count": 1, "active_section_count": 1}, "release_status": "not_cleared"},
            candidate_rows=[{"alignment_id": "fixture-work__align-0001", "is_coarse_alignment": False, "coarse_alignment_reason": ""}],
        )
        self.assertFalse(gate["can_promote"])
        self.assertTrue(any("AI review found" in blocker for blocker in gate["blockers"]))

    def test_promotion_requires_explicit_fallback_review(self) -> None:
        gate = evaluate_promotion_gates(
            "fixture-work",
            candidate_qc={
                "hard_failure_count": 0,
                "counts": {"alignments": 2, "section_group_alignment_records": 1},
                "source_traceability": {"hard_failure_count": 0},
                "alignment_quality": {"line_order_issues": []},
                "count_disagreement_errors": [],
            },
            ai_reviews=[],
            alignment_snapshot={"summary": {"remaining_corruption_issue_count": 0, "remaining_leakage_issue_count": 0, "remaining_drift_issue_count": 0}},
            repair_log={"summary": {"automatic_correction_count": 0, "curated_correction_count": 0}},
            manifest={"summary": {"exact_alignment_count": 1, "alignment_record_count": 2, "section_group_alignment_record_count": 1, "active_section_count": 1}, "release_status": "not_cleared"},
            candidate_rows=[{"alignment_id": "fixture-work__align-0001", "is_coarse_alignment": True, "coarse_alignment_reason": "Chapter fallback"}],
        )
        self.assertFalse(gate["can_promote"])
        self.assertTrue(any("fallback alignments lack reviewed justification" in blocker for blocker in gate["blockers"]))

    def test_promotion_succeeds_when_deterministic_qc_and_ai_review_pass(self) -> None:
        gate = evaluate_promotion_gates(
            "fixture-work",
            candidate_qc={
                "hard_failure_count": 0,
                "counts": {"alignments": 2, "section_group_alignment_records": 1},
                "source_traceability": {"hard_failure_count": 0},
                "alignment_quality": {"line_order_issues": []},
                "count_disagreement_errors": [],
            },
            ai_reviews=[
                {"alignment_id": "fixture-work__align-0001", "classification": "fallback_justified", "high_risk": True}
            ],
            alignment_snapshot={"summary": {"remaining_corruption_issue_count": 0, "remaining_leakage_issue_count": 0, "remaining_drift_issue_count": 0}},
            repair_log={"summary": {"automatic_correction_count": 4, "curated_correction_count": 1}},
            manifest={"summary": {"exact_alignment_count": 1, "alignment_record_count": 2, "section_group_alignment_record_count": 1, "active_section_count": 1}, "release_status": "not_cleared"},
            candidate_rows=[{"alignment_id": "fixture-work__align-0001", "is_coarse_alignment": True, "coarse_alignment_reason": "Chapter fallback"}],
        )
        self.assertTrue(gate["can_promote"])
        self.assertEqual(gate["next_state"], "candidate_ready_for_promotion")

    def test_mozi_chapter_three_note_leakage_and_drift_are_caught(self) -> None:
        rows = load_jsonl(REPO_ROOT / "tests" / "fixtures" / "mozi_chapter3_broken_candidate.jsonl")
        reviews = review_alignment_rows("mozi", rows, qc_report={}, repair_log={}, sample_size=len(rows), seed=1)
        by_alignment_id = {review["alignment_id"]: review for review in reviews}

        self.assertEqual(by_alignment_id["mozi-003-that-which-is-affectable__align-0004"]["classification"], "note_leakage")
        self.assertEqual(by_alignment_id["mozi-003-that-which-is-affectable__align-0007"]["classification"], "semantic_drift")

    def test_existing_work_guardrails_remain_stable(self) -> None:
        shijing_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "shijing.yml")
        laozi_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "laozi.yml")
        laozi_alignment = load_json(REPO_ROOT / "logs" / "qc_reports" / "laozi__alignment_qc.json")
        shangshu_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "shangshu.yml")
        shangshu_alignment = load_json(REPO_ROOT / "logs" / "qc_reports" / "shangshu__alignment_qc.json")
        yijing_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "yijing.yml")
        yijing_alignment = load_json(REPO_ROOT / "logs" / "qc_reports" / "yijing__alignment_qc.json")

        self.assertEqual(shijing_manifest["summary"]["section_count"], 305)
        self.assertEqual(shijing_manifest["summary"]["complete_sections"], 305)
        self.assertEqual(laozi_manifest["summary"]["section_count"], 81)
        self.assertEqual(laozi_alignment["exact_alignment_count"], 714)
        self.assertEqual(laozi_alignment["chapter_fallback_count"], 0)
        self.assertEqual(shangshu_manifest["summary"]["complete_sections"], 58)
        self.assertEqual(shangshu_manifest["summary"]["metadata_only_sections"], 2)
        self.assertEqual(shangshu_alignment["summary"]["exact_alignment_count"], 135)
        self.assertEqual(shangshu_alignment["summary"]["fallback_section_count"], 0)
        self.assertEqual(shangshu_alignment["summary"]["remaining_drift_issue_count"], 0)
        self.assertEqual(yijing_manifest["summary"]["section_count"], 64)
        self.assertEqual(yijing_alignment["summary"]["exact_alignment_count"], 450)
        self.assertEqual(yijing_alignment["summary"]["fallback_section_count"], 0)
        self.assertEqual(yijing_alignment["summary"]["remaining_line_order_issue_count"], 0)


if __name__ == "__main__":
    unittest.main()
