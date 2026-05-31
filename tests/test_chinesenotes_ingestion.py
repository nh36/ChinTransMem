from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import load_json_compatible_yaml, read_jsonl
from ingest_chinesenotes_work import stage_chinesenotes_work


class ChineseNotesIngestionTest(unittest.TestCase):
    def test_stage_chinesenotes_work_builds_staging_outputs_and_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source_root = temp_path / "chinesenotes"
            (source_root / "data" / "corpus").mkdir(parents=True)
            (source_root / "corpus" / "daodejing").mkdir(parents=True)

            (source_root / "data" / "corpus" / "collections.csv").write_text(
                "\n".join(
                    [
                        "# Collection File, HTML Gloss File, Title, Description, Introduction File, Corpus, Language, Format, Period",
                        "daodejing.csv\tdaodejing.html\tDaode Jing 《道德經》\tPilot source\tdaodejing/daodejing000.txt\tLiterary Chinese\tMixed\tPre-Han\tPhilosophy",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (source_root / "data" / "corpus" / "daodejing.csv").write_text(
                "\n".join(
                    [
                        "# Source file, Gloss output file, title",
                        "daodejing/daodejing001.txt\tdaodejing/daodejing001.html\tDaode Jing 《道德經》",
                        "daodejing/daodejing002.txt\tdaodejing/daodejing002.html\tSupplemental source",
                        "daodejing/missing.txt\tdaodejing/missing.html\tMissing source",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (source_root / "corpus" / "daodejing" / "daodejing000.txt").write_text(
                "English translation: James Legge\n",
                encoding="utf-8",
            )
            (source_root / "corpus" / "daodejing" / "daodejing001.txt").write_text(
                "\n".join(
                    [
                        "一章",
                        "道可道、非常道。",
                        "〈王弼注〉",
                        "(The Dao)",
                        "The Dao that can be trodden is not the enduring Dao.",
                        "二章",
                        "天下皆知美之為美。",
                        "〈王弼注〉",
                        "三章",
                        "(Loose title)",
                        "Only English survives in this test fixture.",
                        "本作品在全世界都属于公有领域。",
                        "English translation: James Legge",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (source_root / "corpus" / "daodejing" / "daodejing002.txt").write_text(
                "\n".join(
                    [
                        "四章",
                        "上善若水。",
                        "(The highest excellence)",
                        "The highest excellence is like water.",
                        "MIXED boundary marker 甲乙",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            output_root = temp_path / "staging"
            report_root = temp_path / "reports"
            works_before = (REPO_ROOT / "metadata" / "works.yml").read_text(encoding="utf-8")
            report = stage_chinesenotes_work(
                source_root=source_root,
                work_id="laozi",
                mode="staging",
                output_root=output_root,
                report_root=report_root,
            )
            works_after = (REPO_ROOT / "metadata" / "works.yml").read_text(encoding="utf-8")

            sections = read_jsonl(output_root / "laozi" / "sections.jsonl")
            section_by_status = {section["status"]: section for section in sections}
            source_pointers = read_jsonl(output_root / "laozi" / "source_pointers.jsonl")
            alignments = read_jsonl(output_root / "laozi" / "alignments.jsonl")
            manifest = load_json_compatible_yaml(output_root / "laozi" / "staging_manifest.yml")
            qc_report = load_json_compatible_yaml(report_root / "chinesenotes__laozi__staging_report.json")

        self.assertEqual(report["summary"]["total_metadata_rows"], 3)
        self.assertEqual(report["summary"]["source_files_found"], 2)
        self.assertEqual(report["summary"]["source_files_missing"], 1)
        self.assertEqual(report["summary"]["sections_with_chinese"], 3)
        self.assertEqual(report["summary"]["sections_with_english"], 3)
        self.assertEqual(report["summary"]["sections_that_could_become_tm_exports_now"], 1)
        self.assertEqual(report["summary"]["sections_requiring_manual_boundary_review"], 1)
        self.assertEqual(report["status_counts"]["missing_source_file"], 1)
        self.assertIn("exportable_candidate", section_by_status)
        self.assertIn("chinese_only", section_by_status)
        self.assertIn("english_only", section_by_status)
        self.assertIn("needs_boundary_review", section_by_status)
        self.assertEqual(len(source_pointers), 3)
        self.assertEqual(len(alignments), 1)
        self.assertEqual(qc_report["summary"]["sections_that_could_become_tm_exports_now"], 1)
        self.assertEqual(manifest["summary"]["source_files_found"], 2)
        self.assertEqual(works_before, works_after)

    def test_committed_staging_outputs_exist_without_new_active_work(self) -> None:
        manifest = load_json_compatible_yaml(REPO_ROOT / "corpus" / "staging" / "chinesenotes" / "laozi" / "staging_manifest.yml")
        report = load_json_compatible_yaml(REPO_ROOT / "logs" / "qc_reports" / "chinesenotes__laozi__staging_report.json")
        work_ids = {work["work_id"] for work in load_json_compatible_yaml(REPO_ROOT / "metadata" / "works.yml")}

        self.assertEqual(manifest["work_id"], "laozi")
        self.assertEqual(report["work_id"], "laozi")
        self.assertNotIn("laozi", work_ids)
        self.assertEqual(report["summary"]["source_files_found"], 1)
        self.assertEqual(report["summary"]["sections_detected"], 81)
        self.assertEqual(report["summary"]["sections_with_chinese"], 81)
        self.assertEqual(report["summary"]["sections_with_english"], 81)
        self.assertEqual(report["summary"]["sections_that_could_become_tm_exports_now"], 81)
        self.assertEqual(report["summary"]["sections_requiring_manual_boundary_review"], 0)


if __name__ == "__main__":
    unittest.main()
