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

from export_pilot import export_pilot
from import_lunyu_legge_pilot import import_pilot
from init_db import initialize_database
from validate_tmx import validate_tmx_export

XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"


class TmxExportTest(unittest.TestCase):
    def test_tmx_export_matches_database_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "pilot.sqlite3"
            tmx_output = temp_path / "aligned.tmx"
            report_output = temp_path / "tmx-validation.json"

            initialize_database(db_path)
            import_pilot(db_path)
            export_summary = export_pilot(db_path, temp_path / "aligned.jsonl", temp_path / "aligned.csv", tmx_output)
            validation_summary = validate_tmx_export(db_path, tmx_output, report_output)

            tree = ET.parse(tmx_output)
            tus = tree.getroot().findall("./body/tu")
            first_tuvs = tus[0].findall("tuv")

            self.assertEqual(export_summary["rows_exported"], 16)
            self.assertEqual(validation_summary["status"], "pass")
            self.assertEqual(validation_summary["tu_count"], 16)
            self.assertEqual(len(tus), 16)
            self.assertEqual(tus[0].attrib["tuid"], "lunyu__book-01-xueer__001__zhwikisource-20260529__legge-cc-v1-1893")
            self.assertEqual(first_tuvs[0].attrib[f"{{{XML_NAMESPACE}}}lang"], "zh-Hant")
            self.assertEqual(first_tuvs[1].attrib[f"{{{XML_NAMESPACE}}}lang"], "en")
            self.assertEqual(first_tuvs[0].findtext("seg"), "子曰：學而時習之，不亦說乎？有朋自遠方來，不亦樂乎？人不知而不慍，不亦君子乎？")

    def test_tmx_validation_fails_after_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "pilot.sqlite3"
            tmx_output = temp_path / "aligned.tmx"

            initialize_database(db_path)
            import_pilot(db_path)
            export_pilot(db_path, temp_path / "aligned.jsonl", temp_path / "aligned.csv", tmx_output)

            tree = ET.parse(tmx_output)
            first_target_seg = tree.getroot().find("./body/tu/tuv[@xml:lang='en']/seg", {"xml": XML_NAMESPACE})
            assert first_target_seg is not None
            first_target_seg.text = "tampered translation memory row"
            tree.write(tmx_output, encoding="utf-8", xml_declaration=True)

            with self.assertRaises(ValueError):
                validate_tmx_export(db_path, tmx_output, temp_path / "tmx-validation.json")
