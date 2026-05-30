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
from audit_shijing_completion_quality import audit_shijing_completion_quality
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
            shijing_quality_output = temp_path / "shijing__completion_quality.json"
            shijing_quality_markdown = temp_path / "shijing__completion_quality.md"
            shijing_spotcheck_packet = temp_path / "shijing__spotcheck_packet.md"

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
            shijing_quality_summary = audit_shijing_completion_quality(
                json_output_path=shijing_quality_output,
                markdown_output_path=shijing_quality_markdown,
                spotcheck_output_path=shijing_spotcheck_packet,
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
            self.assertEqual(shijing_quality_summary["hard_failure_count"], 0)
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
                len([section for section in manifests["shijing"]["sections"] if section["tmx_status"] != "complete"]),
                manifests["shijing"]["summary"]["metadata_only_sections"],
            )
            self.assertEqual(expected_exact_alignment_counts[DEFAULT_WORK_ID], 501)
            self.assertEqual(expected_exact_alignment_counts["mengzi"], 260)
            self.assertEqual(expected_section_counts["shijing"], 311)
            self.assertEqual(manifests["shijing"]["summary"]["extant_poem_count"], 305)
            self.assertGreaterEqual(expected_complete_section_counts["shijing"], 123)
            self.assertGreaterEqual(expected_exact_alignment_counts["shijing"], 270)
            self.assertEqual(
                manifests["shijing"]["summary"]["metadata_only_sections"] + expected_complete_section_counts["shijing"],
                expected_section_counts["shijing"],
            )
            self.assertTrue(shijing_quality_output.exists())
            self.assertTrue(shijing_quality_markdown.exists())
            self.assertTrue(shijing_spotcheck_packet.exists())
            self.assertEqual(len(shijing_inventory["poems"]), expected_section_counts["shijing"])
            self.assertEqual({section["section_id"] for section in manifests["shijing"]["sections"]}, shijing_inventory_sections)
            self.assertEqual(shijing_coverage_summary["manifest_section_count"], expected_section_counts["shijing"])
            self.assertEqual(
                shijing_coverage_summary["units_with_at_least_one_exact_alignment"],
                expected_complete_section_counts["shijing"],
            )
            self.assertEqual(shijing_quality_summary["summary"]["complete_sections"], expected_complete_section_counts["shijing"])
            self.assertGreater(
                shijing_quality_summary["summary"]["ocr_or_fulltext_derived_sections"],
                0,
            )
            self.assertEqual(
                shijing_quality_summary["summary"]["metadata_only_sections"],
                manifests["shijing"]["summary"]["metadata_only_sections"],
            )
            self.assertGreater(
                shijing_coverage_summary["complete_sections_by_witness_type"]["OCR-derived witness"],
                0,
            )
            self.assertLess(
                shijing_coverage_summary["units_with_verified_public_domain_english_source"],
                shijing_coverage_summary["units_with_english_public_domain_witness"],
            )
            self.assertTrue(
                all(
                    section["verification_status"] in {"human_verified_ocr", "human_verified_fulltext"}
                    for section in shijing_quality_summary["sections"]
                    if section["english_witness_type"] == "fulltext_ocr_derived_witness"
                )
            )
            self.assertTrue(any(section["verification_status"] == "human_verified_ocr" for section in shijing_quality_summary["sections"]))
            self.assertTrue(all(not section["needs_human_text_review"] for section in shijing_quality_summary["sections"]))
            self.assertTrue(
                all(section["verification_decision"] == "export" for section in shijing_quality_summary["sections"])
            )
            self.assertGreaterEqual(
                sum(1 for row in shijing_rows if row["is_coarse_alignment"]),
                1,
            )
            self.assertNotIn("section_group", shijing_tmx.read_text(encoding="utf-8"))
            exported_shijing_sections = {row["section_id"] for row in shijing_rows}
            self.assertTrue(
                all(
                    source["rights_status"] == "public_domain"
                    for source in sources
                    if source["work_id"] == "shijing" and source.get("section_id") in exported_shijing_sections
                )
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

    def test_shijing_quality_reports_are_present(self) -> None:
        quality_report = load_json_compatible_yaml(REPO_ROOT / "logs" / "qc_reports" / "shijing__completion_quality.json")
        spotcheck_packet = REPO_ROOT / "documentation" / "shijing_spotcheck_packet.md"
        manifest = load_work_manifest("shijing")
        verification_ledger = load_json_compatible_yaml(REPO_ROOT / "metadata" / "shijing_verification_ledger.yml")
        hard_word_minimum = quality_report["thresholds"]["hard_english_word_minimum"]
        hard_ratio_maximum = quality_report["thresholds"]["hard_english_to_chinese_ratio_high_threshold"]
        self.assertEqual(quality_report["work_id"], "shijing")
        self.assertEqual(manifest["summary"]["section_count"], 311)
        self.assertEqual(manifest["summary"]["extant_poem_count"], 305)
        self.assertEqual(quality_report["summary"]["complete_sections"], manifest["summary"]["complete_sections"])
        self.assertEqual(quality_report["summary"]["metadata_only_sections"], manifest["summary"]["metadata_only_sections"])
        self.assertEqual(quality_report["summary"]["exact_alignment_count"], manifest["summary"]["exact_alignment_count"])
        self.assertGreaterEqual(quality_report["summary"]["complete_sections"], 163)
        self.assertGreaterEqual(quality_report["summary"]["exact_alignment_count"], 392)
        self.assertGreaterEqual(quality_report["progress"]["all_human_verified_ocr_sections"], 60)
        self.assertEqual(quality_report["hard_failure_count"], 0)
        self.assertEqual(quality_report["summary"]["sections_needing_human_text_review"], 0)
        self.assertEqual(quality_report["summary"]["sections_with_possible_commentary_leakage"], 0)
        self.assertEqual(quality_report["summary"]["sections_with_extreme_length_ratio"], 0)
        self.assertTrue(spotcheck_packet.exists())
        self.assertEqual(len(verification_ledger["entries"]), manifest["summary"]["section_count"])
        self.assertEqual(quality_report["progress"]["total_extant_poems"], 305)
        self.assertEqual(
            quality_report["progress"]["verified_exportable_poems"],
            quality_report["summary"]["complete_sections"],
        )
        self.assertEqual(
            quality_report["progress"]["non_exportable_repair_queue_remaining"],
            quality_report["summary"]["non_exportable_extant_sections"],
        )
        self.assertEqual(
            quality_report["progress"]["all_human_verified_ocr_sections"],
            sum(1 for section in quality_report["sections"] if section["verification_status"] == "human_verified_ocr"),
        )
        self.assertEqual(
            quality_report["progress"]["newly_repaired_in_latest_tranche"],
            len(quality_report["progress"]["latest_repaired_sections"]),
        )
        self.assertIsNotNone(quality_report["progress"]["latest_repair_batch"])
        self.assertTrue(
            all(
                section["repair_batch"] == quality_report["progress"]["latest_repair_batch"]
                for section in quality_report["progress"]["latest_repaired_sections"]
            )
        )
        self.assertIn(
            quality_report["progress"]["latest_repair_batch"],
            {batch["repair_batch"] for batch in quality_report["progress"]["human_verified_batches"]},
        )
        priority_remaining = quality_report["progress"]["remaining_priority_subdivisions"]
        for subdivision_key in (
            "國風 / 召南",
            "國風 / 邶風",
            "國風 / 鄘風",
            "國風 / 衛風",
            "國風 / 王風",
            "國風 / 鄭風",
            "國風 / 齊風",
            "國風 / 魏風",
            "國風 / 唐風",
        ):
            self.assertIn(subdivision_key, priority_remaining)
            self.assertTrue(
                all(section["review_note"] for section in priority_remaining[subdivision_key])
            )
        skipped_current_witness_sections = quality_report["progress"]["skipped_current_witness_sections"]
        self.assertTrue(skipped_current_witness_sections)
        self.assertTrue(
            all(section["review_note"] for section in skipped_current_witness_sections)
        )
        self.assertTrue(
            all(
                section["review_note"] != "Public-domain witness located, but the English text is not yet verified clean enough for export."
                for section in skipped_current_witness_sections
            )
        )
        skipped_section_ids = {section["section_id"] for section in skipped_current_witness_sections}
        self.assertTrue({"guofeng-weifeng-006", "guofeng-wangfeng-005", "guofeng-wangfeng-010"} <= skipped_section_ids)
        self.assertTrue(
            {
                "guofeng-zhengfeng-001",
                "guofeng-qifeng-002",
                "guofeng-weifeng-state-002",
                "guofeng-tangfeng-002",
            }
            <= skipped_section_ids
        )
        self.assertFalse(any(section["english_word_count"] == 0 for section in quality_report["sections"]))
        self.assertFalse(
            any(
                section["english_word_count"] < hard_word_minimum
                for section in quality_report["sections"]
            )
        )
        self.assertFalse(
            any(
                section["english_to_chinese_length_ratio"] > hard_ratio_maximum
                for section in quality_report["sections"]
            )
        )
        self.assertFalse(
            any(
                (
                    section["contains_chinese_in_english_segment"]
                    or section["contains_untranslated_chinese_title"]
                )
                for section in quality_report["sections"]
            )
        )
        self.assertFalse(any(section["needs_human_text_review"] for section in quality_report["sections"]))
        self.assertFalse(
            any(
                section["english_witness_status"] in {"ocr_extracted_needs_review", "fulltext_extracted_needs_review"}
                for section in quality_report["sections"]
            )
        )
        self.assertFalse(any(section["suspiciously_extreme_length_ratio"] for section in quality_report["sections"]))
        self.assertFalse(any(section["possible_commentary_leakage_markers"] for section in quality_report["sections"]))
        ledger_by_section = {entry["section_id"]: entry for entry in verification_ledger["entries"]}
        self.assertTrue(all(section["section_id"] in ledger_by_section for section in quality_report["sections"]))
        self.assertTrue(
            all(ledger_by_section[section["section_id"]]["decision"] == "export" for section in quality_report["sections"])
        )
        self.assertTrue(
            all(
                ledger_by_section[section["section_id"]]["verification_status"]
                in {"verified_transcribed_text", "human_verified_ocr", "human_verified_fulltext"}
                for section in quality_report["sections"]
            )
        )

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

        shijing_manifest = load_work_manifest("shijing")
        verification_ledger = load_json_compatible_yaml(REPO_ROOT / "metadata" / "shijing_verification_ledger.yml")
        shijing_export_rows = read_jsonl(corpus_export_paths("shijing")["jsonl"])
        self.assertTrue(
            any(section["english_witness_status"] == "extraction_failed_metadata_only" for section in shijing_manifest["sections"])
        )
        exported_sections = {section["section_id"] for section in shijing_manifest["sections"] if section["tmx_status"] == "complete"}
        ledger_by_section = {entry["section_id"]: entry for entry in verification_ledger["entries"]}
        shijing_sections_by_id = {section["section_id"]: section for section in shijing_manifest["sections"]}
        self.assertTrue(all(section_id in ledger_by_section for section_id in exported_sections))
        self.assertTrue(all(ledger_by_section[section_id]["decision"] == "export" for section_id in exported_sections))
        reviewed_ocr_rows = [
            row
            for row in shijing_export_rows
            if shijing_sections_by_id[row["section_id"]].get("english_witness") == "legge_ocr_reviewed"
        ]
        self.assertTrue(reviewed_ocr_rows)
        self.assertTrue(
            all(
                not any(character.isascii() and character.isalpha() for character in row["translation_ref"])
                for row in reviewed_ocr_rows
            )
        )
