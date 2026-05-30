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

from common import (
    DEFAULT_WORK_ID,
    METADATA_DIR,
    corpus_export_paths,
    load_work_manifest,
    load_json_compatible_yaml,
    read_jsonl,
)
from audit_work_coverage import audit_work_coverage
from export_corpus import load_exact_alignment_rows, write_tmx
from import_corpus import import_corpus
from init_db import initialize_database
from qc_corpus import run_qc
from validate_alignment_granularity import validate_work_alignment_granularity
from validate_ingestion_policy import validate_ingestion_policy
from validate_tmx import validate_tmx_file


class CorpusWorkflowTest(unittest.TestCase):
    def test_lunyu_workflow_counts_and_qc(self) -> None:
        works = load_json_compatible_yaml(METADATA_DIR / "works.yml")
        work_ids = [work["work_id"] for work in works]
        manifests = {work_id: load_work_manifest(work_id) for work_id in work_ids}
        sections = load_json_compatible_yaml(METADATA_DIR / "sections.yml")
        sources = load_json_compatible_yaml(METADATA_DIR / "sources.yml")
        expected_segment_counts = {
            work_id: sum(
                len(read_jsonl(REPO_ROOT / source["processed_path"]))
                for source in sources
                if source["work_id"] == work_id and str(source["processed_path"]).endswith(".jsonl")
            )
            for work_id in manifests
        }
        expected_section_counts = {
            work_id: manifests[work_id]["summary"]["section_count"] for work_id in manifests
        }
        expected_complete_section_counts = {
            work_id: manifests[work_id]["summary"]["complete_sections"] for work_id in manifests
        }
        expected_exact_alignment_counts = {
            work_id: manifests[work_id]["summary"]["exact_alignment_count"] for work_id in manifests
        }
        expected_total_segments = sum(expected_segment_counts.values())
        expected_total_alignments = sum(
            expected_exact_alignment_counts[work_id] + expected_complete_section_counts[work_id]
            for work_id in manifests
        )
        shijing_inventory = load_json_compatible_yaml(METADATA_DIR / "shijing_poem_inventory.yml")
        shijing_inventory_sections = {item["section_id"] for item in shijing_inventory["poems"]}

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            db_path = temp_path / "corpus.sqlite3"
            corpus_tmx = temp_path / "lunyu__all__aligned_passages.tmx"
            mengzi_tmx = temp_path / "mengzi__all__aligned_passages.tmx"
            shijing_tmx = temp_path / "shijing__all__aligned_passages.tmx"
            tmx_validation_output = temp_path / "lunyu__corpus_tmx_validation.json"
            mengzi_tmx_validation_output = temp_path / "mengzi__corpus_tmx_validation.json"
            shijing_tmx_validation_output = temp_path / "shijing__corpus_tmx_validation.json"
            qc_output = temp_path / "lunyu__qc.json"
            mengzi_qc_output = temp_path / "mengzi__qc.json"
            shijing_qc_output = temp_path / "shijing__qc.json"
            shijing_coverage_output = temp_path / "shijing__coverage_audit.json"
            shijing_coverage_markdown = temp_path / "shijing__coverage_audit.md"
            shijing_granularity_output = temp_path / "shijing__granularity_qc.json"

            initialize_database(db_path)
            import_summary = import_corpus(db_path)
            corpus_rows = load_exact_alignment_rows(db_path, DEFAULT_WORK_ID)
            mengzi_rows = load_exact_alignment_rows(db_path, "mengzi")
            shijing_rows = load_exact_alignment_rows(db_path, "shijing")
            write_tmx(corpus_rows, corpus_tmx, work_id=DEFAULT_WORK_ID)
            write_tmx(mengzi_rows, mengzi_tmx, work_id="mengzi")
            write_tmx(shijing_rows, shijing_tmx, work_id="shijing")
            tmx_validation_summary = validate_tmx_file(
                db_path,
                corpus_tmx,
                tmx_validation_output,
                work_id=DEFAULT_WORK_ID,
            )
            mengzi_tmx_validation_summary = validate_tmx_file(
                db_path,
                mengzi_tmx,
                mengzi_tmx_validation_output,
                work_id="mengzi",
            )
            shijing_tmx_validation_summary = validate_tmx_file(
                db_path,
                shijing_tmx,
                shijing_tmx_validation_output,
                work_id="shijing",
            )
            qc_summary = run_qc(db_path, qc_output, work_id=DEFAULT_WORK_ID)
            mengzi_qc_summary = run_qc(db_path, mengzi_qc_output, work_id="mengzi")
            shijing_qc_summary = run_qc(db_path, shijing_qc_output, work_id="shijing")
            policy_reports = {work_id: validate_ingestion_policy(work_id) for work_id in work_ids}
            shijing_coverage_summary = audit_work_coverage(
                "shijing",
                json_output_path=shijing_coverage_output,
                markdown_output_path=shijing_coverage_markdown,
            )
            shijing_granularity_summary = validate_work_alignment_granularity(
                "shijing",
                output_path=shijing_granularity_output,
            )

            self.assertEqual(import_summary["work_count"], len(works))
            self.assertEqual(import_summary["section_count"], len(sections))
            self.assertEqual(import_summary["segments"], expected_total_segments)
            self.assertEqual(import_summary["alignments"], expected_total_alignments)
            for work_id in work_ids:
                self.assertEqual(
                    import_summary["work_summaries"][work_id]["section_count"],
                    expected_section_counts[work_id],
                )
            self.assertEqual(len(corpus_rows), expected_exact_alignment_counts[DEFAULT_WORK_ID])
            self.assertEqual(len(mengzi_rows), expected_exact_alignment_counts["mengzi"])
            self.assertEqual(len(shijing_rows), expected_exact_alignment_counts["shijing"])
            self.assertEqual(tmx_validation_summary["status"], "pass")
            self.assertEqual(mengzi_tmx_validation_summary["status"], "pass")
            self.assertEqual(shijing_tmx_validation_summary["status"], "pass")
            self.assertEqual(qc_summary["status"], "pass")
            self.assertEqual(mengzi_qc_summary["status"], "pass")
            self.assertEqual(shijing_qc_summary["status"], "pass")
            self.assertTrue(all(report["error_count"] == 0 for report in policy_reports.values()))
            self.assertEqual(shijing_granularity_summary["error_count"], 0)
            self.assertEqual(len(qc_summary["sections"]), expected_section_counts[DEFAULT_WORK_ID])
            self.assertEqual(len(mengzi_qc_summary["sections"]), expected_section_counts["mengzi"])
            self.assertEqual(len(shijing_qc_summary["sections"]), expected_section_counts["shijing"])
            self.assertEqual(qc_summary["manifest_summary"]["complete_sections"], expected_section_counts[DEFAULT_WORK_ID])
            self.assertEqual(mengzi_qc_summary["manifest_summary"]["complete_sections"], expected_section_counts["mengzi"])
            self.assertEqual(
                shijing_qc_summary["manifest_summary"]["complete_sections"],
                expected_complete_section_counts["shijing"],
            )

            with closing(sqlite3.connect(db_path)) as connection:
                total_work_count = connection.execute("SELECT COUNT(*) FROM works").fetchone()[0]
                total_section_count = connection.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
                lunyu_section_count = connection.execute(
                    "SELECT COUNT(*) FROM sections WHERE work_id = ?",
                    (DEFAULT_WORK_ID,),
                ).fetchone()[0]
                mengzi_section_count = connection.execute(
                    "SELECT COUNT(*) FROM sections WHERE work_id = ?",
                    ("mengzi",),
                ).fetchone()[0]
                shijing_section_count = connection.execute(
                    "SELECT COUNT(*) FROM sections WHERE work_id = ?",
                    ("shijing",),
                ).fetchone()[0]
                lunyu_segment_count = connection.execute(
                    "SELECT COUNT(*) FROM segments WHERE work_id = ?",
                    (DEFAULT_WORK_ID,),
                ).fetchone()[0]
                mengzi_segment_count = connection.execute(
                    "SELECT COUNT(*) FROM segments WHERE work_id = ?",
                    ("mengzi",),
                ).fetchone()[0]
                shijing_segment_count = connection.execute(
                    "SELECT COUNT(*) FROM segments WHERE work_id = ?",
                    ("shijing",),
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
                mengzi_exact_alignment_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM alignments
                    WHERE work_id = ? AND alignment_type = 'exact_or_near_exact'
                    """,
                    ("mengzi",),
                ).fetchone()[0]
                mengzi_grouped_alignment_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM alignments
                    WHERE work_id = ? AND alignment_type = 'section_group'
                    """,
                    ("mengzi",),
                ).fetchone()[0]
                shijing_exact_alignment_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM alignments
                    WHERE work_id = ? AND alignment_type = 'exact_or_near_exact'
                    """,
                    ("shijing",),
                ).fetchone()[0]
                shijing_grouped_alignment_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM alignments
                    WHERE work_id = ? AND alignment_type = 'section_group'
                    """,
                    ("shijing",),
                ).fetchone()[0]
                book_01_work_count = connection.execute(
                    "SELECT COUNT(DISTINCT work_id) FROM sections WHERE section_id LIKE 'book-01-%'"
                ).fetchone()[0]

            self.assertEqual(total_work_count, len(works))
            self.assertEqual(total_section_count, len(sections))
            self.assertEqual(lunyu_section_count, expected_section_counts[DEFAULT_WORK_ID])
            self.assertEqual(mengzi_section_count, expected_section_counts["mengzi"])
            self.assertEqual(shijing_section_count, expected_section_counts["shijing"])
            self.assertEqual(lunyu_segment_count, expected_segment_counts[DEFAULT_WORK_ID])
            self.assertEqual(mengzi_segment_count, expected_segment_counts["mengzi"])
            self.assertEqual(shijing_segment_count, expected_segment_counts["shijing"])
            self.assertEqual(exact_alignment_count, expected_exact_alignment_counts[DEFAULT_WORK_ID])
            self.assertEqual(grouped_alignment_count, expected_section_counts[DEFAULT_WORK_ID])
            self.assertEqual(mengzi_exact_alignment_count, expected_exact_alignment_counts["mengzi"])
            self.assertEqual(mengzi_grouped_alignment_count, expected_section_counts["mengzi"])
            self.assertEqual(shijing_exact_alignment_count, expected_exact_alignment_counts["shijing"])
            self.assertEqual(shijing_grouped_alignment_count, expected_complete_section_counts["shijing"])
            self.assertEqual(book_01_work_count, 2)
            self.assertTrue(
                all(section["alignment_status"] == "complete" for section in manifests[DEFAULT_WORK_ID]["sections"])
            )
            self.assertTrue(all(section["alignment_status"] == "complete" for section in manifests["mengzi"]["sections"]))
            self.assertEqual(
                len([section for section in manifests["shijing"]["sections"] if section["status"] == "complete"]),
                expected_complete_section_counts["shijing"],
            )
            self.assertEqual(
                len([section for section in manifests["shijing"]["sections"] if section["alignment_status"] == "metadata_only"]),
                manifests["shijing"]["summary"]["metadata_only_sections"],
            )
            self.assertEqual(expected_exact_alignment_counts[DEFAULT_WORK_ID], 501)
            self.assertEqual(expected_exact_alignment_counts["mengzi"], 260)
            self.assertEqual(expected_section_counts["shijing"], 311)
            self.assertEqual(expected_complete_section_counts["shijing"], 305)
            self.assertEqual(expected_exact_alignment_counts["shijing"], 452)
            self.assertEqual(
                manifests["shijing"]["summary"]["metadata_only_sections"] + expected_complete_section_counts["shijing"],
                expected_section_counts["shijing"],
            )
            self.assertEqual(len(shijing_inventory["poems"]), expected_section_counts["shijing"])
            self.assertEqual({section["section_id"] for section in manifests["shijing"]["sections"]}, shijing_inventory_sections)
            self.assertEqual(shijing_coverage_summary["manifest_section_count"], expected_section_counts["shijing"])
            self.assertEqual(
                shijing_coverage_summary["units_with_at_least_one_exact_alignment"],
                expected_complete_section_counts["shijing"],
            )
            self.assertGreaterEqual(
                sum(1 for row in shijing_rows if row["is_coarse_alignment"]),
                1,
            )

            last_section_id = manifests[DEFAULT_WORK_ID]["sections"][-1]["section_id"]
            last_rows = load_exact_alignment_rows(db_path, DEFAULT_WORK_ID, last_section_id)
            self.assertEqual(
                len(last_rows),
                manifests[DEFAULT_WORK_ID]["sections"][-1]["expected_exact_alignment_count"],
            )
            first_mengzi_section_id = manifests["mengzi"]["sections"][0]["section_id"]
            first_mengzi_rows = load_exact_alignment_rows(db_path, "mengzi", first_mengzi_section_id)
            self.assertEqual(
                len(first_mengzi_rows),
                manifests["mengzi"]["sections"][0]["expected_exact_alignment_count"],
            )
            first_shijing_section_id = manifests["shijing"]["sections"][0]["section_id"]
            first_shijing_rows = load_exact_alignment_rows(db_path, "shijing", first_shijing_section_id)
            self.assertEqual(
                len(first_shijing_rows),
                manifests["shijing"]["sections"][0]["expected_exact_alignment_count"],
            )
            for row in shijing_rows:
                if row["alignment_granularity"] == "poem" and ("\n\n" in row["chinese_text"] or "\n\n" in row["translation_text"]):
                    self.assertTrue(row["is_coarse_alignment"])
            body = ET.parse(corpus_tmx).getroot().find("./body")
            mengzi_body = ET.parse(mengzi_tmx).getroot().find("./body")
            shijing_body = ET.parse(shijing_tmx).getroot().find("./body")
            self.assertIsNotNone(body)
            self.assertIsNotNone(mengzi_body)
            self.assertIsNotNone(shijing_body)

    def test_source_ids_are_globally_unique(self) -> None:
        sources = load_json_compatible_yaml(METADATA_DIR / "sources.yml")
        source_ids = [source["source_id"] for source in sources]
        self.assertEqual(len(source_ids), len(set(source_ids)))

    def test_manifest_policy_and_exports_are_consistent(self) -> None:
        works = load_json_compatible_yaml(METADATA_DIR / "works.yml")
        for work in works:
            work_id = work["work_id"]
            manifest = load_work_manifest(work_id)
            policy = manifest["ingestion_policy"]
            self.assertTrue(policy["inventory_required"])
            self.assertTrue((REPO_ROOT / policy["inventory_path"]).exists())
            self.assertTrue((REPO_ROOT / policy["ingestion_plan_path"]).exists())
            self.assertTrue((REPO_ROOT / policy["granularity_policy_path"]).exists())
            self.assertEqual(validate_ingestion_policy(work_id)["error_count"], 0)

            export_rows = read_jsonl(corpus_export_paths(work_id)["jsonl"])
            exported_section_ids = {row["section_id"] for row in export_rows}
            metadata_only_sections = {
                section["section_id"] for section in manifest["sections"] if section["tmx_status"] != "complete"
            }
            self.assertFalse(exported_section_ids & metadata_only_sections)
            self.assertTrue(all(row["alignment_granularity"] in policy["allowed_segment_units"] for row in export_rows))
