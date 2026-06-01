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
from qc_corpus import _severe_ocr_issues


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


MOZI_NOTICE_MARKERS = (
    "the works of mots",
    "the neglected rival of confucius",
    "english translation:",
    "source notice",
)
CJK_RE = re.compile(r"[\u3400-\u9fff]")


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
        self.assertEqual(manifest["summary"]["exact_alignment_count"], 684)
        self.assertEqual(manifest["summary"]["alignment_granularity_counts"], {"chapter": 8, "grouped": 676})
        self.assertEqual(manifest["summary"]["fallback_section_count"], 8)
        self.assertEqual(manifest["summary"]["rights_review_required_section_count"], 30)
        self.assertEqual(manifest["summary"]["release_ready_section_count"], 0)
        self.assertEqual(len(manifest["sections"]), 52)
        self.assertEqual(len(inventory["units"]), 52)
        self.assertEqual(len(ledger["entries"]), 52)
        self.assertEqual(len(sources), 82)
        self.assertEqual(len(export_rows), 684)
        self.assertEqual(alignment_qc["summary"]["active_section_count"], 30)
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
            for marker in MOZI_NOTICE_MARKERS:
                self.assertNotIn(marker, lowered)

        self.assertEqual(corpus_qc["text_integrity"]["translation_with_chinese_sections"], [])
        self.assertEqual(corpus_qc["text_integrity"]["translation_with_notice_sections"], [])
        self.assertEqual(corpus_qc["text_integrity"]["translation_with_commentary_sections"], [])
        self.assertEqual(corpus_qc["text_integrity"]["translation_with_heading_sections"], [])
        self.assertEqual(corpus_qc["text_integrity"]["translation_with_ocr_corruption_rows"], [])

    def test_mozi_alignment_qc_and_fallbacks_are_explicit(self) -> None:
        alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "mozi__alignment_qc.json")
        corpus_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "mozi__corpus_qc.json")

        self.assertEqual(alignment_qc["summary"]["active_section_count"], 30)
        self.assertEqual(alignment_qc["summary"]["blocked_section_count"], 22)
        self.assertEqual(alignment_qc["summary"]["exact_alignment_count"], 684)
        self.assertEqual(alignment_qc["summary"]["alignment_granularity_counts"], {"chapter": 8, "grouped": 676})
        self.assertEqual(alignment_qc["summary"]["fallback_section_count"], 8)
        self.assertEqual(alignment_qc["summary"]["hard_failure_count"], 0)
        self.assertEqual(alignment_qc["summary"]["rights_review_required_section_count"], 30)
        self.assertEqual(alignment_qc["summary"]["release_ready_section_count"], 0)
        self.assertEqual(corpus_qc["alignment_quality"]["hard_failure_count"], 0)
        self.assertEqual(corpus_qc["source_traceability"]["hard_failure_count"], 0)

        fallback_sections = [section for section in alignment_qc["sections"] if section["fallback_used"]]
        self.assertEqual(len(fallback_sections), 8)
        for section in fallback_sections:
            self.assertTrue(section["fallback_reason"])

        blocked_sections = alignment_qc["blocked_sections"]
        self.assertEqual(len(blocked_sections), 22)
        for section in blocked_sections:
            self.assertTrue(section["reason"])
            self.assertNotIn("not verified public domain", section["reason"].lower())

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
        self.assertEqual(summary["blocked_section_count"], alignment_qc["summary"]["blocked_section_count"])
        self.assertEqual(summary["fallback_section_count"], alignment_qc["summary"]["fallback_section_count"])
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
