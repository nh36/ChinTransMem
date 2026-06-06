from __future__ import annotations

import sys
import re
import unittest
from pathlib import Path

# Ensure scripts/ is on sys.path so tests can import project scripts as modules
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import REPO_ROOT
from common import read_jsonl
from shiji_quality import compare_shiji_entity_sequences
from chinesenotes_alignment import load_alignment_anchor_maps


class ShijiWitnessQualityTest(unittest.TestCase):
    def test_shiji_003_translation_text_has_no_known_bad_forms(self) -> None:
        path = REPO_ROOT / "corpus" / "exports" / "jsonl" / "shiji__shiji-003-annals-of-yin__aligned_passages.jsonl"
        self.assertTrue(path.exists(), msg=f"Expected export file missing: {path}")
        rows = read_jsonl(path)
        # Tokens that should be matched case-insensitively (misspellings, generic parenthetical glosses)
        bad_tokens_ci = [
            "succeseful",
            " (luminous)",
            " (view land)",
            " (bright-like)",
            " (cattle-pens)",
            " (obscure)",
            " (shake)",
            " (diminutive)",
            " (report d)",
            " (report b)",
            " (report c)",
            " (lord i)",
            " (lord j)",
            " (heaven b)",
            " (documents)",
        ]
        # Tokens where exact case matters (romanization or capitalization issues)
        bad_tokens_exact = ["Zao Yu", "Zhu gui"]

        found_in_raw = set()
        for row in rows:
            text = str(row.get("translation_text", ""))
            raw = str(row.get("translation_text_raw", ""))
            lower_text = text.lower()
            lower_raw = raw.lower()
            for token in bad_tokens_ci:
                self.assertNotIn(
                    token.lower(),
                    lower_text,
                    msg=f"Bad token '{token}' found in cleaned translation_text for alignment {row.get('alignment_id')}",
                )
                if token.lower() in lower_raw:
                    found_in_raw.add(token)
            for token in bad_tokens_exact:
                self.assertNotIn(
                    token,
                    text,
                    msg=f"Bad token '{token}' found in cleaned translation_text for alignment {row.get('alignment_id')}",
                )
                if token in raw:
                    found_in_raw.add(token)


    def test_shiji_003_entity_sequence_not_mismatch(self) -> None:
        path = REPO_ROOT / "corpus" / "exports" / "jsonl" / "shiji__shiji-003-annals-of-yin__aligned_passages.jsonl"
        rows = read_jsonl(path)
        anchors = load_alignment_anchor_maps(REPO_ROOT / "metadata" / "shiji_alignment_anchors.yml")
        anchor_map = anchors.get("shiji-003") or {}
        anchor_list = list(anchor_map.get("anchors", []))
        for row in rows:
            chinese_text = str(row.get("chinese_text", ""))
            translation_text = str(row.get("translation_text", ""))
            result = compare_shiji_entity_sequences(chinese_text, translation_text, anchor_list)
            verdict = result.get("entity_sequence_verdict")
            self.assertNotEqual(
                verdict,
                "mismatch",
                msg=(f"Entity sequence mismatch for alignment {row.get('alignment_id')}: {verdict}")
            )


if __name__ == "__main__":
    unittest.main()
