from __future__ import annotations

import sys
import unittest
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import corpus_export_paths, load_json_compatible_yaml, load_work_manifest, read_jsonl
from shijing_quality import build_shijing_quality_context, detect_suspicious_ocr_artifacts


class ShijingQualitySanityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.quality_report = load_json_compatible_yaml(
            REPO_ROOT / "logs" / "qc_reports" / "shijing__completion_quality.json"
        )
        cls.manifest = load_work_manifest("shijing")
        cls.export_rows = read_jsonl(corpus_export_paths("shijing")["jsonl"])
        cls.section_id = next(
            section["section_id"]
            for section in cls.quality_report["sections"]
            if section["verification_status"] == "human_verified_ocr"
        )
        cls.section = next(
            deepcopy(section)
            for section in cls.manifest["sections"]
            if section["section_id"] == cls.section_id
        )
        cls.row = next(
            deepcopy(row)
            for row in cls.export_rows
            if row["section_id"] == cls.section_id
        )

    def _single_section_manifest(self) -> dict[str, object]:
        return {
            "work_id": "shijing",
            "summary": {
                "section_count": 1,
                "extant_poem_count": 1,
                "complete_sections": 1,
                "metadata_only_sections": 0,
                "exact_alignment_count": 1,
            },
            "sections": [deepcopy(self.section)],
            "sources": self.manifest["sources"],
        }

    def _context_for_translation(self, translation_text: str) -> dict[str, object]:
        row = deepcopy(self.row)
        row["translation_text"] = translation_text
        return build_shijing_quality_context(
            manifest=self._single_section_manifest(),
            export_rows=[row],
        )

    def test_detect_suspicious_ocr_artifacts_flags_known_bad_examples(self) -> None:
        text = "\n".join(
            [
                "0 Chung, the herald answers the call.",
                "The m}r token should never survive source review.",
                r"The \vill fragment is an OCR scar, not a word.",
                "Ts4ing and silk7 both show digit contamination inside words.",
                "Cho'v and Ho'v preserve apostrophe-v OCR damage.",
                "Wliere tliey wander, the coiifure remains impossible English.",
                "The Ae^-stone token still shows a stray caret.",
                "A stray • bullet in running English should be reviewed.",
            ]
        )

        issues_by_code = {
            issue["code"]: issue
            for issue in detect_suspicious_ocr_artifacts(text)
        }

        self.assertIn("zero_vocative_confusion", issues_by_code)
        self.assertIn("0 Chung", issues_by_code["zero_vocative_confusion"]["matches"])
        self.assertIn("digit_letter_confusion", issues_by_code)
        self.assertTrue({"Ts4ing", "silk7"} <= set(issues_by_code["digit_letter_confusion"]["matches"]))
        self.assertIn("apostrophe_vw_artifact", issues_by_code)
        self.assertTrue({"Cho'v", "Ho'v"} <= set(issues_by_code["apostrophe_vw_artifact"]["matches"]))
        self.assertIn("tli_wli_artifact", issues_by_code)
        self.assertTrue({"Wliere", "tliey"} <= set(issues_by_code["tli_wli_artifact"]["matches"]))
        self.assertIn("double_i_artifact", issues_by_code)
        self.assertIn("coiifure", issues_by_code["double_i_artifact"]["matches"])
        self.assertIn("brace_artifact", issues_by_code)
        self.assertIn("backslash_artifact", issues_by_code)
        self.assertIn("caret_artifact", issues_by_code)
        self.assertIn("bullet_artifact", issues_by_code)

    def test_detect_suspicious_ocr_artifacts_honors_source_checked_override(self) -> None:
        self.assertEqual(
            detect_suspicious_ocr_artifacts(
                "0 Chung answers the call.",
                {"zero_vocative_confusion": {"0 Chung"}},
            ),
            [],
        )

    def test_exportable_ocr_text_with_suspicious_artifact_becomes_hard_failure(self) -> None:
        context = self._context_for_translation(
            "0 Chung, hear this faithful envoy and keep the willow court in peace while the bride • waits near the gate."
        )

        section = context["sections"][0]
        self.assertIn("zero_vocative_confusion", section["suspicious_ocr_artifact_markers"])
        self.assertIn("bullet_artifact", section["suspicious_ocr_artifact_markers"])
        self.assertIn("complete_contains_suspicious_ocr_artifact", section["hard_failure_codes"])
        self.assertEqual(context["summary"]["sections_with_suspicious_ocr_artifacts"], 1)

    def test_exportable_ocr_text_with_embedded_chinese_becomes_hard_failure(self) -> None:
        context = self._context_for_translation(
            "This translation has stray 采蘩詩 characters embedded inside otherwise English wording and enough additional words to trigger the export guardrail."
        )

        section = context["sections"][0]
        self.assertTrue(section["contains_chinese_in_english_segment"])
        self.assertIn("chinese_in_english_segment", section["warning_codes"])
        self.assertIn("complete_contains_chinese_text", section["hard_failure_codes"])


if __name__ == "__main__":
    unittest.main()
