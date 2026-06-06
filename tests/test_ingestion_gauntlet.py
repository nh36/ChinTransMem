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
from ingestion_gauntlet import compare_candidate_and_active_exports, evaluate_promotion_gates
from qc_corpus import run_alignment_quality_checks, run_text_integrity_checks
from ai_review_alignments import review_alignment_rows
from shiji_quality import compare_shiji_entity_sequences


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

    def test_liji_candidate_outputs_are_separate_from_active_exports(self) -> None:
        active_paths = corpus_export_paths("liji")
        candidate_paths = candidate_corpus_export_paths("liji")

        self.assertNotEqual(candidate_paths["jsonl"], active_paths["jsonl"])
        self.assertNotEqual(candidate_paths["csv"], active_paths["csv"])
        self.assertNotEqual(candidate_paths["tmx"], active_paths["tmx"])
        self.assertIn("/corpus/candidates/liji/", str(candidate_paths["jsonl"]))
        self.assertEqual(candidate_qc_report_path("liji").name, "liji__candidate_qc.json")
        self.assertEqual(candidate_ai_review_path("liji").name, "liji__alignment_review.jsonl")
        self.assertEqual(candidate_report_path("liji").name, "liji_candidate_report.md")

    def test_shiji_batch_candidate_outputs_are_separate_from_active_exports(self) -> None:
        active_paths = corpus_export_paths("shiji")
        candidate_paths = candidate_corpus_export_paths("shiji", "benji")

        self.assertNotEqual(candidate_paths["jsonl"], active_paths["jsonl"])
        self.assertNotEqual(candidate_paths["csv"], active_paths["csv"])
        self.assertNotEqual(candidate_paths["tmx"], active_paths["tmx"])
        self.assertIn("/corpus/candidates/shiji/benji/", str(candidate_paths["jsonl"]))
        self.assertEqual(candidate_qc_report_path("shiji", "benji").name, "shiji__benji__candidate_qc.json")
        self.assertEqual(candidate_ai_review_path("shiji", "benji").name, "shiji__benji__alignment_review.jsonl")
        self.assertEqual(candidate_report_path("shiji", "benji").name, "shiji_benji_candidate_report.md")

    def test_shiji_batch_scope_is_required(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_promotion_gates("shiji")

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
        self.assertTrue(any("alignment review found" in blocker for blocker in gate["blockers"]))

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

    def test_gauntlet_catches_known_bad_mozi_fixture(self) -> None:
        rows = load_jsonl(REPO_ROOT / "tests" / "fixtures" / "mozi_gauntlet_known_bad_candidate.jsonl")
        text_integrity = run_text_integrity_checks("mozi", rows=rows)
        reviews = review_alignment_rows(
            "mozi",
            rows,
            qc_report={
                "text_integrity": text_integrity,
                "alignment_quality": {"non_grouped_segmentation_mismatch_rows": ["mozi-003-that-which-is-affectable__align-0007"]},
            },
            repair_log={},
            sample_size=len(rows),
            seed=1,
        )
        classifications = {review["alignment_id"]: review["classification"] for review in reviews}
        gate = evaluate_promotion_gates(
            "fixture-work",
            candidate_qc={
                "hard_failure_count": text_integrity["hard_failure_count"],
                "counts": {"alignments": 4, "section_group_alignment_records": 1},
                "source_traceability": {"hard_failure_count": 0},
                "alignment_quality": {"line_order_issues": []},
                "count_disagreement_errors": [],
            },
            ai_reviews=reviews,
            alignment_snapshot={
                "summary": {
                    "remaining_corruption_issue_count": 1,
                    "remaining_leakage_issue_count": 1,
                    "remaining_drift_issue_count": 1,
                }
            },
            repair_log={"summary": {"automatic_correction_count": 0, "curated_correction_count": 0}},
            manifest={
                "summary": {
                    "exact_alignment_count": 4,
                    "alignment_record_count": 5,
                    "section_group_alignment_record_count": 1,
                    "active_section_count": 2,
                },
                "release_status": "not_cleared",
            },
            candidate_rows=rows,
        )

        self.assertGreater(text_integrity["hard_failure_count"], 0)
        self.assertIn("translation_with_ocr_corruption_rows", text_integrity)
        self.assertEqual(classifications["mozi-001-make-close-the-scholars__align-0001"], "ocr_issue")
        self.assertEqual(classifications["mozi-003-that-which-is-affectable__align-0004"], "note_leakage")
        self.assertEqual(classifications["mozi-003-that-which-is-affectable__align-0007"], "semantic_drift")
        self.assertFalse(gate["can_promote"])

    def test_repaired_fixture_only_passes_when_bad_text_is_removed_and_fallback_is_justified(self) -> None:
        rows = [
            {
                "alignment_id": "mozi-001-make-close-the-scholars__align-0001",
                "work_id": "mozi",
                "section_id": "mozi-001-make-close-the-scholars",
                "order": 1,
                "source_segment_count": 2,
                "target_segment_count": 42,
                "is_coarse_alignment": True,
                "coarse_alignment_reason": "ChineseNotes source segmentation remains too coarse for grouped alignment at this chapter scale; retained chapter-level fallback after deterministic OCR repair.",
                "chinese_text": "入國而不存其士則亡國矣見賢而不急則緩其君矣",
                "translation_text": "Formerly Lord Wen of Chin was once in exile and yet later became the leading feudal lord. Lord Huan of Ch'i was once forced to leave his state and yet later became a tyrant among the feudal lords. Lord Kou Chien of Yiieh was once brought under humiliation by the king of Wu and yet he was later looked upon with awe by the princes of China. Thus, Pi Kan died of his uprightness, Meng Pen perished by his strength, Hsi Shih paid with her life for her beauty, and Wu Ch'i was torn alive for his achievement. The water in a river does not come from a single source, neither is the fur coat that is worth a thousand yi is not from the white fur of a single fox.",
            },
            {
                "alignment_id": "mozi-003-that-which-is-affectable__align-0004",
                "work_id": "mozi",
                "section_id": "mozi-003-that-which-is-affectable",
                "order": 12,
                "source_segment_count": 2,
                "target_segment_count": 3,
                "is_coarse_alignment": False,
                "coarse_alignment_reason": None,
                "chinese_text": "齊桓染於管仲、鮑叔，晉文染於舅犯、高偃。",
                "translation_text": "Lord Huan of Ch’i came under the influence of Kuan Chung and Pao Shu; Lord Wen of Chin, under that of Uncle Fan and Kao Yen; and the five lords who followed good influences became Tyrants among the feudal lords and handed their fame to posterity.",
            },
            {
                "alignment_id": "mozi-003-that-which-is-affectable__align-0007",
                "work_id": "mozi",
                "section_id": "mozi-003-that-which-is-affectable",
                "order": 15,
                "source_segment_count": 2,
                "target_segment_count": 4,
                "is_coarse_alignment": False,
                "coarse_alignment_reason": None,
                "chinese_text": "此六君者所染不當，故國家殘亡，身為刑戮。舉天下之貪暴苛擾者，必稱此六君也。",
                "translation_text": "Now these six princes had been under bad influences. Therefore their states were ruined and they were executed, their ancestral temples were destroyed and descendants annihilated. The whole world points to these six princes as the most greedy and disturbing people.",
            },
            {
                "alignment_id": "mozi-003-that-which-is-affectable__align-0008",
                "work_id": "mozi",
                "section_id": "mozi-003-that-which-is-affectable",
                "order": 17,
                "source_segment_count": 4,
                "target_segment_count": 5,
                "is_coarse_alignment": False,
                "coarse_alignment_reason": None,
                "chinese_text": "凡君之所以安者，何也？以其行理也。",
                "translation_text": "Now, how can the rulers obtain security? They can obtain it by following the right way, and one naturally follows the right way when under good influence.",
            },
        ]
        text_integrity = run_text_integrity_checks("mozi", rows=rows)
        reviews = review_alignment_rows("mozi", rows, qc_report={"text_integrity": text_integrity, "alignment_quality": {}}, repair_log={}, sample_size=len(rows), seed=1)
        gate = evaluate_promotion_gates(
            "fixture-work",
            candidate_qc={
                "hard_failure_count": text_integrity["hard_failure_count"],
                "counts": {"alignments": 5, "section_group_alignment_records": 1},
                "source_traceability": {"hard_failure_count": 0},
                "alignment_quality": {"line_order_issues": []},
                "count_disagreement_errors": [],
            },
            ai_reviews=reviews,
            alignment_snapshot={"summary": {"remaining_corruption_issue_count": 0, "remaining_leakage_issue_count": 0, "remaining_drift_issue_count": 0}},
            repair_log={"summary": {"automatic_correction_count": 5, "curated_correction_count": 1}},
            manifest={
                "summary": {
                    "exact_alignment_count": 4,
                    "alignment_record_count": 5,
                    "section_group_alignment_record_count": 1,
                    "active_section_count": 2,
                },
                "release_status": "not_cleared",
            },
            candidate_rows=rows,
        )

        self.assertEqual(text_integrity["hard_failure_count"], 0)
        self.assertTrue(all(review["classification"] in {"pass", "fallback_justified"} for review in reviews))
        self.assertTrue(gate["can_promote"])

    def test_candidate_active_comparison_reports_mismatched_counts(self) -> None:
        comparison = compare_candidate_and_active_exports(
            "mozi",
            candidate_qc={"hard_failure_count": 0},
            active_qc={"hard_failure_count": 0},
            candidate_rows=[{"section_id": "s1", "alignment_id": "a1", "is_coarse_alignment": False}],
            active_rows=[],
            candidate_alignment_snapshot={"summary": {"remaining_corruption_issue_count": 0, "remaining_leakage_issue_count": 0, "remaining_drift_issue_count": 0}},
            active_alignment_snapshot={"summary": {"remaining_corruption_issue_count": 0, "remaining_leakage_issue_count": 0, "remaining_drift_issue_count": 0}},
        )

        self.assertFalse(comparison["matches"])
        self.assertTrue(any("exact alignment counts differ" in mismatch for mismatch in comparison["mismatches"]))

    def test_existing_work_guardrails_remain_stable(self) -> None:
        shijing_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "shijing.yml")
        laozi_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "laozi.yml")
        laozi_alignment = load_json(REPO_ROOT / "logs" / "qc_reports" / "laozi__alignment_qc.json")
        shangshu_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "shangshu.yml")
        shangshu_alignment = load_json(REPO_ROOT / "logs" / "qc_reports" / "shangshu__alignment_qc.json")
        yijing_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "yijing.yml")
        yijing_alignment = load_json(REPO_ROOT / "logs" / "qc_reports" / "yijing__alignment_qc.json")
        mozi_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "mozi.yml")

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
        self.assertEqual(mozi_manifest["summary"]["active_section_count"], 30)

    def test_liji_active_sections_have_provenance_and_rights_metadata(self) -> None:
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "liji.yml")
        sources = {
            source["source_id"]: source
            for source in load_json(REPO_ROOT / "metadata" / "sources.yml")
            if source.get("work_id") == "liji"
        }

        self.assertEqual(manifest["summary"]["active_section_count"], 49)
        self.assertEqual(len(sources), 98)
        for section in manifest["sections"]:
            self.assertEqual(section["export_status"], "active")
            self.assertEqual(section["rights_status"], "rights_review_required")
            self.assertEqual(section["release_status"], "not_cleared")
            source_ids = section["source_ids"]
            self.assertIn("source_id", source_ids)
            self.assertIn("target_source_id", source_ids)
            for source_id in (source_ids["source_id"], source_ids["target_source_id"]):
                source = sources[source_id]
                self.assertTrue(source["source_url"])
                self.assertEqual(source["rights_status"], "rights_review_required")
                self.assertEqual(source["release_status"], "not_cleared")
                self.assertTrue(source.get("rights_note") or source.get("notes"))

    def test_liji_active_exports_are_clean_and_fallbacks_reviewed(self) -> None:
        candidate_qc = load_json(candidate_qc_report_path("liji"))
        candidate_report = candidate_report_path("liji").read_text(encoding="utf-8")
        completion_report = (REPO_ROOT / "documentation" / "liji_completion_quality.md").read_text(encoding="utf-8")
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "liji.yml")
        reviews = load_jsonl(candidate_ai_review_path("liji"))
        active_rows = load_jsonl(corpus_export_paths("liji")["jsonl"])
        active_text_integrity = run_text_integrity_checks("liji", rows=active_rows)
        former_fallback_sections = {
            "liji-015-record-of-small-matters-in-the-dress-of",
            "liji-019-record-of-music",
            "liji-031-the-state-of-equilibrium-and-harmony",
            "liji-042-the-great-learning",
        }

        self.assertEqual(candidate_qc["hard_failure_count"], 0)
        self.assertEqual(active_text_integrity["hard_failure_count"], 0)
        self.assertEqual(candidate_qc["text_integrity"]["translation_with_ocr_corruption_rows"], [])
        self.assertEqual(candidate_qc["text_integrity"]["translation_with_notice_sections"], [])
        self.assertEqual(candidate_qc["text_integrity"]["translation_with_commentary_sections"], [])
        self.assertEqual(candidate_qc["text_integrity"]["translation_with_heading_sections"], [])
        self.assertEqual(
            {review["classification"] for review in reviews},
            {"pass"},
        )
        self.assertTrue(
            former_fallback_sections.issubset({review["section_id"] for review in reviews})
        )
        self.assertTrue(
            all(not section["fallback_used"] for section in manifest["sections"] if section["section_id"] in former_fallback_sections)
        )
        self.assertIn("Reviewed fallback alignments: 0", candidate_report)
        self.assertIn("Current state: active_proof_of_concept", candidate_report)
        self.assertIn("Candidate and active promoted exports match on counts and file content.", candidate_report)
        self.assertIn("Remaining coarse fallbacks: 0", completion_report)
        self.assertIn("liji-031-the-state-of-equilibrium-and-harmony", completion_report)
        self.assertIn("liji-042-the-great-learning", completion_report)
        self.assertIn("scope: resolved", completion_report)

    def test_liji_mapping_and_reports_agree(self) -> None:
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "liji.yml")
        mapping = load_json(REPO_ROOT / "metadata" / "chinesenotes_work_mapping.yml")
        candidate_qc = load_json(candidate_qc_report_path("liji"))
        active_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "liji__corpus_qc.json")
        alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "liji__alignment_qc.json")
        mozi_completion = (REPO_ROOT / "documentation" / "mozi_completion_quality.md").read_text(encoding="utf-8")

        mapping_entry = next(entry for entry in mapping["works"] if entry["chintransmem_work_id"] == "liji")
        self.assertEqual(mapping_entry["status"], "already_ingested")
        self.assertEqual(mapping_entry["preferred_use"], "aligned_passages")
        self.assertEqual(manifest["summary"]["section_count"], 49)
        self.assertEqual(manifest["summary"]["active_section_count"], 49)
        self.assertEqual(manifest["summary"]["exact_alignment_count"], 1876)
        self.assertEqual(manifest["summary"]["fallback_section_count"], 0)
        self.assertEqual(candidate_qc["status"], "pass")
        self.assertEqual(candidate_qc["counts"]["exact_alignment_records"], 1876)
        self.assertEqual(active_qc["manifest_summary"]["exact_alignment_count"], 1876)
        self.assertEqual(active_qc["manifest_summary"]["fallback_section_count"], 0)
        self.assertEqual(active_qc["manifest_summary"]["remaining_corruption_issue_count"], 0)
        self.assertEqual(active_qc["manifest_summary"]["remaining_leakage_issue_count"], 0)
        self.assertEqual(active_qc["manifest_summary"]["remaining_drift_issue_count"], 0)
        self.assertEqual(alignment_qc["summary"]["exact_alignment_count"], 1876)
        self.assertEqual(alignment_qc["summary"]["fallback_section_count"], 0)
        self.assertEqual(alignment_qc["summary"]["alignment_granularity_counts"], {"block": 1637, "grouped": 239})
        self.assertEqual(mozi_completion.splitlines()[0], "# Mozi completion quality")

    def test_shiji_active_sections_have_provenance_and_rights_metadata(self) -> None:
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "shiji.yml")
        sources = {
            source["source_id"]: source
            for source in load_json(REPO_ROOT / "metadata" / "sources.yml")
            if source.get("work_id") == "shiji"
        }
        active_sections = [section for section in manifest["sections"] if section["export_status"] == "active"]

        self.assertEqual(manifest["summary"]["section_count"], 3)
        self.assertEqual(manifest["summary"]["active_section_count"], 2)
        self.assertEqual(manifest["summary"]["metadata_only_blocked_section_count"], 1)
        for section in active_sections:
            self.assertEqual(section["rights_status"], "rights_review_required")
            self.assertEqual(section["release_status"], "not_cleared")
            source_ids = section["source_ids"]
            self.assertIn("source_id", source_ids)
            self.assertIn("target_source_id", source_ids)
            for source_id in (source_ids["source_id"], source_ids["target_source_id"]):
                source = sources[source_id]
                self.assertTrue(source["source_url"])
                self.assertEqual(source["rights_status"], "rights_review_required")
                self.assertEqual(source["release_status"], "not_cleared")
                self.assertTrue(source.get("rights_note") or source.get("notes"))

    def test_shiji_batch_exports_are_clean_and_agree_with_active(self) -> None:
        candidate_qc = load_json(candidate_qc_report_path("shiji", "benji"))
        candidate_report = candidate_report_path("shiji", "benji").read_text(encoding="utf-8")
        reviews = load_jsonl(candidate_ai_review_path("shiji", "benji"))
        active_rows = load_jsonl(corpus_export_paths("shiji")["jsonl"])
        active_text_integrity = run_text_integrity_checks("shiji", rows=active_rows)
        comparison = compare_candidate_and_active_exports("shiji", batch_id="benji")

        self.assertEqual(candidate_qc["hard_failure_count"], 0)
        self.assertEqual(active_text_integrity["hard_failure_count"], 0)
        self.assertEqual(candidate_qc["text_integrity"]["translation_with_ocr_corruption_rows"], [])
        self.assertEqual(candidate_qc["text_integrity"]["translation_with_notice_sections"], [])
        self.assertEqual(candidate_qc["text_integrity"]["translation_with_commentary_sections"], [])
        self.assertEqual(candidate_qc["text_integrity"]["translation_with_heading_sections"], [])
        self.assertEqual({review["classification"] for review in reviews}, {"pass"})
        self.assertTrue(comparison["matches"])
        self.assertEqual(comparison["candidate_fallback_count"], 0)
        self.assertEqual(comparison["active_fallback_count"], 0)
        self.assertIn("Monolithic promotion occurred: False", candidate_report)
        self.assertIn("Batch id: benji", candidate_report)
        self.assertIn("Current state: active_proof_of_concept", candidate_report)
        self.assertIn("Named-entity drift issues detected:", candidate_report)
        self.assertIn("Named-entity drift issues repaired:", candidate_report)
        self.assertIn("Named-entity drift issues remaining: 0", candidate_report)
        self.assertIn("Shiji 003 succession sequence passed entity-order validation: True", candidate_report)
        self.assertIn("Candidate and active promoted exports match on counts and file content.", candidate_report)

    def test_shiji_mapping_and_reports_agree(self) -> None:
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "shiji.yml")
        mapping = load_json(REPO_ROOT / "metadata" / "chinesenotes_work_mapping.yml")
        batch_mapping = load_json(REPO_ROOT / "metadata" / "shiji_batch_mapping.yml")
        verification = load_json(REPO_ROOT / "metadata" / "shiji_verification_ledger.yml")
        candidate_qc = load_json(candidate_qc_report_path("shiji", "benji"))
        active_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "shiji__corpus_qc.json")
        alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "shiji__alignment_qc.json")

        mapping_entry = next(entry for entry in mapping["works"] if entry["chintransmem_work_id"] == "shiji")
        benji_batch = next(entry for entry in batch_mapping["batches"] if entry["batch_id"] == "benji")
        self.assertEqual(mapping_entry["status"], "already_ingested")
        self.assertEqual(mapping_entry["preferred_use"], "aligned_passages")
        self.assertEqual(benji_batch["selected_chapter_numbers"], [1, 2, 3])
        self.assertEqual(manifest["summary"]["section_count"], 3)
        self.assertEqual(manifest["summary"]["active_section_count"], 2)
        self.assertEqual(manifest["summary"]["metadata_only_blocked_section_count"], 1)
        self.assertEqual(manifest["summary"]["exact_alignment_count"], 46)
        self.assertEqual(manifest["summary"]["fallback_section_count"], 0)
        self.assertEqual(manifest["summary"]["alignment_granularity_counts"], {"block": 46})
        self.assertEqual(candidate_qc["status"], "pass")
        self.assertEqual(candidate_qc["counts"]["exact_alignment_records"], 46)
        self.assertEqual(active_qc["manifest_summary"]["exact_alignment_count"], 46)
        self.assertEqual(active_qc["manifest_summary"]["fallback_section_count"], 0)
        self.assertEqual(active_qc["manifest_summary"]["remaining_corruption_issue_count"], 0)
        self.assertEqual(active_qc["manifest_summary"]["remaining_leakage_issue_count"], 0)
        self.assertEqual(active_qc["manifest_summary"]["remaining_drift_issue_count"], 0)
        self.assertEqual(alignment_qc["summary"]["exact_alignment_count"], 46)
        self.assertEqual(alignment_qc["summary"]["fallback_section_count"], 0)
        self.assertEqual(alignment_qc["summary"]["alignment_granularity_counts"], {"block": 46})
        self.assertEqual(verification["summary"]["active_exportable_section_count"], 2)
        self.assertGreater(alignment_qc["summary"]["drift_issue_count_before_repair"], 0)
        self.assertEqual(alignment_qc["summary"]["repaired_drift_issue_count"], alignment_qc["summary"]["drift_issue_count_before_repair"])
        self.assertEqual(alignment_qc["summary"]["remaining_drift_issue_count"], 0)
        self.assertEqual(alignment_qc["summary"]["anchor_mapped_section_count"], 1)
        self.assertEqual(alignment_qc["summary"]["anchor_mapped_sections"], ["shiji-003-annals-of-yin"])
        self.assertTrue(alignment_qc["summary"]["entity_sequence_validation_passed"])

    def test_shiji_003_succession_sequence_passes_entity_order_validation(self) -> None:
        anchors = load_json(REPO_ROOT / "metadata" / "shiji_alignment_anchors.yml")["sections"][0]["anchors"]
        rows = load_jsonl(corpus_export_paths("shiji")["jsonl"])
        yin_rows = [row for row in rows if row["section_id"] == "shiji-003-annals-of-yin"]
        expected_fragments = [
            "契卒，子昭明立。",
            "昭明卒，子相土立。",
            "相土卒，子昌若立。",
            "昌若卒，子曹圉立。",
            "曹圉卒，子冥立。",
            "冥卒，子振立。",
            "主癸卒，子天乙立，是為成湯。",
        ]

        for fragment in expected_fragments:
            row = next(row for row in yin_rows if fragment in row["chinese_text"])
            comparison = compare_shiji_entity_sequences(
                str(row["chinese_text"]),
                str(row["translation_text"]),
                anchors,
            )
            self.assertEqual(comparison["entity_sequence_verdict"], "pass", fragment)

    def test_shiji_entity_sequence_drift_is_caught_by_qc_and_gates(self) -> None:
        rows = [
            {
                "alignment_id": "shiji-003-annals-of-yin__aligned-003",
                "work_id": "shiji",
                "section_id": "shiji-003-annals-of-yin",
                "order": 8,
                "source_segment_count": 2,
                "target_segment_count": 1,
                "is_coarse_alignment": False,
                "coarse_alignment_reason": None,
                "chinese_text": "契卒，子昭明立。昭明卒，子相土立。",
                "translation_text": "Qi (documents) died, and his son Zhaoming (luminous) succeeded him.",
            }
        ]
        qc = run_text_integrity_checks("shiji", rows=rows)
        alignment_qc = run_alignment_quality_checks("shiji", rows=rows)
        reviews = review_alignment_rows(
            "shiji",
            rows,
            qc_report={"alignment_quality": alignment_qc, "text_integrity": qc},
            repair_log={},
            sample_size=len(rows),
            seed=1,
        )
        gate = evaluate_promotion_gates(
            "fixture-work",
            candidate_qc={
                "hard_failure_count": alignment_qc["hard_failure_count"],
                "counts": {"alignments": 1, "section_group_alignment_records": 1},
                "source_traceability": {"hard_failure_count": 0},
                "alignment_quality": {"line_order_issues": []},
                "count_disagreement_errors": [],
            },
            ai_reviews=reviews,
            alignment_snapshot={
                "summary": {
                    "remaining_corruption_issue_count": 0,
                    "remaining_leakage_issue_count": 0,
                    "remaining_drift_issue_count": alignment_qc["hard_failure_count"],
                }
            },
            repair_log={"summary": {"automatic_correction_count": 0, "curated_correction_count": 0}},
            manifest={
                "summary": {
                    "exact_alignment_count": 1,
                    "alignment_record_count": 2,
                    "section_group_alignment_record_count": 1,
                    "active_section_count": 1,
                },
                "release_status": "not_cleared",
            },
            candidate_rows=rows,
        )

        self.assertGreater(alignment_qc["hard_failure_count"], 0)
        self.assertTrue(alignment_qc["entity_sequence_drift_issues"])
        self.assertEqual(reviews[0]["classification"], "semantic_drift")
        self.assertEqual(reviews[0]["entity_sequence_verdict"], "target_lagging")
        self.assertIn("lags behind the Chinese source sequence", reviews[0]["drift_explanation"])
        self.assertFalse(gate["can_promote"])
        self.assertTrue(any("deterministic candidate QC" in blocker for blocker in gate["blockers"]))

    def test_shiji_002_is_metadata_only_with_explicit_blocker_and_no_alignment_file(self) -> None:
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "shiji.yml")
        section = next(section for section in manifest["sections"] if section["section_id"] == "shiji-002-annals-of-xia")
        alignment_path = REPO_ROOT / "corpus" / "processed" / "alignments" / "shiji__shiji-002-annals-of-xia__cn-zh-1f6b1d3__cn-en-1f6b1d3__alignments.jsonl"

        self.assertEqual(section["export_status"], "metadata_only")
        self.assertEqual(section["alignment_processed_path"], None)
        self.assertIn("group 36", section["fallback_reason"])
        self.assertIn("target segment length/structure imbalance suggests missing grouping", section["fallback_reason"])
        self.assertFalse(alignment_path.exists())


if __name__ == "__main__":
    unittest.main()
