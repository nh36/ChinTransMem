from __future__ import annotations

import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import corpus_export_paths

CJK_RE = re.compile(r"[\u3400-\u9fff]")
NOTICE_MARKERS = (
    "english translation:",
    "chinese text:",
    "public domain worldwide",
    "this work was published before january 1, 1923",
    "english translations",
    "legge 1891",
)
COMMENTARY_MARKERS = ("〈", "〉", "編者按", "河上", "注釋")
PARENTHETICAL_HEADING_RE = re.compile(r"^\([^()]{1,120}\)$")


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class LaoziPromotionTest(unittest.TestCase):
    def test_laozi_is_active_with_81_chapters_and_provenance(self) -> None:
        works = load_json(REPO_ROOT / "metadata" / "works.yml")
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "laozi.yml")
        inventory = load_json(REPO_ROOT / "metadata" / "laozi_inventory.yml")
        ledger = load_json(REPO_ROOT / "metadata" / "laozi_verification_ledger.yml")
        sources = [row for row in load_json(REPO_ROOT / "metadata" / "sources.yml") if row["work_id"] == "laozi"]

        self.assertIn("laozi", {work["work_id"] for work in works})
        self.assertEqual(manifest["summary"]["section_count"], 81)
        self.assertEqual(manifest["summary"]["complete_sections"], 81)
        self.assertEqual(manifest["summary"]["metadata_only_sections"], 0)
        self.assertEqual(len(manifest["sections"]), 81)
        self.assertEqual(len(inventory["units"]), 81)
        self.assertEqual(len(ledger["entries"]), 81)
        self.assertEqual(len(sources), 162)

        decisions = {entry["decision"] for entry in ledger["entries"]}
        self.assertEqual(decisions, {"export"})
        for entry in ledger["entries"]:
            self.assertEqual(len(entry["upstream_commit_sha"]), 40)
            self.assertEqual(entry["upstream_repository_url"], "https://github.com/alexamies/chinesenotes.com")
            self.assertTrue(entry["local_raw_capture_path"].startswith("corpus/raw/chinesenotes/"))
            self.assertTrue(entry["processed_source_path"].startswith("corpus/processed/chinese_base_texts/"))
            self.assertTrue(entry["processed_translation_path"].startswith("corpus/processed/translations/"))

        for source in sources:
            self.assertEqual(source["rights_status"], "public_domain")
            self.assertTrue(source["source_url"].startswith("https://github.com/alexamies/chinesenotes.com/blob/"))
            self.assertTrue((REPO_ROOT / source["raw_path"]).exists())
            self.assertTrue((REPO_ROOT / source["processed_path"]).exists())
            if source["language_code"] == "en":
                self.assertIn("Legge 1891", source["notes"])
            self.assertIn("Review date: 2026-05-31", source["notes"])
        self.assertTrue((REPO_ROOT / "metadata" / "laozi_alignment_overrides.yml").exists())

    def test_laozi_exports_and_qc_are_clean(self) -> None:
        export_paths = corpus_export_paths("laozi")
        export_jsonl = export_paths["jsonl"]
        export_csv = export_paths["csv"]
        export_tmx = export_paths["tmx"]
        qc_report = load_json(REPO_ROOT / "logs" / "qc_reports" / "laozi__corpus_qc.json")
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
        self.assertFalse(qc_report["alignment_quality"]["false_precision_multi_clause_targets"])
        self.assertFalse(qc_report["alignment_quality"]["question_punctuation_mismatches"])
        self.assertFalse(qc_report["alignment_quality"]["suspicious_length_imbalance_rows"])

        self.assertEqual(len({row["section_id"] for row in rows}), 81)
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
            if row["alignment_granularity"] == "chapter":
                self.assertTrue(row["is_coarse_alignment"])
                self.assertTrue(row["coarse_alignment_reason"])

    def test_chapter_five_alignment_is_repaired(self) -> None:
        rows = load_jsonl(REPO_ROOT / "corpus" / "exports" / "jsonl" / "laozi__laozi-chapter-005__aligned_passages.jsonl")

        self.assertEqual(len(rows), 9)
        self.assertEqual(rows[0]["chinese_text"], "天地不仁，")
        self.assertEqual(
            rows[0]["translation_text"],
            "Heaven and earth do not act from (the impulse of) any wish to be benevolent;",
        )
        self.assertNotIn("The sages do not act", rows[0]["translation_text"])
        bellows_row = next(row for row in rows if row["translation_text"] == "May not the space between heaven and earth be compared to a bellows?")
        self.assertEqual(bellows_row["chinese_text"], "天地之間，其猶橐籥乎？")
        self.assertEqual(bellows_row["source_segment_count"], 2)
        self.assertEqual(bellows_row["target_segment_count"], 1)

    def test_laozi_alignment_qc_and_shijing_stability(self) -> None:
        alignment_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "laozi__alignment_qc.json")
        rows = load_jsonl(corpus_export_paths("laozi")["jsonl"])
        granularity_counts = Counter(row["alignment_granularity"] for row in rows)
        manifest = load_json(REPO_ROOT / "metadata" / "manifests" / "shijing.yml")
        lunyu_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "lunyu__corpus_qc.json")
        mengzi_qc = load_json(REPO_ROOT / "logs" / "qc_reports" / "mengzi__corpus_qc.json")

        self.assertEqual(alignment_qc["active_chapter_count"], 81)
        self.assertEqual(alignment_qc["counts_by_granularity"], dict(granularity_counts))
        self.assertGreater(alignment_qc["exact_alignment_count"], 260)
        self.assertGreater(alignment_qc["automatic_fine_grained_alignment_count"], 0)
        self.assertGreaterEqual(alignment_qc["curated_override_chapter_count"], 1)
        self.assertIn("laozi-chapter-062", {item["section_id"] for item in alignment_qc["curated_override_sections"]})
        self.assertLess(alignment_qc["chapter_fallback_count"], 47)
        self.assertEqual(len(alignment_qc["chapter_fallbacks"]), alignment_qc["chapter_fallback_count"])
        self.assertEqual(alignment_qc["blocked_chapter_count"], 0)
        self.assertEqual(alignment_qc["hard_failure_count"], 0)
        self.assertGreater(granularity_counts["sentence"] + granularity_counts["block"] + granularity_counts["grouped"], 0)
        self.assertTrue(all(item["coarse_alignment_reason"] for item in alignment_qc["chapter_fallbacks"]))
        self.assertEqual(lunyu_qc["status"], "pass")
        self.assertEqual(mengzi_qc["status"], "pass")

        self.assertEqual(manifest["summary"]["section_count"], 305)
        self.assertEqual(manifest["summary"]["complete_sections"], 305)
        self.assertEqual(manifest["summary"]["metadata_only_sections"], 0)


if __name__ == "__main__":
    unittest.main()
