from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from common import (
    DEFAULT_WORK_ID,
    METADATA_DIR,
    load_json_compatible_yaml,
    load_work_manifest,
    load_work_manifests,
    write_json,
)

WORKS_PATH = METADATA_DIR / "works.yml"
SECTIONS_PATH = METADATA_DIR / "sections.yml"
SOURCES_PATH = METADATA_DIR / "sources.yml"
ALIASES_PATH = METADATA_DIR / "romanization_aliases.yml"
INGESTION_LOG_PATH = METADATA_DIR / "ingestion_log.yml"


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return list(load_json_compatible_yaml(path))


def _metadata_only_sections(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for section in manifest["sections"]:
        sections.append(
            {
                "section_id": section["section_id"],
                "work_id": manifest["work_id"],
                "parent_section_id": section.get("parent_section_id"),
                "label": section["label"],
                "canonical_ref": section["canonical_ref"],
                "sort_key": section["sort_key"],
                "notes": section.get("notes", f"Metadata skeleton for {section['label']}."),
            }
        )
    return sections


def _merge_records(
    records_by_work: list[tuple[str, list[dict[str, Any]]]],
    *,
    key: str | None = None,
    key_fn: Any = None,
    sort_field: str | None = None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, records in records_by_work:
        ordered = records
        if sort_field is not None:
            ordered = sorted(records, key=lambda record: record.get(sort_field) or 0)
        for record in ordered:
            if key_fn is not None:
                identifier = str(key_fn(record))
            else:
                identifier = str(record[key or ""])
            if identifier in seen:
                continue
            merged.append(record)
            seen.add(identifier)
    return merged


def _merge_sources(records_by_work: list[tuple[str, list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, records in records_by_work:
        for record in records:
            source_id = str(record["source_id"])
            if source_id in seen:
                continue
            merged.append(record)
            seen.add(source_id)
    return merged


def _merge_ingestion_log(records_by_work: list[tuple[str, list[dict[str, Any]]]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, records in records_by_work:
        for record in records:
            run_id = str(record["run_id"])
            if run_id in seen:
                continue
            merged.append(record)
            seen.add(run_id)
    return merged


def bootstrap_work(work_id: str, *, skip_fetch: bool = False) -> dict[str, Any]:
    manifest = load_work_manifest(work_id)
    if work_id == "lunyu":
        from bootstrap_lunyu_corpus import bootstrap_corpus as bootstrap_lunyu_corpus

        summary = bootstrap_lunyu_corpus(skip_fetch=skip_fetch)
        return {
            "work_id": work_id,
            "summary": summary,
            "manifest": load_work_manifest(work_id),
            "sections": _load_json_list(SECTIONS_PATH),
            "sources": _load_json_list(SOURCES_PATH),
            "aliases": _load_json_list(ALIASES_PATH),
            "ingestion_log": _load_json_list(INGESTION_LOG_PATH),
        }

    return {
        "work_id": work_id,
        "summary": manifest["summary"],
        "manifest": manifest,
        "sections": _metadata_only_sections(manifest),
        "sources": list(manifest.get("sources", [])),
        "aliases": list(manifest.get("romanization_aliases", [])),
        "ingestion_log": list(manifest.get("ingestion_log", [])),
    }


def bootstrap_all_manifests(*, skip_fetch: bool = False, work_id: str | None = None) -> dict[str, Any]:
    work_manifests = load_work_manifests()
    work_ids = [str(manifest["work_id"]) for manifest in work_manifests]
    if work_id is not None and work_id not in work_ids:
        raise KeyError(f"Unknown work_id: {work_id}")
    bootstrapped = [bootstrap_work(work_id, skip_fetch=skip_fetch) for work_id in work_ids]

    sections_by_work = [(result["work_id"], result["sections"]) for result in bootstrapped]
    sources_by_work = [(result["work_id"], result["sources"]) for result in bootstrapped]
    aliases_by_work = [(result["work_id"], result["aliases"]) for result in bootstrapped]
    ingestion_by_work = [(result["work_id"], result["ingestion_log"]) for result in bootstrapped]

    merged_sections = _merge_records(sections_by_work, key="section_id", sort_field="sort_key")
    merged_sources = _merge_sources(sources_by_work)
    merged_aliases = _merge_records(
        aliases_by_work,
        key_fn=lambda record: (
            record["entity_type"],
            record["entity_id"],
            record["alias"],
            record["romanization_system"],
        ),
    )
    merged_ingestion = _merge_ingestion_log(ingestion_by_work)

    write_json(SECTIONS_PATH, merged_sections)
    write_json(SOURCES_PATH, merged_sources)
    write_json(ALIASES_PATH, merged_aliases)
    write_json(INGESTION_LOG_PATH, merged_ingestion)

    return {
        "default_work_id": DEFAULT_WORK_ID,
        "requested_work_id": work_id,
        "work_count": len(work_ids),
        "works": [
            {
                "work_id": result["work_id"],
                "section_count": len(result["manifest"]["sections"]),
                "summary": result["manifest"]["summary"],
            }
            for result in bootstrapped
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bootstrap manifest-driven corpus metadata for all configured works."
    )
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Reuse local raw captures instead of downloading fresh copies.",
    )
    parser.add_argument("--work-id", default=None, help="Bootstrap metadata for a specific work while preserving aggregate metadata.")
    args = parser.parse_args()
    print(bootstrap_all_manifests(skip_fetch=args.skip_fetch, work_id=args.work_id))


if __name__ == "__main__":
    main()
