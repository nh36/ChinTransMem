from __future__ import annotations

from pathlib import Path
from typing import Any

from common import REPO_ROOT, load_json_compatible_yaml

VERIFICATION_LEDGER_PATH = REPO_ROOT / "metadata" / "shijing_verification_ledger.yml"

ALLOWED_VERIFICATION_STATUSES = {
    "verified_transcribed_text",
    "human_verified_ocr",
    "human_verified_fulltext",
    "needs_text_repair",
    "extraction_failed_non_exportable",
    "title_only_lost_text",
}
ALLOWED_DECISIONS = {
    "export",
    "do_not_export_until_repaired",
    "metadata_only_lost_text",
}
VERIFIED_EXPORT_STATUSES = {
    "verified_transcribed_text",
    "human_verified_ocr",
    "human_verified_fulltext",
}
REQUIRED_LEDGER_FIELDS = (
    "section_id",
    "title",
    "canonical_ref",
    "chinese_source_status",
    "english_source_status",
    "english_witness_type",
    "source_volume",
    "source_page_or_anchor",
    "raw_source_path",
    "processed_translation_path",
    "verification_status",
    "reviewer_note",
    "extraction_method",
    "alignment_status",
    "alignment_granularity",
    "remaining_warnings",
    "decision",
)


def load_shijing_verification_ledger(path: Path = VERIFICATION_LEDGER_PATH) -> list[dict[str, Any]]:
    payload = load_json_compatible_yaml(path)
    entries = payload.get("entries", []) if isinstance(payload, dict) else payload
    if not isinstance(entries, list):
        raise ValueError("Shijing verification ledger must contain an 'entries' list.")
    return [dict(entry) for entry in entries]


def build_verification_index(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for entry in entries:
        section_id = str(entry.get("section_id", "")).strip()
        if not section_id:
            raise ValueError("Verification ledger entry is missing section_id.")
        if section_id in index:
            raise ValueError(f"Duplicate Shijing verification ledger entry for {section_id}.")
        missing = [field for field in REQUIRED_LEDGER_FIELDS if field not in entry]
        if missing:
            raise ValueError(f"Verification ledger entry {section_id} is missing fields: {', '.join(missing)}")
        verification_status = str(entry["verification_status"])
        if verification_status not in ALLOWED_VERIFICATION_STATUSES:
            raise ValueError(f"{section_id}: invalid verification_status {verification_status!r}")
        decision = str(entry["decision"])
        if decision not in ALLOWED_DECISIONS:
            raise ValueError(f"{section_id}: invalid decision {decision!r}")
        remaining_warnings = entry.get("remaining_warnings")
        if not isinstance(remaining_warnings, list):
            raise ValueError(f"{section_id}: remaining_warnings must be a list.")
        index[section_id] = {
            **entry,
            "section_id": section_id,
            "remaining_warnings": [str(item) for item in remaining_warnings],
        }
    return index


def validate_verification_coverage(section_ids: set[str], verification_index: dict[str, dict[str, Any]]) -> None:
    missing = sorted(section_ids - set(verification_index))
    extra = sorted(set(verification_index) - section_ids)
    if missing:
        raise ValueError(f"Shijing verification ledger is missing entries for: {', '.join(missing[:10])}")
    if extra:
        raise ValueError(f"Shijing verification ledger has unknown section_ids: {', '.join(extra[:10])}")


def verification_entry_is_exportable(entry: dict[str, Any]) -> bool:
    return str(entry.get("decision")) == "export"


def verification_entry_is_verified(entry: dict[str, Any]) -> bool:
    return verification_entry_is_exportable(entry) and str(entry.get("verification_status")) in VERIFIED_EXPORT_STATUSES


def verification_entry_needs_human_review(entry: dict[str, Any]) -> bool:
    return str(entry.get("verification_status")) not in VERIFIED_EXPORT_STATUSES
