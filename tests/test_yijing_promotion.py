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
OCR_MARKER_RE = re.compile(
    r"\b[a-z]{2,}[A-Z][a-z]{2,}\b|\b[a-z]{2,}-\s+[A-Za-z]{2,}\b|\b[A-Za-z]{2,}[,;:_^][A-Za-z]{2,}\b|\b1\s+[a-z]{2,}\b"
)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def line_position_from_chinese(source_text: str) -> str | None:
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


def line_position_from_translation(translation_text: str) -> str | None:
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


class YijingPromotionTest(unittest.TestCase):
    def test_yijing_is_active_with_complete_provenance(self) -> None:
        works = load_json(REPO_ROOT / "metadata" / "works.yml")
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "yijing.yml")
        inventory = load_json(REPO_ROOT / "metadata" / "yijing_inventory.yml")
        ledger = load_json(REPO_ROOT / "metadata" / "yijing_verification_ledger.yml")
        sources = [row for row in load_json(REPO_ROOT / "metadata" / "sources.yml") if row["work_id"] == "yijing"]

        self.assertIn("yijing", {work["work_id"] for work in works})
        self.assertEqual(manifest["summary"]["section_count"], 64)
        self.assertEqual(manifest["summary"]["complete_sections"], 64)
        self.assertEqual(manifest["summary"]["metadata_only_sections"], 0)
        self.assertEqual(manifest["summary"]["exact_alignment_count"], 450)
        self.assertEqual(len(manifest["sections"]), 64)
        self.assertEqual(len(inventory["units"]), 64)
        self.assertEqual(len(ledger["entries"]), 64)
        self.assertEqual(len(sources), 128)

        self.assertEqual({entry["decision"] for entry in ledger["entries"]}, {"export"})
        for entry in ledger["entries"]:
            self.assertEqual(len(entry["upstream_commit_sha"]), 40)
            self.assertEqual(entry["upstream_repository_url"], "https://github.com/alexamies/chinesenotes.com")
            self.assertTrue(entry["local_raw_capture_path"].startswith("corpus/raw/chinesenotes/"))
            self.assertTrue(entry["processed_source_path"].startswith("corpus/processed/chinese_base_texts/"))
            self.assertTrue(entry["processed_translation_path"].startswith("corpus/processed/translations/"))
            self.assertTrue(entry["processed_alignment_path"].startswith("corpus/processed/alignments/"))
            self.assertEqual(entry["alignment_status"], "complete")
            self.assertEqual(entry["verification_status"], "verified_transcribed_text")
            self.assertFalse(entry["fallback_used"])
            self.assertFalse(entry["curated_override_used"])
            self.assertTrue((REPO_ROOT / entry["local_raw_capture_path"]).exists())
            self.assertTrue((REPO_ROOT / entry["processed_source_path"]).exists())
            self.assertTrue((REPO_ROOT / entry["processed_translation_path"]).exists())
            self.assertTrue((REPO_ROOT / entry["processed_alignment_path"]).exists())

        for source in sources:
            self.assertEqual(source["rights_status"], "public_domain")
            self.assertTrue(source["source_url"].startswith("https://github.com/alexamies/chinesenotes.com/blob/"))
            self.assertTrue((REPO_ROOT / source["raw_path"]).exists())
            self.assertTrue((REPO_ROOT / source["processed_path"]).exists())
            if source["language_code"] == "en":
                self.assertIn("James Legge", source["citation"])

    def test_yijing_exports_and_qc_are_clean(self) -> None:
        export_paths = corpus_export_paths("yijing")
        rows = load_jsonl(export_paths["jsonl"])
        qc_report = load_json(REPO_ROOT / "logs" / "qc_reports" / "yijing__corpus_qc.json")
        alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "yijing__alignment_qc.json")

        self.assertTrue(export_paths["jsonl"].exists())
        self.assertTrue(export_paths["csv"].exists())
        self.assertTrue(export_paths["tmx"].exists())
        self.assertEqual(qc_report["status"], "pass")
        self.assertEqual(qc_report["hard_failure_count"], 0)
        self.assertFalse(qc_report["text_integrity"]["empty_source_sections"])
        self.assertFalse(qc_report["text_integrity"]["empty_translation_sections"])
        self.assertFalse(qc_report["text_integrity"]["translation_with_chinese_sections"])
        self.assertFalse(qc_report["text_integrity"]["translation_with_notice_sections"])
        self.assertFalse(qc_report["text_integrity"]["translation_with_commentary_sections"])
        self.assertFalse(qc_report["text_integrity"]["translation_with_heading_sections"])
        self.assertFalse(qc_report["text_integrity"]["translation_with_ocr_corruption_rows"])
        self.assertFalse(qc_report["alignment_quality"]["false_precision_multi_clause_targets"])
        self.assertFalse(qc_report["alignment_quality"]["question_punctuation_mismatches"])
        self.assertFalse(qc_report["alignment_quality"]["suspicious_length_imbalance_rows"])
        self.assertFalse(qc_report["alignment_quality"]["non_grouped_segmentation_mismatch_rows"])
        self.assertFalse(qc_report["alignment_quality"]["alignment_drift_issues"])

        self.assertEqual(alignment_qc["summary"]["total_section_count"], 64)
        self.assertEqual(alignment_qc["summary"]["active_section_count"], 64)
        self.assertEqual(alignment_qc["summary"]["exportable_section_count"], 64)
        self.assertEqual(alignment_qc["summary"]["exact_alignment_count"], 450)
        self.assertEqual(alignment_qc["summary"]["alignment_granularity_counts"], {"block": 450})
        self.assertEqual(alignment_qc["summary"]["curated_override_section_count"], 0)
        self.assertEqual(alignment_qc["summary"]["fallback_section_count"], 0)
        self.assertEqual(alignment_qc["summary"]["blocked_section_count"], 0)
        self.assertEqual(alignment_qc["summary"]["remaining_corruption_issue_count"], 0)
        self.assertEqual(alignment_qc["summary"]["remaining_drift_issue_count"], 0)
        self.assertEqual(alignment_qc["summary"]["hard_failure_count"], 0)
        self.assertEqual(len(rows), 450)
        self.assertEqual(len({row["section_id"] for row in rows}), 64)

        for row in rows:
            source_text = str(row["chinese_text"]).strip()
            translation_text = str(row["translation_text"]).strip()
            lowered = translation_text.casefold()
            self.assertTrue(source_text)
            self.assertTrue(translation_text)
            self.assertIsNone(CJK_RE.search(translation_text))
            self.assertFalse(any(marker in lowered for marker in YIJING_NOTICE_MARKERS))
            self.assertFalse(any(marker in lowered for marker in YIJING_COMMENTARY_MARKERS))
            self.assertIsNone(OCR_MARKER_RE.search(translation_text))

    def test_yijing_line_positions_remain_aligned(self) -> None:
        rows = load_jsonl(corpus_export_paths("yijing")["jsonl"])
        for row in rows:
            source_text = str(row["chinese_text"]).strip()
            translation_text = str(row["translation_text"]).strip()
            source_position = line_position_from_chinese(source_text)
            if source_position is None:
                continue
            self.assertEqual(
                source_position,
                line_position_from_translation(translation_text),
                msg=f"Line-position drift in {row['alignment_id']}: {source_text!r} vs {translation_text!r}",
            )

    def test_yijing_mapping_summary_matches_generated_outputs(self) -> None:
        mapping = load_json(REPO_ROOT / "metadata" / "chinesenotes_work_mapping.yml")
        yijing_mapping = next(item for item in mapping["works"] if item["chintransmem_work_id"] == "yijing")
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "yijing.yml")
        alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "yijing__alignment_qc.json")
        summary = yijing_mapping["generated_summary"]

        self.assertEqual(yijing_mapping["status"], "already_ingested")
        self.assertEqual(yijing_mapping["english_coverage"], "complete")
        self.assertEqual(yijing_mapping["chinese_coverage"], "complete")
        self.assertEqual(yijing_mapping["preferred_use"], "base_text")
        self.assertEqual(summary["total_section_count"], manifest["summary"]["section_count"])
        self.assertEqual(summary["active_section_count"], alignment_qc["summary"]["active_section_count"])
        self.assertEqual(summary["exportable_section_count"], alignment_qc["summary"]["exportable_section_count"])
        self.assertEqual(summary["exact_alignment_count"], alignment_qc["summary"]["exact_alignment_count"])
        self.assertEqual(summary["alignment_granularity_counts"], alignment_qc["summary"]["alignment_granularity_counts"])
        self.assertEqual(summary["curated_override_section_count"], alignment_qc["summary"]["curated_override_section_count"])
        self.assertEqual(summary["fallback_section_count"], alignment_qc["summary"]["fallback_section_count"])
        self.assertEqual(summary["blocked_section_count"], alignment_qc["summary"]["blocked_section_count"])
        self.assertEqual(summary["remaining_drift_issue_count"], alignment_qc["summary"]["remaining_drift_issue_count"])
        self.assertEqual(summary["english_witness"], alignment_qc["summary"]["english_witness"])
        self.assertIn("64 active hexagrams", yijing_mapping["notes"])
        self.assertIn("450 exact alignments", yijing_mapping["notes"])
        self.assertIn("Ten Wings commentary and trigram headings excluded", yijing_mapping["notes"])

    def test_existing_work_guardrails_remain_stable(self) -> None:
        laozi_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "laozi.yml")
        laozi_alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "laozi__alignment_qc.json")
        shangshu_manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "shangshu.yml")
        shangshu_alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "shangshu__alignment_qc.json")
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

        self.assertEqual(shijing_manifest["summary"]["section_count"], 305)
        self.assertEqual(shijing_manifest["summary"]["complete_sections"], 305)
        self.assertEqual(shijing_manifest["summary"]["metadata_only_sections"], 0)


if __name__ == "__main__":
    unittest.main()
