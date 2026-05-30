from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import DEFAULT_WORK_ID, load_corpus_manifest
from export_corpus import load_exact_alignment_rows, write_tmx
from import_corpus import import_corpus
from init_db import initialize_database
from validate_tmx import validate_tmx_file

XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"


class TmxExportTest(unittest.TestCase):
    def test_tmx_export_matches_manifest_counts(self) -> None:
        manifest = load_corpus_manifest()
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "corpus.sqlite3"
            corpus_tmx = temp_path / "lunyu__all__aligned_passages.tmx"
            report_output = temp_path / "tmx-validation.json"

            initialize_database(db_path)
            import_corpus(db_path)
            export_rows = load_exact_alignment_rows(db_path, DEFAULT_WORK_ID)
            write_tmx(export_rows, corpus_tmx, work_id=DEFAULT_WORK_ID)
            validation_summary = validate_tmx_file(db_path, corpus_tmx, report_output, work_id=DEFAULT_WORK_ID)

            tree = ET.parse(corpus_tmx)
            tus = tree.getroot().findall("./body/tu")

            self.assertEqual(len(export_rows), manifest["summary"]["exact_alignment_count"])
            self.assertEqual(validation_summary["status"], "pass")
            self.assertEqual(validation_summary["tu_count"], manifest["summary"]["exact_alignment_count"])
            self.assertEqual(len(tus), manifest["summary"]["exact_alignment_count"])
            self.assertGreater(len(tus), 0)
            first_tuvs = tus[0].findall("tuv")
            self.assertEqual(first_tuvs[0].attrib[f"{{{XML_NAMESPACE}}}lang"], "zh-Hant")
            self.assertEqual(first_tuvs[1].attrib[f"{{{XML_NAMESPACE}}}lang"], "en")

    def test_tmx_validation_fails_after_tampering(self) -> None:
        manifest = load_corpus_manifest()
        first_section_id = manifest["sections"][0]["section_id"]
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "corpus.sqlite3"
            tampered_tmx = temp_path / "tampered-section.tmx"

            initialize_database(db_path)
            import_corpus(db_path)
            export_rows = load_exact_alignment_rows(db_path, DEFAULT_WORK_ID, first_section_id)
            write_tmx(export_rows, tampered_tmx, work_id=DEFAULT_WORK_ID)

            tree = ET.parse(tampered_tmx)
            first_target_seg = tree.getroot().find("./body/tu/tuv[@xml:lang='en']/seg", {"xml": XML_NAMESPACE})
            assert first_target_seg is not None
            first_target_seg.text = "tampered translation memory row"
            tree.write(tampered_tmx, encoding="utf-8", xml_declaration=True)

            with self.assertRaises(ValueError):
                validate_tmx_file(
                    db_path,
                    tampered_tmx,
                    temp_path / "tmx-validation.json",
                    first_section_id,
                    work_id=DEFAULT_WORK_ID,
                )
