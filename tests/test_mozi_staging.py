from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import corpus_export_paths


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class MoziStagingTest(unittest.TestCase):
    def test_mozi_is_staged_metadata_only_with_provenance(self) -> None:
        works = load_json(REPO_ROOT / "metadata" / "works.yml")
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "mozi.yml")
        inventory = load_json(REPO_ROOT / "metadata" / "mozi_inventory.yml")
        ledger = load_json(REPO_ROOT / "metadata" / "mozi_verification_ledger.yml")
        sources = [row for row in load_json(REPO_ROOT / "metadata" / "sources.yml") if row["work_id"] == "mozi"]

        self.assertIn("mozi", {work["work_id"] for work in works})
        self.assertEqual(manifest["status"], "staged")
        self.assertEqual(manifest["summary"]["section_count"], 52)
        self.assertEqual(manifest["summary"]["complete_sections"], 0)
        self.assertEqual(manifest["summary"]["metadata_only_sections"], 52)
        self.assertEqual(manifest["summary"]["exact_alignment_count"], 0)
        self.assertEqual(len(manifest["sections"]), 52)
        self.assertEqual(len(inventory["units"]), 52)
        self.assertEqual(len(ledger["entries"]), 52)
        self.assertEqual(len(sources), 52)

        self.assertEqual({entry["decision"] for entry in ledger["entries"]}, {"metadata_only"})
        for entry in ledger["entries"]:
            self.assertEqual(len(entry["upstream_commit_sha"]), 40)
            self.assertEqual(entry["upstream_repository_url"], "https://github.com/alexamies/chinesenotes.com")
            self.assertEqual(entry["decision"], "metadata_only")
            self.assertEqual(entry["alignment_status"], "not_exported")
            self.assertIsNone(entry["processed_translation_path"])
            self.assertIsNone(entry["processed_alignment_path"])
            self.assertTrue(entry["local_raw_capture_path"].startswith("corpus/raw/chinesenotes/"))
            self.assertTrue(entry["processed_source_path"].startswith("corpus/processed/chinese_base_texts/"))
            self.assertTrue((REPO_ROOT / entry["local_raw_capture_path"]).exists())
            self.assertTrue((REPO_ROOT / entry["processed_source_path"]).exists())
            self.assertTrue(entry["reason_automatic_alignment_failed"])

        for source in sources:
            self.assertEqual(source["rights_status"], "public_domain")
            self.assertTrue(source["source_url"].startswith("https://github.com/alexamies/chinesenotes.com/blob/"))
            self.assertTrue((REPO_ROOT / source["raw_path"]).exists())
            self.assertTrue((REPO_ROOT / source["processed_path"]).exists())

        for unit in inventory["units"]:
            self.assertEqual(unit["decision"], "metadata_only")
            self.assertEqual(unit["verification_status"], "metadata_only")
            self.assertEqual(unit["english_witness_status"], "unverified_or_missing")
            self.assertTrue(unit["reason"])

    def test_mozi_exports_and_qc_remain_empty_but_clean(self) -> None:
        export_paths = corpus_export_paths("mozi")
        qc_report = load_json(REPO_ROOT / "logs" / "qc_reports" / "mozi__corpus_qc.json")
        alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "mozi__alignment_qc.json")
        tmx_validation = load_json(export_paths["tmx_validation"])
        rows = load_jsonl(export_paths["jsonl"])

        self.assertTrue(export_paths["jsonl"].exists())
        self.assertTrue(export_paths["csv"].exists())
        self.assertTrue(export_paths["tmx"].exists())
        self.assertEqual(rows, [])
        self.assertEqual(qc_report["status"], "pass")
        self.assertEqual(qc_report["hard_failure_count"], 0)
        self.assertEqual(qc_report["counts"]["alignments"], 0)
        self.assertEqual(tmx_validation["status"], "pass")
        self.assertEqual(tmx_validation["section_count"], 0)
        self.assertEqual(tmx_validation["corpus"]["tu_count"], 0)
        self.assertEqual(alignment_qc["summary"]["total_section_count"], 52)
        self.assertEqual(alignment_qc["summary"]["active_section_count"], 0)
        self.assertEqual(alignment_qc["summary"]["exportable_section_count"], 0)
        self.assertEqual(alignment_qc["summary"]["blocked_section_count"], 52)
        self.assertEqual(alignment_qc["summary"]["exact_alignment_count"], 0)
        self.assertEqual(alignment_qc["summary"]["fallback_section_count"], 0)
        self.assertEqual(alignment_qc["summary"]["hard_failure_count"], 0)

    def test_mozi_mapping_summary_matches_generated_outputs(self) -> None:
        mapping = load_json(REPO_ROOT / "metadata" / "chinesenotes_work_mapping.yml")
        mozi_mapping = next(item for item in mapping["works"] if item["chintransmem_work_id"] == "mozi")
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "mozi.yml")
        alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "mozi__alignment_qc.json")
        summary = mozi_mapping["generated_summary"]

        self.assertEqual(mozi_mapping["status"], "staged")
        self.assertEqual(mozi_mapping["preferred_use"], "metadata_only")
        self.assertEqual(summary["total_section_count"], manifest["summary"]["section_count"])
        self.assertEqual(summary["active_section_count"], alignment_qc["summary"]["active_section_count"])
        self.assertEqual(summary["exportable_section_count"], alignment_qc["summary"]["exportable_section_count"])
        self.assertEqual(summary["exact_alignment_count"], alignment_qc["summary"]["exact_alignment_count"])
        self.assertEqual(summary["blocked_section_count"], alignment_qc["summary"]["blocked_section_count"])
        self.assertEqual(summary["fallback_section_count"], alignment_qc["summary"]["fallback_section_count"])
        self.assertEqual(summary["english_witness"], alignment_qc["summary"]["english_witness"])
        self.assertEqual(summary["embedded_chinesenotes_english_section_count"], 2)
        self.assertIn("52 detected chapters", mozi_mapping["notes"])
        self.assertIn("0 active/exportable chapters", mozi_mapping["notes"])
        self.assertIn("no clean public-domain English witness", mozi_mapping["notes"])

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
