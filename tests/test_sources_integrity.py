from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Ensure scripts/ is on sys.path so tests can import project scripts as modules
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import METADATA_DIR, load_json_compatible_yaml, load_work_manifests


class SourcesIntegrityTest(unittest.TestCase):
    def test_every_work_has_at_least_one_source(self) -> None:
        works = load_json_compatible_yaml(METADATA_DIR / "works.yml")
        sources = load_json_compatible_yaml(METADATA_DIR / "sources.yml")
        sources_by_work = {}
        for s in sources:
            sources_by_work.setdefault(s.get("work_id"), []).append(s)
        for work in works:
            work_id = work.get("work_id")
            self.assertIn(
                work_id,
                sources_by_work,
                msg=f"Work {work_id} has no source records in metadata/sources.yml",
            )

    def test_manifest_section_source_ids_exist(self) -> None:
        manifests = load_work_manifests()
        sources = load_json_compatible_yaml(METADATA_DIR / "sources.yml")
        source_ids = {s["source_id"] for s in sources}
        for manifest in manifests:
            for section in manifest.get("sections", []):
                source_ids_block = section.get("source_ids") or {}
                for key in ("source_id", "target_source_id"):
                    sid = source_ids_block.get(key)
                    if sid:
                        self.assertIn(
                            sid,
                            source_ids,
                            msg=(
                                f"Section {section.get('section_id')} in manifest {manifest.get('work_id')} references missing source id: {sid}"
                            ),
                        )

    def test_sources_not_truncated(self) -> None:
        sources = load_json_compatible_yaml(METADATA_DIR / "sources.yml")
        # Guardrail: repository is expected to have a large number of committed sources
        # (several hundreds). Fail if sources.yml was accidentally truncated to a tiny file.
        self.assertGreater(
            len(sources),
            800,
            msg=f"Suspiciously small number of source records ({len(sources)}) in metadata/sources.yml",
        )


if __name__ == "__main__":
    unittest.main()
