from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
API_DIR = REPO_ROOT / "web" / "api"
for path in (SCRIPTS_DIR, API_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from common import DEFAULT_WORK_ID, load_work_manifest
from import_corpus import import_corpus
from init_db import initialize_database
from corpus_api import CorpusApiHandler


class ApiTest(unittest.TestCase):
    def test_work_and_section_routes(self) -> None:
        lunyu_manifest = load_work_manifest(DEFAULT_WORK_ID)
        mengzi_manifest = load_work_manifest("mengzi")
        shijing_manifest = load_work_manifest("shijing")
        first_section = lunyu_manifest["sections"][0]
        first_mengzi_section = mengzi_manifest["sections"][0]
        first_shijing_section = shijing_manifest["sections"][0]
        first_sbe_shijing_section = shijing_manifest["sections"][1]

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "corpus.sqlite3"
            initialize_database(db_path)
            import_corpus(db_path)

            handler = type("ConfiguredCorpusApiHandler", (CorpusApiHandler,), {"db_path": db_path})
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base_url = f"http://127.0.0.1:{server.server_port}"

                health = self._get_json(f"{base_url}/health")
                works = self._get_json(f"{base_url}/works")
                work_sections = self._get_json(f"{base_url}/works/{DEFAULT_WORK_ID}/sections")
                mengzi_sections = self._get_json(f"{base_url}/works/mengzi/sections")
                shijing_sections = self._get_json(f"{base_url}/works/shijing/sections")
                compatibility_sections = self._get_json(f"{base_url}/sections")
                work_passages = self._get_json(
                    f"{base_url}/works/{DEFAULT_WORK_ID}/sections/{first_section['section_id']}/passages"
                )
                mengzi_passages = self._get_json(
                    f"{base_url}/works/mengzi/sections/{first_mengzi_section['section_id']}/passages"
                )
                shijing_passages = self._get_json(
                    f"{base_url}/works/shijing/sections/{first_shijing_section['section_id']}/passages"
                )
                shijing_sbe_passages = self._get_json(
                    f"{base_url}/works/shijing/sections/{first_sbe_shijing_section['section_id']}/passages"
                )
                compatibility_passages = self._get_json(f"{base_url}/sections/{first_section['section_id']}/passages")
            finally:
                server.shutdown()
                thread.join(timeout=5)
                server.server_close()

        self.assertEqual(health["status"], "ok")
        work_ids = {work["work_id"] for work in works["works"]}
        self.assertIn("lunyu", work_ids)
        self.assertIn("mengzi", work_ids)
        self.assertIn("shijing", work_ids)
        self.assertEqual(len(work_sections["sections"]), lunyu_manifest["summary"]["section_count"])
        self.assertEqual(len(mengzi_sections["sections"]), mengzi_manifest["summary"]["section_count"])
        self.assertEqual(len(shijing_sections["sections"]), shijing_manifest["summary"]["section_count"])
        self.assertEqual(len(compatibility_sections["sections"]), lunyu_manifest["summary"]["section_count"])
        self.assertEqual(work_sections["sections"][0]["expected_exact_alignment_count"], first_section["expected_exact_alignment_count"])
        self.assertEqual(work_passages["work_id"], DEFAULT_WORK_ID)
        self.assertEqual(work_passages["section_id"], first_section["section_id"])
        self.assertEqual(len(work_passages["rows"]), first_section["expected_exact_alignment_count"])
        self.assertEqual(mengzi_passages["work_id"], "mengzi")
        self.assertEqual(mengzi_passages["section_id"], first_mengzi_section["section_id"])
        self.assertEqual(len(mengzi_passages["rows"]), first_mengzi_section["expected_exact_alignment_count"])
        self.assertEqual(shijing_passages["work_id"], "shijing")
        self.assertEqual(shijing_passages["section_id"], first_shijing_section["section_id"])
        self.assertEqual(len(shijing_passages["rows"]), first_shijing_section["expected_exact_alignment_count"])
        self.assertEqual(shijing_sbe_passages["work_id"], "shijing")
        self.assertEqual(shijing_sbe_passages["section_id"], first_sbe_shijing_section["section_id"])
        self.assertEqual(len(shijing_sbe_passages["rows"]), first_sbe_shijing_section["expected_exact_alignment_count"])
        self.assertEqual(compatibility_passages["section_id"], first_section["section_id"])
        self.assertEqual(len(compatibility_passages["rows"]), first_section["expected_exact_alignment_count"])

    def _get_json(self, url: str) -> dict[str, object]:
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read().decode("utf-8"))
