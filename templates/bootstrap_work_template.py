from __future__ import annotations

import argparse
import json
from typing import Any

from common import MANIFESTS_DIR, REPO_ROOT, write_json

WORK_ID = "{work_id}"
MANIFEST_PATH = MANIFESTS_DIR / f"{WORK_ID}.yml"
INVENTORY_PATH = REPO_ROOT / "metadata" / f"{WORK_ID}_inventory.yml"


def build_ingestion_policy() -> dict[str, Any]:
    return {
        "inventory_required": True,
        "inventory_path": f"metadata/{WORK_ID}_inventory.yml",
        "inventory_unit_key": "units",
        "ingestion_plan_required": True,
        "ingestion_plan_path": f"documentation/{WORK_ID}_ingestion_plan.md",
        "source_audit_required": True,
        "source_audit_path": f"documentation/{WORK_ID}_ingestion_plan.md",
        "granularity_policy_required": True,
        "granularity_policy_path": "documentation/alignment_granularity_policy.md",
        "section_unit": "",
        "preferred_segment_unit": "",
        "minimum_required_alignment_scope": "",
        "maximum_exact_alignment_scope": "",
        "allowed_segment_units": [],
        "coarse_alignment_units": [],
        "granularity_order": [],
        "metadata_only_allowed": True,
        "missing_text_policy": "retain_metadata_only_sections_until_clean_public_domain_witnesses_exist",
        "commentary_policy": "exclude_commentary_and_notes_from_exact_alignments_and_tmx",
        "rights_policy": "public_domain_only_for_export",
        "allowed_export_rights_statuses": ["public_domain"],
        "section_group_export_policy": "forbidden",
        "completion_definition": ""
    }


def bootstrap_corpus(skip_fetch: bool = False) -> dict[str, Any]:
    del skip_fetch
    manifest = {
        "work_id": WORK_ID,
        "work_status": "proposal",
        "source_pair_defaults": {
            "source_id": "",
            "target_source_id": "",
            "source_language": "zh-Hant",
            "target_language": "en",
        },
        "summary": {
            "section_count": 0,
            "complete_sections": 0,
            "metadata_only_sections": 0,
            "sections_needing_alignment": 0,
            "sections_needing_qc": 0,
            "exact_alignment_count": 0,
        },
        "ingestion_policy": build_ingestion_policy(),
        "sections": [],
    }
    inventory = {
        "work_id": WORK_ID,
        "title": f"Canonical {WORK_ID} inventory",
        "count_basis": {"canonical_unit_count": 0, "basis_note": ""},
        "units": [],
    }
    write_json(MANIFEST_PATH, manifest)
    write_json(INVENTORY_PATH, inventory)
    return manifest["summary"]


def main() -> None:
    parser = argparse.ArgumentParser(description=f"Bootstrap metadata for {WORK_ID}.")
    parser.add_argument("--skip-fetch", action="store_true", help="Placeholder option for future fetch control.")
    args = parser.parse_args()
    summary = bootstrap_corpus(skip_fetch=args.skip_fetch)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
