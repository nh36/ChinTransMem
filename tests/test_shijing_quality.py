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

    def _context_for_blocks(
        self,
        *,
        chinese_blocks: list[str],
        translation_blocks: list[str],
    ) -> dict[str, object]:
        rows = []
        for index, (chinese_text, translation_text) in enumerate(zip(chinese_blocks, translation_blocks), start=1):
            row = deepcopy(self.row)
            row["alignment_id"] = f"test-alignment-{index}"
            row["order"] = index
            row["chinese_text"] = chinese_text
            row["translation_text"] = translation_text
            row["alignment_granularity"] = "stanza"
            row["is_coarse_alignment"] = False
            rows.append(row)
        return build_shijing_quality_context(
            manifest=self._single_section_manifest(),
            export_rows=rows,
        )

    def test_detect_suspicious_ocr_artifacts_flags_known_bad_examples(self) -> None:
        text = "\n".join(
            [
                "You, 0 Chung, are to be loved.",
                "But the words of m}r brothers.",
                r"In the country \vill ever hold to the right.",
                "The men of Ts4ing are in Seaou.",
                "The men of Tsing are in Cho'v.",
                "Ho'v splendid is his lambs fur.",
                "Where the girls were like flowering rushes. Although tliey are like flowering rushes.",
                "She in the thin white silk7.",
                "They will give me beautiful Ae^-stone.",
                "It is brothers who greatl)7 sympathize.",
                "My horses are greyj.",
                "A stray • bullet in running English should be reviewed.",
                "The impossible coiifure survives the OCR pass.",
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
        self.assertIn("paren_digit_intraword_artifact", issues_by_code)
        self.assertIn("greatl)7", issues_by_code["paren_digit_intraword_artifact"]["matches"])
        self.assertIn("trailing_j_artifact", issues_by_code)
        self.assertIn("greyj", issues_by_code["trailing_j_artifact"]["matches"])
        self.assertIn("apostrophe_vw_artifact", issues_by_code)
        self.assertTrue({"Cho'v", "Ho'v"} <= set(issues_by_code["apostrophe_vw_artifact"]["matches"]))
        self.assertIn("tli_wli_artifact", issues_by_code)
        self.assertIn("tliey", issues_by_code["tli_wli_artifact"]["matches"])
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

    def test_detect_suspicious_ocr_artifacts_flags_truncated_final_stanza(self) -> None:
        chinese_blocks = [
            "呦呦鹿鳴\n食野之苹\n我有嘉賓\n鼓瑟吹笙\n吹笙鼓簧\n承筐是將\n人之好我\n示我周行",
            "呦呦鹿鳴\n食野之蒿\n我有嘉賓\n德音孔昭\n視民不恌\n君子是則\n我有旨酒\n嘉賓式燕以敖",
            "呦呦鹿鳴\n食野之芩\n我有嘉賓\n鼓瑟鼓琴\n鼓瑟鼓琴\n和樂且湛\n我有旨酒\n以燕樂嘉賓之心",
        ]
        translation_blocks = [
            "With pleased sounds the deer call to one another,\nEating the celery of the fields.\nI have here admirable guests;\nThe lutes are struck, and the organ is blown for them.\nThe baskets of offerings also are presented to them.\nThe men love me,\nAnd will show me the perfect path.",
            "With pleased sounds the deer call to one another,\nEating the southernwood of the fields.\nI have here admirable guests,\nWhose virtuous fame is grandly brilliant.\nThe officers have in them a pattern and model.\nI have good wine,\nWhich my admirable guests drink, enjoying themselves.",
            "With pleased sounds the deer call to one another,\nEating the salsola of the fields.\nI have here admirable guests,",
        ]

        issues_by_code = {
            issue["code"]: issue
            for issue in detect_suspicious_ocr_artifacts(
                "\n\n".join(translation_blocks),
                chinese_blocks=chinese_blocks,
                english_blocks=translation_blocks,
            )
        }

        self.assertIn("terminal_truncation_punctuation", issues_by_code)
        self.assertIn("I have here admirable guests,", issues_by_code["terminal_truncation_punctuation"]["matches"])
        self.assertIn("truncated_final_stanza", issues_by_code)

    def test_exportable_ocr_text_with_suspicious_artifact_becomes_hard_failure(self) -> None:
        context = self._context_for_translation(
            "0 Chung, hear this faithful envoy and keep the willow court in peace while the bride • waits near the gate."
        )

        section = context["sections"][0]
        self.assertIn("zero_vocative_confusion", section["suspicious_ocr_artifact_markers"])
        self.assertIn("bullet_artifact", section["suspicious_ocr_artifact_markers"])
        self.assertIn("complete_contains_suspicious_ocr_artifact", section["hard_failure_codes"])
        self.assertEqual(context["summary"]["sections_with_suspicious_ocr_artifacts"], 1)

    def test_exportable_ocr_text_with_truncated_final_stanza_becomes_hard_failure(self) -> None:
        context = self._context_for_blocks(
            chinese_blocks=[
                "呦呦鹿鳴\n食野之苹\n我有嘉賓\n鼓瑟吹笙\n吹笙鼓簧\n承筐是將\n人之好我\n示我周行",
                "呦呦鹿鳴\n食野之蒿\n我有嘉賓\n德音孔昭\n視民不恌\n君子是則\n我有旨酒\n嘉賓式燕以敖",
                "呦呦鹿鳴\n食野之芩\n我有嘉賓\n鼓瑟鼓琴\n鼓瑟鼓琴\n和樂且湛\n我有旨酒\n以燕樂嘉賓之心",
            ],
            translation_blocks=[
                "With pleased sounds the deer call to one another,\nEating the celery of the fields.\nI have here admirable guests;\nThe lutes are struck, and the organ is blown for them.\nThe baskets of offerings also are presented to them.\nThe men love me,\nAnd will show me the perfect path.",
                "With pleased sounds the deer call to one another,\nEating the southernwood of the fields.\nI have here admirable guests,\nWhose virtuous fame is grandly brilliant.\nThe officers have in them a pattern and model.\nI have good wine,\nWhich my admirable guests drink, enjoying themselves.",
                "With pleased sounds the deer call to one another,\nEating the salsola of the fields.\nI have here admirable guests,",
            ],
        )

        section = context["sections"][0]
        self.assertIn("terminal_truncation_punctuation", section["suspicious_ocr_artifact_markers"])
        self.assertIn("truncated_final_stanza", section["suspicious_ocr_artifact_markers"])
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
