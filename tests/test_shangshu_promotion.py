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

CJK_RE = re.compile(r"[\u3400-\u9fff]")
NOTICE_MARKERS = (
    "english translation:",
    "english translations",
    "public domain worldwide",
    "this work was published before january 1, 1923",
)
COMMENTARY_MARKERS = ("〈", "〉", "編者按", "注釋")
PARENTHETICAL_HEADING_RE = re.compile(r"^\([^()]{1,120}\)$")
BAD_FORMS = ("inteuigent", "without-effprt", "cour- te-qus", "rea,ched", "black-liaired", "1 can")


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class ShangshuPromotionTest(unittest.TestCase):
    def test_shangshu_is_active_with_exportable_and_metadata_only_sections(self) -> None:
        works = load_json(REPO_ROOT / "metadata" / "works.yml")
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "shangshu.yml")
        inventory = load_json(REPO_ROOT / "metadata" / "shangshu_inventory.yml")
        ledger = load_json(REPO_ROOT / "metadata" / "shangshu_verification_ledger.yml")
        sources = [row for row in load_json(REPO_ROOT / "metadata" / "sources.yml") if row["work_id"] == "shangshu"]

        self.assertIn("shangshu", {work["work_id"] for work in works})
        self.assertEqual(manifest["summary"]["section_count"], 60)
        self.assertEqual(manifest["summary"]["complete_sections"], 58)
        self.assertEqual(manifest["summary"]["metadata_only_sections"], 2)
        self.assertEqual(manifest["summary"]["exact_alignment_count"], 130)
        self.assertEqual(len(manifest["sections"]), 60)
        self.assertEqual(len(inventory["units"]), 60)
        self.assertEqual(len(ledger["entries"]), 60)
        self.assertEqual(len(sources), 118)

        decisions = {entry["decision"] for entry in ledger["entries"]}
        self.assertEqual(decisions, {"export", "metadata_only"})
        blocked_ids = {
            entry["section_id"]
            for entry in ledger["entries"]
            if entry["decision"] == "metadata_only"
        }
        self.assertEqual(
            blocked_ids,
            {
                "shangshu-002-yu-shu-dan-zhu-forged",
                "shangshu-008-xia-shu-yu-shi-forged",
            },
        )
        for entry in ledger["entries"]:
            self.assertEqual(len(entry["upstream_commit_sha"]), 40)
            self.assertEqual(entry["upstream_repository_url"], "https://github.com/alexamies/chinesenotes.com")
            self.assertTrue(entry["local_raw_capture_path"].startswith("corpus/raw/chinesenotes/"))
            self.assertTrue(entry["processed_source_path"].startswith("corpus/processed/chinese_base_texts/"))
            if entry["decision"] == "export":
                self.assertTrue(entry["processed_translation_path"].startswith("corpus/processed/translations/"))
                self.assertTrue(entry["translation_raw_capture_path"].startswith("corpus/raw/wikisource/"))
                self.assertTrue(entry["translation_source_pages"])
                self.assertEqual(entry["alignment_status"], "complete")
                self.assertEqual(entry["verification_status"], "verified_rendered_transcription")
            else:
                self.assertIsNone(entry["processed_translation_path"])
                self.assertEqual(entry["alignment_status"], "not_exported")

        for source in sources:
            self.assertEqual(source["rights_status"], "public_domain")
            self.assertTrue((REPO_ROOT / source["raw_path"]).exists())
            self.assertTrue((REPO_ROOT / source["processed_path"]).exists())
            if source["language_code"] == "zh-Hant":
                self.assertTrue(source["source_url"].startswith("https://github.com/alexamies/chinesenotes.com/blob/"))
                self.assertTrue(source["raw_path"].startswith("corpus/raw/chinesenotes/"))
            else:
                self.assertTrue(source["source_url"].startswith("https://en.wikisource.org/wiki/"))
                self.assertTrue(source["raw_path"].startswith("corpus/raw/wikisource/"))
                self.assertIn("Sacred Books of the East", source["citation"])

    def test_shangshu_exports_and_alignment_qc_are_clean(self) -> None:
        export_paths = corpus_export_paths("shangshu")
        export_jsonl = export_paths["jsonl"]
        export_csv = export_paths["csv"]
        export_tmx = export_paths["tmx"]
        qc_report = load_json(REPO_ROOT / "logs" / "qc_reports" / "shangshu__corpus_qc.json")
        alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "shangshu__alignment_qc.json")
        rows = load_jsonl(export_jsonl)

        self.assertTrue(export_jsonl.exists())
        self.assertTrue(export_csv.exists())
        self.assertTrue(export_tmx.exists())
        self.assertEqual(qc_report["status"], "pass")
        self.assertEqual(qc_report["hard_failure_count"], 0)
        self.assertFalse(qc_report["text_integrity"]["empty_source_sections"])
        self.assertFalse(qc_report["text_integrity"]["empty_translation_sections"])
        self.assertFalse(qc_report["text_integrity"]["translation_with_chinese_sections"])
        self.assertFalse(qc_report["text_integrity"]["translation_with_notice_sections"])
        self.assertFalse(qc_report["text_integrity"]["translation_with_commentary_sections"])
        self.assertFalse(qc_report["text_integrity"]["translation_with_heading_sections"])
        self.assertFalse(qc_report["text_integrity"]["translation_with_ocr_corruption_rows"])
        self.assertFalse(qc_report["text_integrity"]["translation_with_truncated_fragment_rows"])
        self.assertFalse(qc_report["text_integrity"]["translation_with_known_bad_forms_rows"])
        self.assertFalse(qc_report["alignment_quality"]["false_precision_multi_clause_targets"])
        self.assertFalse(qc_report["alignment_quality"]["non_grouped_segmentation_mismatch_rows"])

        self.assertEqual(alignment_qc["summary"]["total_section_count"], 60)
        self.assertEqual(alignment_qc["summary"]["active_section_count"], 58)
        self.assertEqual(alignment_qc["summary"]["exportable_section_count"], 58)
        self.assertEqual(alignment_qc["summary"]["exact_alignment_count"], 130)
        self.assertEqual(alignment_qc["summary"]["alignment_granularity_counts"], {"block": 41, "grouped": 89})
        self.assertEqual(alignment_qc["summary"]["curated_override_section_count"], 0)
        self.assertEqual(alignment_qc["summary"]["fallback_section_count"], 0)
        self.assertEqual(alignment_qc["summary"]["blocked_section_count"], 2)
        self.assertEqual(alignment_qc["summary"]["remaining_corruption_issue_count"], 0)
        self.assertEqual(
            alignment_qc["summary"]["english_witness"],
            "Wikisource transcription of James Legge, Sacred Books of the East, Volume 3",
        )
        self.assertEqual(alignment_qc["summary"]["hard_failure_count"], 0)
        self.assertEqual(len(rows), 130)
        self.assertEqual(len({row["section_id"] for row in rows}), 58)
        self.assertFalse(
            {"shangshu-002-yu-shu-dan-zhu-forged", "shangshu-008-xia-shu-yu-shi-forged"}
            & {row["section_id"] for row in rows}
        )
        for row in rows:
            source_text = str(row["chinese_text"]).strip()
            translation_text = str(row["translation_text"]).strip()
            lowered = translation_text.lower()
            self.assertTrue(source_text)
            self.assertTrue(translation_text)
            self.assertIsNone(CJK_RE.search(translation_text))
            self.assertFalse(any(marker in translation_text for marker in COMMENTARY_MARKERS))
            self.assertFalse(any(marker in lowered for marker in NOTICE_MARKERS))
            self.assertIsNone(PARENTHETICAL_HEADING_RE.fullmatch(translation_text))
            self.assertFalse(any(marker in lowered for marker in BAD_FORMS))
            self.assertFalse(translation_text.startswith(("Book ", "PART ", "Section ")))

    def test_shangshu_mapping_metadata_matches_generated_qc(self) -> None:
        mapping = load_json(REPO_ROOT / "metadata" / "chinesenotes_work_mapping.yml")
        shangshu_mapping = next(item for item in mapping["works"] if item["chintransmem_work_id"] == "shangshu")
        alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "shangshu__alignment_qc.json")
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "shangshu.yml")
        summary = shangshu_mapping["generated_summary"]

        self.assertEqual(shangshu_mapping["status"], "already_ingested")
        self.assertEqual(shangshu_mapping["preferred_use"], "base_text")
        self.assertEqual(summary["total_section_count"], manifest["summary"]["section_count"])
        self.assertEqual(summary["active_section_count"], alignment_qc["summary"]["active_section_count"])
        self.assertEqual(summary["exportable_section_count"], alignment_qc["summary"]["exportable_section_count"])
        self.assertEqual(summary["exact_alignment_count"], alignment_qc["summary"]["exact_alignment_count"])
        self.assertEqual(summary["alignment_granularity_counts"], alignment_qc["summary"]["alignment_granularity_counts"])
        self.assertEqual(summary["curated_override_section_count"], alignment_qc["summary"]["curated_override_section_count"])
        self.assertEqual(summary["fallback_section_count"], alignment_qc["summary"]["fallback_section_count"])
        self.assertEqual(summary["blocked_section_count"], alignment_qc["summary"]["blocked_section_count"])
        self.assertEqual(summary["english_witness"], alignment_qc["summary"]["english_witness"])
        self.assertIn("Wikisource transcription of James Legge", shangshu_mapping["notes"])
        self.assertIn("130 exact alignments", shangshu_mapping["notes"])
        self.assertIn("2 blocked forged Chinese-only sections", shangshu_mapping["notes"])


if __name__ == "__main__":
    unittest.main()
