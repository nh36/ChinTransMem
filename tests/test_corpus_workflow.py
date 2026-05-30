from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import METADATA_DIR, load_corpus_manifest, load_json_compatible_yaml, read_jsonl
from export_corpus import load_exact_alignment_rows, write_tmx
from import_corpus import import_corpus
from init_db import initialize_database
from qc_corpus import run_qc
from validate_tmx import validate_tmx_file


class CorpusWorkflowTest(unittest.TestCase):
    def test_end_to_end(self) -> None:
        manifest = load_corpus_manifest()
        expected_exact_alignment_count = manifest["summary"]["exact_alignment_count"]
        expected_section_count = manifest["summary"]["section_count"]
        expected_segment_count = sum(
            len(read_jsonl(REPO_ROOT / source["processed_path"]))
            for source in load_json_compatible_yaml(METADATA_DIR / "sources.yml")
            if str(source["processed_path"]).endswith(".jsonl")
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "corpus.sqlite3"
            qc_output = temp_path / "qc.json"
            corpus_tmx = temp_path / "lunyu__all__aligned_passages.tmx"
            tmx_validation_output = temp_path / "lunyu__corpus_tmx_validation.json"

            initialize_database(db_path)
            import_summary = import_corpus(db_path)
            corpus_rows = load_exact_alignment_rows(db_path)
            write_tmx(corpus_rows, corpus_tmx)
            tmx_validation_summary = validate_tmx_file(db_path, corpus_tmx, tmx_validation_output)
            qc_summary = run_qc(db_path, qc_output)

            self.assertEqual(import_summary["section_count"], expected_section_count)
            self.assertEqual(import_summary["segments"], expected_segment_count)
            self.assertEqual(import_summary["alignments"], expected_exact_alignment_count + expected_section_count)
            self.assertEqual(len(corpus_rows), expected_exact_alignment_count)
            self.assertEqual(tmx_validation_summary["status"], "pass")
            self.assertEqual(qc_summary["status"], "pass")
            self.assertEqual(len(qc_summary["sections"]), expected_section_count)

            with sqlite3.connect(db_path) as connection:
                segment_count = connection.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
                alignment_count = connection.execute("SELECT COUNT(*) FROM alignments").fetchone()[0]
            self.assertEqual(segment_count, expected_segment_count)
            self.assertEqual(alignment_count, expected_exact_alignment_count + expected_section_count)

            last_section_id = manifest["sections"][-1]["section_id"]
            last_rows = load_exact_alignment_rows(db_path, last_section_id)
            self.assertEqual(len(last_rows), manifest["sections"][-1]["expected_exact_alignment_count"])
            body = ET.parse(corpus_tmx).getroot().find("./body")
            self.assertIsNotNone(body)
