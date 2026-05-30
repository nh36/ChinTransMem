from __future__ import annotations

from contextlib import closing
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

from common import DEFAULT_WORK_ID, METADATA_DIR, load_work_manifest, load_json_compatible_yaml, read_jsonl
from export_corpus import load_exact_alignment_rows, write_tmx
from import_corpus import import_corpus
from init_db import initialize_database
from qc_corpus import run_qc
from validate_tmx import validate_tmx_file


class CorpusWorkflowTest(unittest.TestCase):
    def test_lunyu_workflow_counts_and_qc(self) -> None:
        manifest = load_work_manifest(DEFAULT_WORK_ID)
        works = load_json_compatible_yaml(METADATA_DIR / "works.yml")
        sections = load_json_compatible_yaml(METADATA_DIR / "sections.yml")
        sources = load_json_compatible_yaml(METADATA_DIR / "sources.yml")
        expected_lunyu_segment_count = sum(
            len(read_jsonl(REPO_ROOT / source["processed_path"]))
            for source in sources
            if source["work_id"] == DEFAULT_WORK_ID and str(source["processed_path"]).endswith(".jsonl")
        )
        expected_lunyu_section_count = manifest["summary"]["section_count"]
        expected_exact_alignment_count = manifest["summary"]["exact_alignment_count"]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "corpus.sqlite3"
            qc_output = temp_path / "qc.json"
            corpus_tmx = temp_path / "lunyu__all__aligned_passages.tmx"
            tmx_validation_output = temp_path / "lunyu__corpus_tmx_validation.json"

            initialize_database(db_path)
            import_summary = import_corpus(db_path)
            corpus_rows = load_exact_alignment_rows(db_path, DEFAULT_WORK_ID)
            write_tmx(corpus_rows, corpus_tmx, work_id=DEFAULT_WORK_ID)
            tmx_validation_summary = validate_tmx_file(
                db_path,
                corpus_tmx,
                tmx_validation_output,
                work_id=DEFAULT_WORK_ID,
            )
            qc_summary = run_qc(db_path, qc_output, work_id=DEFAULT_WORK_ID)

            self.assertEqual(import_summary["work_count"], len(works))
            self.assertEqual(import_summary["section_count"], len(sections))
            self.assertEqual(import_summary["segments"], expected_lunyu_segment_count)
            self.assertEqual(import_summary["alignments"], expected_exact_alignment_count + expected_lunyu_section_count)
            self.assertEqual(import_summary["work_summaries"][DEFAULT_WORK_ID]["section_count"], expected_lunyu_section_count)
            self.assertEqual(len(corpus_rows), expected_exact_alignment_count)
            self.assertEqual(tmx_validation_summary["status"], "pass")
            self.assertEqual(qc_summary["status"], "pass")
            self.assertEqual(len(qc_summary["sections"]), expected_lunyu_section_count)
            self.assertEqual(qc_summary["manifest_summary"]["complete_sections"], expected_lunyu_section_count)

            with closing(sqlite3.connect(db_path)) as connection:
                total_work_count = connection.execute("SELECT COUNT(*) FROM works").fetchone()[0]
                total_section_count = connection.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
                lunyu_section_count = connection.execute(
                    "SELECT COUNT(*) FROM sections WHERE work_id = ?",
                    (DEFAULT_WORK_ID,),
                ).fetchone()[0]
                lunyu_segment_count = connection.execute(
                    "SELECT COUNT(*) FROM segments WHERE work_id = ?",
                    (DEFAULT_WORK_ID,),
                ).fetchone()[0]
                exact_alignment_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM alignments
                    WHERE work_id = ? AND alignment_type = 'exact_or_near_exact'
                    """,
                    (DEFAULT_WORK_ID,),
                ).fetchone()[0]
                grouped_alignment_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM alignments
                    WHERE work_id = ? AND alignment_type = 'section_group'
                    """,
                    (DEFAULT_WORK_ID,),
                ).fetchone()[0]

            self.assertEqual(total_work_count, len(works))
            self.assertEqual(total_section_count, len(sections))
            self.assertEqual(lunyu_section_count, expected_lunyu_section_count)
            self.assertEqual(lunyu_segment_count, expected_lunyu_segment_count)
            self.assertEqual(exact_alignment_count, expected_exact_alignment_count)
            self.assertEqual(grouped_alignment_count, expected_lunyu_section_count)
            self.assertTrue(all(section["alignment_status"] == "complete" for section in manifest["sections"]))

            last_section_id = manifest["sections"][-1]["section_id"]
            last_rows = load_exact_alignment_rows(db_path, DEFAULT_WORK_ID, last_section_id)
            self.assertEqual(len(last_rows), manifest["sections"][-1]["expected_exact_alignment_count"])
            body = ET.parse(corpus_tmx).getroot().find("./body")
            self.assertIsNotNone(body)

    def test_source_ids_are_globally_unique(self) -> None:
        sources = load_json_compatible_yaml(METADATA_DIR / "sources.yml")
        source_ids = [source["source_id"] for source in sources]
        self.assertEqual(len(source_ids), len(set(source_ids)))
