from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import load_json_compatible_yaml
from inventory_chinesenotes import build_inventory, infer_work_id_candidate


class ChineseNotesInventoryTest(unittest.TestCase):
    def test_build_inventory_detects_bilingual_legge_sample(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source_root = Path(temp_dir) / "chinesenotes"
            (source_root / "data" / "corpus").mkdir(parents=True)
            (source_root / "corpus" / "shijing").mkdir(parents=True)
            (source_root / "corpus" / "modern_articles").mkdir(parents=True)

            (source_root / "license.txt").write_text(
                "Apache 2.0 for code\nCC BY-SA 3.0 for text files\n",
                encoding="utf-8",
            )
            (source_root / "data" / "corpus" / "collections.csv").write_text(
                "\n".join(
                    [
                        "# Collection File, HTML Gloss File, Title, Description, Introduction File, Corpus, Language, Format, Period",
                        "shijing.csv\tshijing.html\tThe Book of Songs 詩經\tBilingual Legge corpus\tshijing/shijing000.txt\tLiterary Chinese\tBilingual\tPre-Han\tVerse",
                        "modern_articles.csv\tmodern.html\tMedia articles\tModern news corpus\t\\N\tModern Chinese\tProse\tModern\tnon-fiction",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (source_root / "data" / "corpus" / "shijing.csv").write_text(
                "\n".join(
                    [
                        "# Source file, Gloss output file, title",
                        "shijing/shijing001.txt\tshijing/shijing001.html\t國風‧周南‧關雎 Lessons from the states - Odes Of Zhou And The South - Guan Ju",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (source_root / "data" / "corpus" / "modern_articles.csv").write_text(
                "# Source file, Gloss output file, title\nmodern_articles/news001.txt\tmodern_articles/news001.html\tNews sample\n",
                encoding="utf-8",
            )
            (source_root / "corpus" / "shijing" / "shijing000.txt").write_text(
                "<h4>English translation</h4>\nEnglish translation: James Legge\n",
                encoding="utf-8",
            )
            (source_root / "corpus" / "shijing" / "shijing001.txt").write_text(
                "\n".join(
                    [
                        "關雎",
                        "關關雎鳩，在河之洲。",
                        "Kwan-kwan go the ospreys, on the islet in the river.",
                        "The modest maiden is a good match for the gentleman.",
                        "本作品在全世界都属于公有领域。",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (source_root / "corpus" / "modern_articles" / "news001.txt").write_text(
                "This is a modern article without classical relevance.\n",
                encoding="utf-8",
            )

            payload = build_inventory(source_root)
            records_by_path = {record["upstream_relative_path"]: record for record in payload["records"]}

        shijing = records_by_path["data/corpus/shijing.csv"]
        modern_articles = records_by_path["data/corpus/modern_articles.csv"]

        self.assertTrue(shijing["english_appears_present"])
        self.assertTrue(shijing["chinese_appears_present"])
        self.assertTrue(shijing["translator_attribution_appears"])
        self.assertTrue(shijing["public_domain_notice_appears"])
        self.assertEqual(shijing["likely_chintransmem_work_id_candidate"], "shijing")
        self.assertEqual(shijing["status"], "candidate")
        self.assertEqual(modern_articles["status"], "ignore")

    def test_alias_work_id_inference(self) -> None:
        self.assertEqual(infer_work_id_candidate("daodejing"), "laozi")
        self.assertEqual(infer_work_id_candidate("sunzibingfa"), "sunzi")
        self.assertIsNone(infer_work_id_candidate("modern_articles"))

    def test_committed_mapping_and_inventory_exist(self) -> None:
        mapping = load_json_compatible_yaml(REPO_ROOT / "metadata" / "chinesenotes_work_mapping.yml")
        work_ids = {entry["chintransmem_work_id"] for entry in mapping["works"]}
        self.assertEqual(
            work_ids,
            {
                "shijing",
                "lunyu",
                "mengzi",
                "zhuangzi",
                "xunzi",
                "hanfeizi",
                "zuozhuan",
                "shiji",
                "liji",
                "shangshu",
                "yijing",
                "mozi",
                "laozi",
                "liezi",
            },
        )
        inventory = load_json_compatible_yaml(REPO_ROOT / "metadata" / "chinesenotes_inventory.yml")
        self.assertEqual(inventory["upstream_repository"], "https://github.com/alexamies/chinesenotes.com")
        self.assertEqual(len(inventory["upstream_commit_sha"]), 40)
        self.assertGreater(inventory["summary"]["record_count"], 0)
        self.assertGreaterEqual(inventory["summary"]["english_detected_in_candidate_or_review_records"], 1)
        integration_plan = (REPO_ROOT / "documentation" / "chinesenotes_integration_plan.md").read_text(
            encoding="utf-8"
        )
        third_party_notice = (REPO_ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
        self.assertIn("# ChineseNotes integration plan", integration_plan)
        self.assertIn("alexamies/chinesenotes.com", third_party_notice)
        self.assertIn(inventory["upstream_commit_sha"], third_party_notice)


if __name__ == "__main__":
    unittest.main()
