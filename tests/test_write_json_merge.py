from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

# Ensure scripts/ is on sys.path so tests can import project scripts as modules
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
import sys
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import common


class WriteJsonMergeTest(unittest.TestCase):
    def test_safe_merge_preserves_existing_and_updates(self) -> None:
        tmp_dir = tempfile.TemporaryDirectory()
        try:
            tmp = Path(tmp_dir.name)
            old_md = common.METADATA_DIR
            common.METADATA_DIR = tmp
            tmp.mkdir(parents=True, exist_ok=True)
            sources_path = tmp / "sources.yml"
            initial = [
                {
                    "source_id": "s1",
                    "work_id": "lunyu",
                    "section_id": "sec1",
                    "author_or_translator_ids": ["a1"],
                    "processed_path": "p1",
                    "raw_path": "r1",
                    "rights_status": "public_domain",
                    "source_kind": "wikisource",
                    "language_code": "zh",
                },
                {
                    "source_id": "s2",
                    "work_id": "mozi",
                    "section_id": "sec2",
                    "author_or_translator_ids": ["a2"],
                    "processed_path": "p2",
                    "raw_path": "r2",
                    "rights_status": "public_domain",
                    "source_kind": "wikisource",
                    "language_code": "zh",
                },
            ]
            sources_path.write_text(json.dumps(initial, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

            new_payload = [
                {
                    "source_id": "s2",
                    "work_id": "mozi",
                    "section_id": "sec2",
                    "author_or_translator_ids": ["a2_updated"],
                    "processed_path": "p2_new",
                    "raw_path": "r2",
                    "rights_status": "public_domain",
                    "source_kind": "wikisource",
                    "language_code": "zh",
                },
                {
                    "source_id": "s3",
                    "work_id": "shiji",
                    "section_id": "sec3",
                    "author_or_translator_ids": [],
                    "processed_path": "p3",
                    "raw_path": "r3",
                    "rights_status": "rights_review_required",
                    "source_kind": "processed_translation",
                    "language_code": "en",
                },
            ]

            common.write_json(sources_path, new_payload)
            merged = json.loads(sources_path.read_text(encoding="utf8"))
            ids = [s["source_id"] for s in merged]
            self.assertIn("s1", ids)
            self.assertIn("s2", ids)
            self.assertIn("s3", ids)
            # check s2 updated
            s2 = next(s for s in merged if s["source_id"] == "s2")
            self.assertEqual(s2.get("processed_path"), "p2_new")
        finally:
            common.METADATA_DIR = old_md
            tmp_dir.cleanup()


if __name__ == "__main__":
    unittest.main()
