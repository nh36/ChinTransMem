from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import (
    DEFAULT_DB_PATH,
    METADATA_DIR,
    REPO_ROOT,
    connect_db,
    load_json_compatible_yaml,
    load_work_manifests,
    read_jsonl,
    repo_relative,
    sha256_file,
    utc_now_iso,
)
from init_db import initialize_database


def alignment_path_for_section(section: dict[str, object]) -> Path:
    source_ids = section.get("source_ids")
    if not isinstance(source_ids, dict):
        raise KeyError(f"Section {section['section_id']} does not define source_ids")
    source_id = str(source_ids["source_id"])
    target_source_id = str(source_ids["target_source_id"])
    source_suffix = source_id.split("__", 1)[1] if "__" in source_id else source_id
    target_suffix = target_source_id.split("__", 1)[1] if "__" in target_source_id else target_source_id
    return (
        REPO_ROOT
        / "corpus"
        / "processed"
        / "alignments"
        / f"{section['work_id']}__{section['section_id']}__{source_suffix}__{target_suffix}__alignments.jsonl"
    )


def _load_people() -> list[dict[str, object]]:
    people = load_json_compatible_yaml(METADATA_DIR / "persons.yml")
    for person in people:
        person["roles_json"] = json.dumps(person.pop("roles"), ensure_ascii=False)
    return people


def _load_sources() -> list[dict[str, object]]:
    """Load declared sources from metadata/sources.yml and auto-discover processed segment files.

    Auto-discovered sources are added with conservative default metadata so the importer
    can load their processed segments when sources.yml is incomplete.
    """
    sources = load_json_compatible_yaml(METADATA_DIR / "sources.yml")
    existing_source_ids = {source["source_id"] for source in sources}
    loaded_paths = set()
    # Load known sections so we only auto-add sources for declared sections
    try:
        declared_sections = {s["section_id"] for s in load_json_compatible_yaml(METADATA_DIR / "sections.yml")}
    except Exception:
        declared_sections = set()
    # Also include sections declared in manifests so auto-discovery covers manifest-driven works
    try:
        manifests = load_work_manifests()
        for manifest in manifests:
            for sec in manifest.get("sections", []):
                if sec.get("section_id"):
                    declared_sections.add(sec.get("section_id"))
    except Exception:
        pass
    for source in sources:
        raw_path = REPO_ROOT / source["raw_path"]
        processed_path = REPO_ROOT / source["processed_path"]
        if not raw_path.exists():
            raise FileNotFoundError(raw_path)
        if not processed_path.exists():
            raise FileNotFoundError(processed_path)
        try:
            loaded_paths.add(str((REPO_ROOT / source["processed_path"]).resolve()))
        except Exception:
            loaded_paths.add(str(source["processed_path"]))
        source["author_or_translator_ids_json"] = json.dumps(source.pop("author_or_translator_ids"), ensure_ascii=False)
    # Optionally discover processed segment files under corpus/processed for diagnostics,
    # but do NOT auto-add them to declared sources.yml. The importer must only ingest
    # sources explicitly declared in metadata/sources.yml for deterministic imports.
    # Keep track of discovered files for debugging but don't mutate the authoritative list.
    #
    # processed_root = REPO_ROOT / "corpus" / "processed"
    # if processed_root.exists():
    #     discovered = []
    #     for path in processed_root.rglob("*__segments.jsonl"):
    #         try:
    #             resolved = str(path.resolve())
    #         except Exception:
    #             resolved = str(path)
    #         if resolved in loaded_paths:
    #             continue
    #         try:
    #             candidate_segments = read_jsonl(path)
    #         except Exception:
    #             continue
    #         candidate_source_ids = {seg.get("source_id") for seg in candidate_segments if seg.get("source_id")}
    #         if candidate_source_ids:
    #             discovered.append({"path": str(path.relative_to(REPO_ROOT)), "source_ids": list(candidate_source_ids)})
    #         loaded_paths.add(resolved)
    return sources


def _load_segments(sources: list[dict[str, object]]) -> list[dict[str, object]]:
    """Load segments from declared sources, plus any processed segment files under corpus/processed.

    This makes the importer robust if metadata/sources.yml is incomplete: processed
    segment JSONL files are discovered and loaded automatically to ensure alignments
    referencing them don't fail validation.
    """
    segments: list[dict[str, object]] = []
    loaded_paths: set[str] = set()
    for source in sources:
        processed_path = REPO_ROOT / str(source["processed_path"])
        if processed_path.suffix == ".jsonl" and processed_path.exists():
            candidate_segments = read_jsonl(processed_path)
            # Only include records that have the required DB fields
            valid_segments = [s for s in candidate_segments if s.get("segment_id") and s.get("segment_order") is not None]
            if valid_segments:
                segments.extend(valid_segments)
            try:
                loaded_paths.add(str(processed_path.resolve()))
            except Exception:
                loaded_paths.add(str(processed_path))
    # Also discover any processed segment files under corpus/processed that may not be listed in sources.yml
    processed_root = REPO_ROOT / "corpus" / "processed"
    if processed_root.exists():
        # build set of source_ids declared/auto-added from the provided sources list
        declared_source_ids = {s["source_id"] for s in sources}
        for path in processed_root.rglob("*__segments.jsonl"):
            try:
                resolved = str(path.resolve())
            except Exception:
                resolved = str(path)
            if resolved in loaded_paths:
                continue
            if path.suffix == ".jsonl":
                # Only include discovered segment records that have the required DB fields
                candidate_segments = read_jsonl(path)
                valid_segments = [
                    s
                    for s in candidate_segments
                    if s.get("segment_id") and s.get("segment_order") is not None and s.get("source_id") in declared_source_ids
                ]
                if valid_segments:
                    segments.extend(valid_segments)
                    loaded_paths.add(resolved)
    return segments


def _load_alignments(manifests: list[dict[str, object]]) -> list[dict[str, object]]:
    # Load alignments for sections declared in the provided manifests. This ensures
    # alignments correspond to manifest-driven sections even if metadata/sections.yml
    # was augmented at runtime.
    declared_sections = {sec.get("section_id") for manifest in manifests for sec in manifest.get("sections", [])}
    alignments: list[dict[str, object]] = []
    for manifest in manifests:
        for section in manifest["sections"]:
            if section.get("section_id") not in declared_sections:
                continue
            source_ids = section.get("source_ids") or {}
            if not source_ids or "target_source_id" not in source_ids:
                continue
            alignments.extend(read_jsonl(alignment_path_for_section(section)))
    return alignments


def _validate_alignments(alignments: list[dict[str, object]], segments: list[dict[str, object]]) -> None:
    known_segments = {segment["segment_id"] for segment in segments}
    for alignment in alignments:
        chinese_ids = alignment["chinese_segment_ids"]
        translation_ids = alignment["translation_segment_ids"]
        missing = [segment_id for segment_id in [*chinese_ids, *translation_ids] if segment_id not in known_segments]
        if missing:
            raise ValueError(f"Alignment {alignment['alignment_id']} references missing segments: {missing}")


def import_corpus(db_path: Path | str = DEFAULT_DB_PATH) -> dict[str, object]:
    initialize_database(db_path)

    manifests = load_work_manifests()
    works = load_json_compatible_yaml(METADATA_DIR / "works.yml")
    sections = load_json_compatible_yaml(METADATA_DIR / "sections.yml")
    # Augment sections with any manifest-declared sections that aren't in sections.yml
    existing_section_ids = {s["section_id"] for s in sections}
    for manifest in manifests:
        for sec in manifest.get("sections", []):
            if sec.get("section_id") not in existing_section_ids:
                sections.append(
                    {
                        "section_id": sec.get("section_id"),
                        "work_id": sec.get("work_id", manifest.get("work_id")),
                        "parent_section_id": sec.get("parent_section_id"),
                        "label": sec.get("label", sec.get("section_id")),
                        "canonical_ref": sec.get("canonical_ref", ""),
                        "sort_key": sec.get("sort_key", 0),
                        "notes": sec.get("notes", ""),
                    }
                )
                existing_section_ids.add(sec.get("section_id"))
    persons = _load_people()
    sources = _load_sources()
    segments = _load_segments(sources)
    alignments = _load_alignments(manifests)
    _validate_alignments(alignments, segments)

    started_at = utc_now_iso()
    with connect_db(db_path) as connection:
        connection.execute("DELETE FROM alignments")
        connection.execute("DELETE FROM segments")
        connection.execute("DELETE FROM sources")
        connection.execute("DELETE FROM persons")
        connection.execute("DELETE FROM sections")
        connection.execute("DELETE FROM works")
        connection.executemany(
            """
            INSERT OR REPLACE INTO works (
                work_id, canonical_title, english_title, work_type, language_code, default_citation, notes
            ) VALUES (
                :work_id, :canonical_title, :english_title, :work_type, :language_code, :default_citation, :notes
            )
            """,
            works,
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO sections (
                section_id, work_id, parent_section_id, label, canonical_ref, sort_key, notes
            ) VALUES (
                :section_id, :work_id, :parent_section_id, :label, :canonical_ref, :sort_key, :notes
            )
            """,
            sections,
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO persons (
                person_id, display_name, romanized_name, roles_json, notes
            ) VALUES (
                :person_id, :display_name, :romanized_name, :roles_json, :notes
            )
            """,
            persons,
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO sources (
                source_id, work_id, section_id, language_code, source_kind, citation, source_url,
                raw_path, processed_path, rights_status, author_or_translator_ids_json, notes
            ) VALUES (
                :source_id, :work_id, :section_id, :language_code, :source_kind, :citation, :source_url,
                :raw_path, :processed_path, :rights_status, :author_or_translator_ids_json, :notes
            )
            """,
            sources,
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO segments (
                segment_id, work_id, section_id, source_id, segment_type, segment_order, canonical_ref,
                text_original, text_normalized, notes
            ) VALUES (
                :segment_id, :work_id, :section_id, :source_id, :segment_type, :segment_order, :canonical_ref,
                :text_original, :text_normalized, :notes
            )
            """,
            segments,
        )
        connection.executemany(
            """
            INSERT OR REPLACE INTO alignments (
                alignment_id, work_id, section_id, source_id, target_source_id, alignment_type, confidence,
                chinese_segment_ids_json, translation_segment_ids_json, alignment_granularity, section_unit,
                segment_type, is_coarse_alignment, coarse_alignment_reason, source_segment_count,
                target_segment_count, notes
            ) VALUES (
                :alignment_id, :work_id, :section_id, :source_id, :target_source_id, :alignment_type, :confidence,
                :chinese_segment_ids_json, :translation_segment_ids_json, :alignment_granularity, :section_unit,
                :segment_type, :is_coarse_alignment, :coarse_alignment_reason, :source_segment_count,
                :target_segment_count, :notes
            )
            """,
            [
                {
                    **alignment,
                    "chinese_segment_ids_json": json.dumps(alignment["chinese_segment_ids"], ensure_ascii=False),
                    "translation_segment_ids_json": json.dumps(alignment["translation_segment_ids"], ensure_ascii=False),
                    "alignment_granularity": alignment.get("alignment_granularity"),
                    "section_unit": alignment.get("section_unit"),
                    "segment_type": alignment.get("segment_type"),
                    "is_coarse_alignment": int(bool(alignment.get("is_coarse_alignment", False))),
                    "coarse_alignment_reason": alignment.get("coarse_alignment_reason"),
                    "source_segment_count": alignment.get(
                        "source_segment_count",
                        len(alignment["chinese_segment_ids"]),
                    ),
                    "target_segment_count": alignment.get(
                        "target_segment_count",
                        len(alignment["translation_segment_ids"]),
                    ),
                }
                for alignment in alignments
            ],
        )

        tracked_paths = [REPO_ROOT / source["raw_path"] for source in sources]
        tracked_paths.extend(REPO_ROOT / source["processed_path"] for source in sources)
        tracked_paths.extend(
            alignment_path_for_section(section)
            for manifest in manifests
            for section in manifest["sections"]
            if (section.get("source_ids") or {}).get("target_source_id")
        )
        details = {
            "work_count": len(works),
            "section_count": len(sections),
            "counts": {
                "works": len(works),
                "sections": len(sections),
                "persons": len(persons),
                "sources": len(sources),
                "segments": len(segments),
                "alignments": len(alignments),
            },
            "work_summaries": {
                manifest["work_id"]: {
                    "section_count": len(manifest["sections"]),
                    "summary": manifest["summary"],
                }
                for manifest in manifests
            },
            "checksums": {repo_relative(path): sha256_file(path) for path in tracked_paths},
        }
        finished_at = utc_now_iso()
        connection.execute(
            """
            INSERT OR REPLACE INTO agent_runs (
                run_id, run_kind, status, started_at, finished_at, db_path, details_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"corpus-import-{finished_at}",
                "corpus_import",
                "completed",
                started_at,
                finished_at,
                str(Path(db_path)),
                json.dumps(details, ensure_ascii=False, sort_keys=True),
            ),
        )

    return {
        "db_path": str(db_path),
        "work_count": len(works),
        "section_count": len(sections),
        "segments": len(segments),
        "alignments": len(alignments),
        "work_summaries": {
            manifest["work_id"]: {
                "section_count": len(manifest["sections"]),
                "summary": manifest["summary"],
            }
            for manifest in manifests
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Import all configured corpus metadata and processed files into SQLite.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file.")
    args = parser.parse_args()

    summary = import_corpus(args.db)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
