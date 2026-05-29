from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from export_pilot import export_pilot
from import_lunyu_legge_pilot import import_pilot
from init_db import initialize_database
from qc_pilot import run_qc
from validate_tmx import validate_tmx_export


class PilotWorkflowTest(unittest.TestCase):
    def test_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "pilot.sqlite3"
            jsonl_output = temp_path / "aligned.jsonl"
            csv_output = temp_path / "aligned.csv"
            tmx_output = temp_path / "aligned.tmx"
            qc_output = temp_path / "qc.json"
            tmx_validation_output = temp_path / "tmx-validation.json"

            initialize_database(db_path)
            import_summary = import_pilot(db_path)
            export_summary = export_pilot(db_path, jsonl_output, csv_output, tmx_output)
            tmx_validation_summary = validate_tmx_export(db_path, tmx_output, tmx_validation_output)
            qc_summary = run_qc(db_path, qc_output)

            self.assertEqual(import_summary["segments"], 32)
            self.assertEqual(import_summary["alignments"], 17)
            self.assertEqual(export_summary["rows_exported"], 16)
            self.assertEqual(tmx_validation_summary["status"], "pass")
            self.assertEqual(tmx_validation_summary["tu_count"], 16)
            self.assertEqual(qc_summary["status"], "pass")
            self.assertEqual(len(qc_summary["many_to_many_alignment_ids"]), 1)

            with sqlite3.connect(db_path) as connection:
                segment_count = connection.execute("SELECT COUNT(*) FROM segments").fetchone()[0]
                alignment_count = connection.execute("SELECT COUNT(*) FROM alignments").fetchone()[0]
            self.assertEqual(segment_count, 32)
            self.assertEqual(alignment_count, 17)

            exported_rows = [
                json.loads(line)
                for line in jsonl_output.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual(exported_rows[0]["chinese_ref"], "論語 1.1")
            self.assertEqual(exported_rows[0]["translation_ref"], "Analects I.1")
            self.assertTrue(exported_rows[4]["translation_text"].startswith('The Master said, "To rule'))
            self.assertEqual(exported_rows[-1]["translation_ref"], "Analects I.16")
            self.assertTrue(tmx_output.exists())
