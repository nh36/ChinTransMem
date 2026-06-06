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
SUPPORTED_BOOTSTRAP_WORK_IDS = [
    "lunyu",
    "mengzi",
    "shijing",
    "laozi",
    "shangshu",
    "yijing",
    "mozi",
    "liji",
    "shiji",
]


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return list(load_json_compatible_yaml(path))


def _manifest_sections(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for section in manifest["sections"]:
        sections.append(
            {
                "section_id": section["section_id"],
                "work_id": manifest["work_id"],
                "parent_section_id": section.get("parent_section_id"),
                "label": section.get("label", section.get("title", section["section_id"])),
                "canonical_ref": section["canonical_ref"],
                "sort_key": section["sort_key"],
                "notes": section.get(
                    "notes",
                    f"Metadata skeleton for {section.get('label', section.get('title', section['section_id']))}.",
                ),
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


def bootstrap_work(work_id: str, *, skip_fetch: bool = False, batch_id: str | None = None) -> dict[str, Any]:
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
    if work_id == "mengzi":
        from bootstrap_mengzi_corpus import bootstrap_corpus as bootstrap_mengzi_corpus

        summary = bootstrap_mengzi_corpus(skip_fetch=skip_fetch)
        manifest = load_work_manifest(work_id)
        return {
            "work_id": work_id,
            "summary": summary,
            "manifest": manifest,
            "sections": _manifest_sections(manifest),
            "sources": list(manifest.get("sources", [])),
            "aliases": list(manifest.get("romanization_aliases", [])),
            "ingestion_log": list(manifest.get("ingestion_log", [])),
        }
    if work_id == "shijing":
        from bootstrap_shijing_corpus import bootstrap_corpus as bootstrap_shijing_corpus

        summary = bootstrap_shijing_corpus(skip_fetch=skip_fetch)
        manifest = load_work_manifest(work_id)
        return {
            "work_id": work_id,
            "summary": summary,
            "manifest": manifest,
            "sections": _manifest_sections(manifest),
            "sources": list(manifest.get("sources", [])),
            "aliases": list(manifest.get("romanization_aliases", [])),
            "ingestion_log": list(manifest.get("ingestion_log", [])),
        }
    if work_id == "laozi":
        from bootstrap_laozi_corpus import bootstrap_corpus as bootstrap_laozi_corpus

        summary = bootstrap_laozi_corpus(skip_fetch=skip_fetch)
        manifest = load_work_manifest(work_id)
        return {
            "work_id": work_id,
            "summary": summary,
            "manifest": manifest,
            "sections": _manifest_sections(manifest),
            "sources": list(manifest.get("sources", [])),
            "aliases": list(manifest.get("romanization_aliases", [])),
            "ingestion_log": list(manifest.get("ingestion_log", [])),
        }
    if work_id == "shangshu":
        from bootstrap_shangshu_corpus import bootstrap_corpus as bootstrap_shangshu_corpus

        summary = bootstrap_shangshu_corpus(skip_fetch=skip_fetch)
        manifest = load_work_manifest(work_id)
        return {
            "work_id": work_id,
            "summary": summary,
            "manifest": manifest,
            "sections": _manifest_sections(manifest),
            "sources": list(manifest.get("sources", [])),
            "aliases": list(manifest.get("romanization_aliases", [])),
            "ingestion_log": list(manifest.get("ingestion_log", [])),
        }
    if work_id == "yijing":
        from bootstrap_yijing_corpus import bootstrap_corpus as bootstrap_yijing_corpus

        summary = bootstrap_yijing_corpus(skip_fetch=skip_fetch)
        manifest = load_work_manifest(work_id)
        return {
            "work_id": work_id,
            "summary": summary,
            "manifest": manifest,
            "sections": _manifest_sections(manifest),
            "sources": list(manifest.get("sources", [])),
            "aliases": list(manifest.get("romanization_aliases", [])),
            "ingestion_log": list(manifest.get("ingestion_log", [])),
        }
    if work_id == "mozi":
        from bootstrap_mozi_corpus import bootstrap_corpus as bootstrap_mozi_corpus

        summary = bootstrap_mozi_corpus(skip_fetch=skip_fetch)
        manifest = load_work_manifest(work_id)
        return {
            "work_id": work_id,
            "summary": summary,
            "manifest": manifest,
            "sections": _manifest_sections(manifest),
            "sources": list(manifest.get("sources", [])),
            "aliases": list(manifest.get("romanization_aliases", [])),
            "ingestion_log": list(manifest.get("ingestion_log", [])),
        }
    if work_id == "liji":
        from bootstrap_liji_corpus import bootstrap_liji_corpus

        result = bootstrap_liji_corpus(skip_fetch=skip_fetch)
        manifest = load_work_manifest(work_id)
        return {
            "work_id": work_id,
            "summary": result["summary"],
            "manifest": manifest,
            "sections": result["import_sections"],
            "sources": result["import_sources"],
            "aliases": result["romanization_aliases"],
            "ingestion_log": result["ingestion_log"],
        }
    if work_id == "shiji":
        from bootstrap_shiji_corpus import bootstrap_shiji_corpus

        result = bootstrap_shiji_corpus(skip_fetch=skip_fetch, batch_id=batch_id)
        manifest = load_work_manifest(work_id)
        return {
            "work_id": work_id,
            "summary": result["summary"],
            "manifest": manifest,
            "sections": result["import_sections"],
            "sources": result["import_sources"],
            "aliases": result["romanization_aliases"],
            "ingestion_log": result["ingestion_log"],
        }

    manifest = load_work_manifest(work_id)

    return {
        "work_id": work_id,
        "summary": manifest["summary"],
        "manifest": manifest,
        "sections": _manifest_sections(manifest),
        "sources": list(manifest.get("sources", [])),
        "aliases": list(manifest.get("romanization_aliases", [])),
        "ingestion_log": list(manifest.get("ingestion_log", [])),
    }


def bootstrap_all_manifests(
    *,
    skip_fetch: bool = False,
    work_id: str | None = None,
    batch_id: str | None = None,
) -> dict[str, Any]:
    work_manifests = load_work_manifests()
    manifest_work_ids = [str(manifest["work_id"]) for manifest in work_manifests]
    work_ids: list[str] = []
    for candidate in SUPPORTED_BOOTSTRAP_WORK_IDS + manifest_work_ids:
        if candidate not in work_ids:
            work_ids.append(candidate)
    if work_id is not None and work_id not in work_ids:
        raise KeyError(f"Unknown work_id: {work_id}")
    manifest_by_work_id = {str(manifest["work_id"]): manifest for manifest in work_manifests}
    bootstrapped: list[dict[str, Any]] = []
    for current_work_id in work_ids:
        manifest = manifest_by_work_id.get(current_work_id)
        if work_id is None or current_work_id == work_id:
            bootstrapped.append(
                bootstrap_work(
                    current_work_id,
                    skip_fetch=skip_fetch,
                    batch_id=batch_id if current_work_id == work_id else None,
                )
            )
            continue
        if manifest is None:
            continue
        bootstrapped.append(
            {
                "work_id": current_work_id,
                "summary": manifest["summary"],
                "manifest": manifest,
                "sections": _manifest_sections(manifest),
                "sources": list(manifest.get("sources", [])),
                "aliases": list(manifest.get("romanization_aliases", [])),
                "ingestion_log": list(manifest.get("ingestion_log", [])),
            }
        )

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

    # Perform a safe merge when writing sources.yml: preserve any existing source
    # records that are unrelated to the current bootstrap run, update existing
    # records when the same source_id is present in the new set, and append any
    # genuinely new source records. This prevents accidental truncation when a
    # subset of works are bootstrapped in isolation.
    def _safe_write_sources(new_sources: list[dict[str, Any]]) -> None:
        try:
            existing = load_json_compatible_yaml(SOURCES_PATH)
        except Exception:
            existing = []
        new_by_id = {str(s["source_id"]): s for s in new_sources}
        final: list[dict[str, Any]] = []
        # Preserve existing order, updating records that appear in new_sources
        for s in existing:
            sid = str(s["source_id"])
            if sid in new_by_id:
                merged = dict(s)
                merged.update(new_by_id[sid])
                final.append(merged)
                del new_by_id[sid]
            else:
                final.append(s)
        # Append any remaining new sources not already preserved
        for sid, s in new_by_id.items():
            final.append(s)
        write_json(SOURCES_PATH, final)

    _safe_write_sources(merged_sources)
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
