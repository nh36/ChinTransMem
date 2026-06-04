from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import corpus_export_paths
from mozi_ocr import detect_mozi_leakage_issues, detect_mozi_ocr_issues
from qc_corpus import _severe_ocr_issues


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


MOZI_NOTICE_MARKERS = (
    "the works of mots",
    "the neglected rival of confucius",
    "english translation:",
    "source notice",
)
MOZI_LEAKAGE_ARTIFACTS = (
    "These are the noted wicked men",
    "These are the able assistants",
    "WHO are",
    "historj-",
    "mstrumental",
    "«",
    "°",
)
MOZI_BAD_OCR_TOKENS = (
    "Watcliing",
    "sigked",
    "Wiiat",
    "wbat",
    "difierent",
    "oflflcial",
    "quaMed",
    "StoTiso",
    "v/ODiucms",
    "acHevemeat",
    "triSe",
    "sa3drLg",
    "an3rwhere",
    "Mots0",
    "tliore",
    "suffi.cient",
    "otliers",
    "Tlieieupoii",
    "wliy",
    "yoxmger",
    "oj0S.cials",
    "an3d3hing",
    "ofiering",
    "tbey",
    "Ofiensive",
)
CJK_RE = re.compile(r"[\u3400-\u9fff]")


def row_by_alignment_id(rows: list[dict[str, object]], alignment_id: str) -> dict[str, object]:
    return next(row for row in rows if row["alignment_id"] == alignment_id)


class MoziPromotionTest(unittest.TestCase):
    def test_mozi_manifest_inventory_ledger_and_exports_agree(self) -> None:
        works = load_json(REPO_ROOT / "metadata" / "works.yml")
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "mozi.yml")
        inventory = load_json(REPO_ROOT / "metadata" / "mozi_inventory.yml")
        ledger = load_json(REPO_ROOT / "metadata" / "mozi_verification_ledger.yml")
        sources = [row for row in load_json(REPO_ROOT / "metadata" / "sources.yml") if row["work_id"] == "mozi"]
        export_rows = load_jsonl(corpus_export_paths("mozi")["jsonl"])
        alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "mozi__alignment_qc.json")
        corpus_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "mozi__corpus_qc.json")

        self.assertIn("mozi", {work["work_id"] for work in works})
        self.assertEqual(manifest["status"], "active")
        self.assertEqual(manifest["corpus_use_status"], "proof_of_concept")
        self.assertEqual(manifest["release_status"], "not_cleared")
        self.assertEqual(manifest["summary"]["section_count"], 52)
        self.assertEqual(manifest["summary"]["active_section_count"], 30)
        self.assertEqual(manifest["summary"]["metadata_only_section_count"], 22)
        self.assertEqual(manifest["summary"]["exact_alignment_count"], 663)
        self.assertEqual(manifest["summary"]["alignment_granularity_counts"], {"chapter": 8, "grouped": 655})
        self.assertEqual(manifest["summary"]["curated_override_section_count"], 1)
        self.assertEqual(manifest["summary"]["fallback_section_count"], 8)
        self.assertEqual(manifest["summary"]["rights_review_required_section_count"], 30)
        self.assertEqual(manifest["summary"]["release_ready_section_count"], 0)
        self.assertEqual(len(manifest["sections"]), 52)
        self.assertEqual(len(inventory["units"]), 52)
        self.assertEqual(len(ledger["entries"]), 52)
        self.assertEqual(len(export_rows), 663)
        self.assertEqual(alignment_qc["summary"]["exact_alignment_count"], 663)
        self.assertEqual(alignment_qc["summary"]["alignment_record_count"], 693)
        self.assertEqual(alignment_qc["summary"]["section_group_alignment_record_count"], 30)
        self.assertEqual(alignment_qc["summary"]["active_section_count"], 30)
        self.assertEqual(corpus_qc["counts"]["alignments"], 693)
        self.assertEqual(corpus_qc["counts"]["exact_alignment_records"], 663)
        self.assertEqual(corpus_qc["counts"]["section_group_alignment_records"], 30)
        self.assertEqual(corpus_qc["status"], "pass")
        self.assertEqual(corpus_qc["hard_failure_count"], 0)

        active_sections = [section for section in manifest["sections"] if section["export_status"] == "active"]
        blocked_sections = [section for section in manifest["sections"] if section["export_status"] == "metadata_only"]
        active_entries = [entry for entry in ledger["entries"] if entry["export_status"] == "active"]
        blocked_entries = [entry for entry in ledger["entries"] if entry["export_status"] == "metadata_only"]
        source_map = {row["source_id"]: row for row in sources}

        self.assertEqual(len(active_sections), 30)
        self.assertEqual(len(blocked_sections), 22)
        self.assertEqual(len(active_entries), 30)
        self.assertEqual(len(blocked_entries), 22)

        for section in active_sections:
            source_ids = section["source_ids"]
            self.assertEqual(section["corpus_use_status"], "proof_of_concept")
            self.assertEqual(section["release_status"], "not_cleared")
            self.assertEqual(section["alignment_status"], "complete")
            self.assertEqual(section["tmx_status"], "complete")
            self.assertTrue(section["translation_processed_path"])
            self.assertTrue(section["alignment_processed_path"])
            self.assertTrue((REPO_ROOT / section["source_processed_path"]).exists())
            self.assertTrue((REPO_ROOT / section["translation_processed_path"]).exists())
            self.assertTrue((REPO_ROOT / section["alignment_processed_path"]).exists())
            for source_id in (source_ids["source_id"], source_ids["target_source_id"]):
                source = source_map[source_id]
                self.assertTrue(source["source_url"])
                self.assertTrue(source["rights_status"])
                self.assertTrue(source["release_status"])
                self.assertTrue(source["rights_note"] or source["notes"])
                self.assertTrue((REPO_ROOT / source["raw_path"]).exists())
                self.assertTrue((REPO_ROOT / source["processed_path"]).exists())

        for entry in active_entries:
            self.assertEqual(entry["decision"], "proof_of_concept_export")
            self.assertEqual(entry["corpus_use_status"], "proof_of_concept")
            self.assertEqual(entry["release_status"], "not_cleared")
            self.assertEqual(entry["rights_status"], "rights_review_required")
            self.assertTrue(entry["source_url"])
            self.assertTrue(entry["translation_source_url"])
            self.assertTrue(entry["rights_note"])
            self.assertTrue((REPO_ROOT / entry["source_path"]).exists())
            self.assertTrue((REPO_ROOT / entry["translation_source_path"]).exists())
            self.assertTrue((REPO_ROOT / entry["processed_source_path"]).exists())
            self.assertTrue((REPO_ROOT / entry["processed_translation_path"]).exists())
            self.assertTrue((REPO_ROOT / entry["processed_alignment_path"]).exists())

        for entry in blocked_entries:
            self.assertEqual(entry["decision"], "metadata_only")
            self.assertEqual(entry["export_status"], "metadata_only")
            self.assertTrue(entry["rights_note"])
            self.assertTrue(entry["reviewer_note"])
            self.assertNotIn("public-domain", entry["reviewer_note"].lower())

        for unit in inventory["units"]:
            self.assertIn(unit["decision"], {"proof_of_concept_export", "metadata_only"})
            self.assertTrue(unit["release_status"])
            self.assertTrue(unit["rights_status"])
            if unit["export_status"] == "active":
                self.assertEqual(unit["rights_status"], "rights_review_required")
                self.assertEqual(unit["release_status"], "not_cleared")
                self.assertTrue(unit["target_source_id"])
                self.assertEqual(unit["blocker_reason"], "")
            else:
                self.assertEqual(unit["export_status"], "metadata_only")
                self.assertTrue(unit["blocker_reason"])
                self.assertNotIn("public-domain", unit["blocker_reason"].lower())

        for source in sources:
            self.assertTrue(source["rights_status"])
            self.assertTrue(source["release_status"])
            if source["work_id"] != "mozi":
                continue
            if source["rights_status"] == "public_domain_verified":
                self.assertNotEqual(source["release_status"], "unknown")

    def test_mozi_exports_have_clean_traceable_proof_of_concept_text(self) -> None:
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "mozi.yml")
        corpus_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "mozi__corpus_qc.json")
        rows = load_jsonl(corpus_export_paths("mozi")["jsonl"])

        active_section_ids = {section["section_id"] for section in manifest["sections"] if section["export_status"] == "active"}
        exported_section_ids = {row["section_id"] for row in rows}
        self.assertEqual(exported_section_ids, active_section_ids)

        for row in rows:
            translation_text = str(row["translation_text"])
            lowered = translation_text.casefold()
            self.assertTrue(translation_text.strip())
            self.assertFalse(CJK_RE.search(translation_text))
            self.assertEqual(_severe_ocr_issues(translation_text), [])
            self.assertEqual(detect_mozi_ocr_issues(translation_text), [])
            self.assertEqual(detect_mozi_leakage_issues(translation_text), [])
            self.assertNotIn("WHO are", translation_text)
            for marker in MOZI_NOTICE_MARKERS:
                self.assertNotIn(marker, lowered)
            for bad_token in MOZI_BAD_OCR_TOKENS:
                self.assertNotIn(bad_token.casefold(), lowered)
            for artifact in MOZI_LEAKAGE_ARTIFACTS:
                if artifact == "WHO are":
                    continue
                self.assertNotIn(artifact.casefold(), lowered)

        self.assertEqual(corpus_qc["text_integrity"]["translation_with_chinese_sections"], [])
        self.assertEqual(corpus_qc["text_integrity"]["translation_with_notice_sections"], [])
        self.assertEqual(corpus_qc["text_integrity"]["translation_with_commentary_sections"], [])
        self.assertEqual(corpus_qc["text_integrity"]["translation_with_heading_sections"], [])
        self.assertEqual(corpus_qc["text_integrity"]["translation_with_ocr_corruption_rows"], [])

    def test_mozi_chapter_three_alignment_and_leakage_regressions(self) -> None:
        rows = load_jsonl(
            REPO_ROOT
            / "corpus"
            / "exports"
            / "jsonl"
            / "mozi__mozi-003-that-which-is-affectable__aligned_passages.jsonl"
        )
        chapter_text = " ".join(str(row["translation_text"]) for row in rows)

        self.assertEqual(len(rows), 10)
        for artifact in MOZI_LEAKAGE_ARTIFACTS:
            self.assertNotIn(artifact, chapter_text)

        good_kings = row_by_alignment_id(rows, "mozi-003-that-which-is-affectable__align-0002")
        bad_kings = row_by_alignment_id(rows, "mozi-003-that-which-is-affectable__align-0003")
        six_bad_princes = row_by_alignment_id(rows, "mozi-003-that-which-is-affectable__align-0007")
        ruler_security = row_by_alignment_id(rows, "mozi-003-that-which-is-affectable__align-0008")
        ode_close = row_by_alignment_id(rows, "mozi-003-that-which-is-affectable__align-0010")

        self.assertIn("under good influences", str(good_kings["translation_text"]))
        self.assertIn("magnanimous and righteous", str(good_kings["translation_text"]))

        self.assertIn("under bad influences", str(bad_kings["translation_text"]))
        self.assertIn("lost their empire and their lives", str(bad_kings["translation_text"]))

        self.assertIn("states were ruined", str(six_bad_princes["translation_text"]))
        self.assertIn("most greedy and disturbing people", str(six_bad_princes["translation_text"]))
        self.assertNotIn("obtain security", str(six_bad_princes["translation_text"]))

        self.assertIn("rulers obtain security", str(ruler_security["translation_text"]))
        self.assertIn("following the right way", str(ruler_security["translation_text"]))
        self.assertNotIn("states were ruined", str(ruler_security["translation_text"]))

        self.assertTrue(str(ode_close["translation_text"]).startswith("(On the contrary)"))
        self.assertIn("An Ode says", str(ode_close["translation_text"]))
        self.assertIn("theme of this (essay)", str(ode_close["translation_text"]))

    def test_mozi_alignment_qc_and_fallbacks_are_explicit(self) -> None:
        alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "mozi__alignment_qc.json")
        corpus_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "mozi__corpus_qc.json")
        completion_doc = load_text(REPO_ROOT / "documentation" / "mozi_completion_quality.md")
        coverage_doc = load_text(REPO_ROOT / "documentation" / "mozi_coverage_audit.md")
        repair_log = load_json(REPO_ROOT / "logs" / "qc_reports" / "mozi__ocr_repair_log.json")

        self.assertEqual(alignment_qc["summary"]["active_section_count"], 30)
        self.assertEqual(alignment_qc["summary"]["blocked_section_count"], 22)
        self.assertEqual(alignment_qc["summary"]["exact_alignment_count"], 663)
        self.assertEqual(alignment_qc["summary"]["alignment_record_count"], 693)
        self.assertEqual(alignment_qc["summary"]["section_group_alignment_record_count"], 30)
        self.assertEqual(alignment_qc["summary"]["alignment_granularity_counts"], {"chapter": 8, "grouped": 655})
        self.assertEqual(alignment_qc["summary"]["curated_override_section_count"], 1)
        self.assertEqual(alignment_qc["summary"]["fallback_section_count"], 8)
        self.assertEqual(alignment_qc["summary"]["hard_failure_count"], 0)
        self.assertEqual(alignment_qc["summary"]["rights_review_required_section_count"], 30)
        self.assertEqual(alignment_qc["summary"]["release_ready_section_count"], 0)
        self.assertIn("pre_repair_leakage_issue_count", alignment_qc["summary"])
        self.assertIn("repaired_leakage_issue_count", alignment_qc["summary"])
        self.assertEqual(alignment_qc["summary"]["remaining_leakage_issue_count"], 0)
        self.assertEqual(alignment_qc["summary"]["drift_issue_count_before_repair"], 2)
        self.assertEqual(alignment_qc["summary"]["repaired_drift_issue_count"], 2)
        self.assertEqual(alignment_qc["summary"]["remaining_drift_issue_count"], 0)
        self.assertEqual(corpus_qc["alignment_quality"]["hard_failure_count"], 0)
        self.assertEqual(corpus_qc["source_traceability"]["hard_failure_count"], 0)
        self.assertEqual(corpus_qc["status"], "pass")
        self.assertEqual(repair_log["summary"]["issue_count_before_repair"], 532)
        self.assertEqual(repair_log["summary"]["automatic_correction_count"], 471)
        self.assertEqual(repair_log["summary"]["curated_correction_count"], 11)
        self.assertEqual(repair_log["summary"]["remaining_issue_count"], 0)
        self.assertIn("pre_repair_leakage_issue_count", repair_log["summary"])
        self.assertIn("repaired_leakage_issue_count", repair_log["summary"])
        self.assertEqual(repair_log["summary"]["remaining_leakage_issue_count"], 0)
        self.assertFalse(repair_log["summary"]["cleaner_source_layer_found"])
        self.assertGreater(len(repair_log["repairs"]), 0)
        self.assertEqual(repair_log["remaining_issues"], [])
        self.assertTrue(any(repair["raw_token"] == "Watcliing" for repair in repair_log["repairs"]))

        fallback_sections = [section for section in alignment_qc["sections"] if section["fallback_used"]]
        self.assertEqual(len(fallback_sections), 8)
        for section in fallback_sections:
            self.assertTrue(section["fallback_reason"])

        chapter_three = next(
            section for section in alignment_qc["sections"] if section["section_id"] == "mozi-003-that-which-is-affectable"
        )
        self.assertFalse(chapter_three["fallback_used"])
        self.assertTrue(chapter_three["curated_override_used"])

        blocked_sections = alignment_qc["blocked_sections"]
        self.assertEqual(len(blocked_sections), 22)
        for section in blocked_sections:
            self.assertTrue(section["reason"])
            self.assertNotIn("not verified public domain", section["reason"].lower())

        self.assertIn("- Exact alignments: 663", completion_doc)
        self.assertIn("- Total processed alignment records: 693", completion_doc)
        self.assertIn("- Curated override sections: 1", completion_doc)
        self.assertIn("- Remaining coarse fallbacks: 8", completion_doc)
        self.assertIn("- Note/commentary leakage issues remaining: 0", completion_doc)
        self.assertIn("- Drift issues remaining: 0", completion_doc)
        self.assertIn("## Remaining fallbacks", completion_doc)
        self.assertIn("| exact_alignment_count | 663 |", coverage_doc)
        self.assertIn("| units_with_release_ready_english_source | 0 |", coverage_doc)

    def test_mozi_mapping_summary_matches_generated_outputs(self) -> None:
        mapping = load_json(REPO_ROOT / "metadata" / "chinesenotes_work_mapping.yml")
        mozi_mapping = next(item for item in mapping["works"] if item["chintransmem_work_id"] == "mozi")
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "mozi.yml")
        alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "mozi__alignment_qc.json")
        summary = mozi_mapping["generated_summary"]

        self.assertEqual(mozi_mapping["status"], "proof_of_concept_ingested")
        self.assertEqual(mozi_mapping["preferred_use"], "proof_of_concept")
        self.assertEqual(summary["total_section_count"], manifest["summary"]["section_count"])
        self.assertEqual(summary["active_section_count"], alignment_qc["summary"]["active_section_count"])
        self.assertEqual(summary["exportable_section_count"], alignment_qc["summary"]["exportable_section_count"])
        self.assertEqual(summary["exact_alignment_count"], alignment_qc["summary"]["exact_alignment_count"])
        self.assertEqual(summary["alignment_record_count"], alignment_qc["summary"]["alignment_record_count"])
        self.assertEqual(summary["section_group_alignment_record_count"], alignment_qc["summary"]["section_group_alignment_record_count"])
        self.assertEqual(summary["blocked_section_count"], alignment_qc["summary"]["blocked_section_count"])
        self.assertEqual(summary["fallback_section_count"], alignment_qc["summary"]["fallback_section_count"])
        self.assertEqual(summary["corruption_issue_count"], alignment_qc["summary"]["corruption_issue_count"])
        self.assertEqual(summary["pre_repair_corruption_issue_count"], alignment_qc["summary"]["pre_repair_corruption_issue_count"])
        self.assertEqual(summary["corrected_corruption_issue_count"], alignment_qc["summary"]["corrected_corruption_issue_count"])
        self.assertEqual(summary["automatic_correction_count"], alignment_qc["summary"]["automatic_correction_count"])
        self.assertEqual(summary["curated_correction_count"], alignment_qc["summary"]["curated_correction_count"])
        self.assertEqual(summary["remaining_corruption_issue_count"], alignment_qc["summary"]["remaining_corruption_issue_count"])
        self.assertEqual(summary["english_witness"], alignment_qc["summary"]["english_witness"])
        self.assertIn("30 proof-of-concept-active chapters", mozi_mapping["notes"])
        self.assertIn("22 chapters remain metadata-only", mozi_mapping["notes"])

    def test_existing_work_guardrails_remain_stable(self) -> None:
        laozi_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "laozi.yml")
        laozi_alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "laozi__alignment_qc.json")
        shangshu_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "shangshu.yml")
        shangshu_alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "shangshu__alignment_qc.json")
        yijing_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "yijing.yml")
        yijing_alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "yijing__alignment_qc.json")
        shijing_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "shijing.yml")

        self.assertEqual(laozi_manifest["summary"]["section_count"], 81)
        self.assertEqual(laozi_alignment_qc["exact_alignment_count"], 714)
        self.assertEqual(laozi_alignment_qc["chapter_fallback_count"], 0)

        self.assertEqual(shangshu_manifest["summary"]["section_count"], 60)
        self.assertEqual(shangshu_manifest["summary"]["complete_sections"], 58)
        self.assertEqual(shangshu_manifest["summary"]["metadata_only_sections"], 2)
        self.assertEqual(shangshu_alignment_qc["summary"]["exact_alignment_count"], 135)
        self.assertEqual(shangshu_alignment_qc["summary"]["fallback_section_count"], 0)
        self.assertEqual(shangshu_alignment_qc["summary"]["remaining_drift_issue_count"], 0)

        self.assertEqual(yijing_manifest["summary"]["section_count"], 64)
        self.assertEqual(yijing_alignment_qc["summary"]["exact_alignment_count"], 450)
        self.assertEqual(yijing_alignment_qc["summary"]["fallback_section_count"], 0)
        self.assertEqual(yijing_alignment_qc["summary"]["remaining_line_order_issue_count"], 0)

        self.assertEqual(shijing_manifest["summary"]["section_count"], 305)
        self.assertEqual(shijing_manifest["summary"]["complete_sections"], 305)
        self.assertEqual(shijing_manifest["summary"]["metadata_only_sections"], 0)


if __name__ == "__main__":
    unittest.main()
