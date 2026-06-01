from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from common import (
    MANIFESTS_DIR,
    METADATA_DIR,
    inventory_units,
    load_json_compatible_yaml,
    load_sources,
    load_work_inventory,
    load_work_manifest,
    manifest_ingestion_policy,
    resolve_repo_path,
)

SCHEMA_PATH = METADATA_DIR / "ingestion_policy_schema.json"


def manifest_work_ids() -> list[str]:
    return sorted(path.stem for path in MANIFESTS_DIR.glob("*.yml"))


def load_schema() -> dict[str, Any]:
    return load_json_compatible_yaml(SCHEMA_PATH)


def require_path(errors: list[str], work_id: str, label: str, path_value: str | None) -> None:
    if not path_value:
        errors.append(f"{work_id}: missing {label}.")
        return
    if not resolve_repo_path(path_value).exists():
        errors.append(f"{work_id}: required {label} does not exist at {path_value}.")


def validate_policy_block(work_id: str, manifest: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    policy = manifest.get("ingestion_policy")
    if not isinstance(policy, dict):
        return [f"{work_id}: missing ingestion_policy block."]

    for field in schema["required_policy_fields"]:
        if field not in policy:
            errors.append(f"{work_id}: ingestion_policy missing required field '{field}'.")

    if errors:
        return errors

    if policy["section_unit"] not in schema["allowed_section_units"]:
        errors.append(f"{work_id}: invalid section_unit '{policy['section_unit']}'.")

    allowed_segment_units = policy["allowed_segment_units"]
    if not isinstance(allowed_segment_units, list) or not allowed_segment_units:
        errors.append(f"{work_id}: allowed_segment_units must be a non-empty list.")
    else:
        invalid_units = [unit for unit in allowed_segment_units if unit not in schema["allowed_segment_units"]]
        if invalid_units:
            errors.append(f"{work_id}: invalid allowed_segment_units {invalid_units}.")

    for field in ("preferred_segment_unit", "minimum_required_alignment_scope", "maximum_exact_alignment_scope"):
        if policy[field] not in policy["allowed_segment_units"]:
            errors.append(f"{work_id}: {field} '{policy[field]}' must appear in allowed_segment_units.")

    if policy["rights_policy"] not in schema["allowed_rights_policies"]:
        errors.append(f"{work_id}: invalid rights_policy '{policy['rights_policy']}'.")
    if policy["missing_text_policy"] not in schema["allowed_missing_text_policies"]:
        errors.append(f"{work_id}: invalid missing_text_policy '{policy['missing_text_policy']}'.")
    if policy["commentary_policy"] not in schema["allowed_commentary_policies"]:
        errors.append(f"{work_id}: invalid commentary_policy '{policy['commentary_policy']}'.")
    if policy["section_group_export_policy"] not in schema["allowed_section_group_export_policies"]:
        errors.append(f"{work_id}: invalid section_group_export_policy '{policy['section_group_export_policy']}'.")

    granularity_order = policy["granularity_order"]
    if not isinstance(granularity_order, list) or not granularity_order:
        errors.append(f"{work_id}: granularity_order must be a non-empty list.")
    else:
        missing_from_order = [
            value
            for value in [policy["section_unit"], *policy["allowed_segment_units"]]
            if value not in granularity_order
        ]
        if missing_from_order:
            errors.append(f"{work_id}: granularity_order is missing {missing_from_order}.")

    coarse_units = policy["coarse_alignment_units"]
    if not isinstance(coarse_units, list):
        errors.append(f"{work_id}: coarse_alignment_units must be a list.")
    else:
        invalid_coarse = [unit for unit in coarse_units if unit not in policy["allowed_segment_units"]]
        if invalid_coarse:
            errors.append(f"{work_id}: coarse_alignment_units must be a subset of allowed_segment_units: {invalid_coarse}.")

    if not policy["completion_definition"].strip():
        errors.append(f"{work_id}: completion_definition must be non-empty.")

    if policy["inventory_required"]:
        require_path(errors, work_id, "inventory_path", policy.get("inventory_path"))
    if policy["ingestion_plan_required"]:
        require_path(errors, work_id, "ingestion_plan_path", policy.get("ingestion_plan_path"))
    if policy["source_audit_required"]:
        require_path(errors, work_id, "source_audit_path", policy.get("source_audit_path"))
    if policy["granularity_policy_required"]:
        require_path(errors, work_id, "granularity_policy_path", policy.get("granularity_policy_path"))

    return errors


def validate_inventory_alignment(work_id: str, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    policy = manifest_ingestion_policy(work_id, manifest)
    if not policy["inventory_required"]:
        return errors

    inventory_payload = load_work_inventory(work_id, manifest)
    units = inventory_units(inventory_payload, work_id, manifest)
    section_ids = {section["section_id"] for section in manifest["sections"]}
    inventory_ids = {unit["section_id"] for unit in units}

    if len(units) != len(manifest["sections"]):
        errors.append(
            f"{work_id}: manifest section count {len(manifest['sections'])} does not match inventory count {len(units)}."
        )
    if section_ids != inventory_ids:
        missing_from_manifest = sorted(inventory_ids - section_ids)
        missing_from_inventory = sorted(section_ids - inventory_ids)
        if missing_from_manifest:
            errors.append(f"{work_id}: inventory units missing from manifest: {missing_from_manifest}.")
        if missing_from_inventory:
            errors.append(f"{work_id}: manifest sections missing from inventory: {missing_from_inventory}.")

    return errors


def validate_sources(work_id: str, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    policy = manifest_ingestion_policy(work_id, manifest)
    source_map = {source["source_id"]: source for source in load_sources(work_id)}

    for source in source_map.values():
        if not source.get("rights_status"):
            errors.append(f"{work_id}: source {source['source_id']} is missing rights_status.")
        if not source.get("source_url"):
            errors.append(f"{work_id}: source {source['source_id']} is missing source_url.")

    allowed_rights = set(policy["allowed_export_rights_statuses"])
    for section in manifest["sections"]:
        if section.get("tmx_status") != "complete":
            continue
        source_ids = section.get("source_ids") or {}
        if isinstance(source_ids, dict):
            referenced_source_ids = [
                source_id
                for source_id in (source_ids.get("source_id"), source_ids.get("target_source_id"))
                if source_id
            ]
        else:
            referenced_source_ids = [source_id for source_id in source_ids if source_id]
        if not referenced_source_ids:
            errors.append(f"{work_id}: exportable section {section['section_id']} is missing source_ids.")
            continue
        for source_id in referenced_source_ids:
            if not source_id:
                continue
            source = source_map.get(source_id)
            if source is None:
                errors.append(f"{work_id}: exportable section {section['section_id']} references unknown source {source_id}.")
                continue
            if source.get("rights_status") not in allowed_rights:
                errors.append(
                    f"{work_id}: exportable section {section['section_id']} uses non-exportable rights status "
                    f"{source.get('rights_status')} for {source_id}."
                )
            if policy["rights_policy"] == "proof_of_concept_export_allowed_with_explicit_rights_review":
                if not source.get("release_status"):
                    errors.append(f"{work_id}: proof-of-concept export source {source_id} is missing release_status.")
                if not (source.get("rights_note") or source.get("notes")):
                    errors.append(f"{work_id}: proof-of-concept export source {source_id} is missing rights_note/notes.")
                if not source.get("processed_path"):
                    errors.append(f"{work_id}: proof-of-concept export source {source_id} is missing processed_path.")

    return errors


def validate_ingestion_policy(work_id: str) -> dict[str, Any]:
    schema = load_schema()
    manifest = load_work_manifest(work_id)
    errors = [
        *validate_policy_block(work_id, manifest, schema),
        *validate_inventory_alignment(work_id, manifest),
        *validate_sources(work_id, manifest),
    ]
    return {"work_id": work_id, "error_count": len(errors), "errors": errors}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate manifest-driven ingestion policy requirements.")
    parser.add_argument("--work-id", help="Validate only one work manifest.")
    args = parser.parse_args()

    work_ids = [args.work_id] if args.work_id else manifest_work_ids()
    reports = [validate_ingestion_policy(work_id) for work_id in work_ids]
    errors = [error for report in reports for error in report["errors"]]
    print(json.dumps({"reports": reports, "error_count": len(errors)}, ensure_ascii=False, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
