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
    sources = load_json_compatible_yaml(METADATA_DIR / "sources.yml")
    for source in sources:
        raw_path = REPO_ROOT / source["raw_path"]
        processed_path = REPO_ROOT / source["processed_path"]
        if not raw_path.exists():
            raise FileNotFoundError(raw_path)
        if not processed_path.exists():
            raise FileNotFoundError(processed_path)
        source["author_or_translator_ids_json"] = json.dumps(source.pop("author_or_translator_ids"), ensure_ascii=False)
    return sources


def _load_segments(sources: list[dict[str, object]]) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    for source in sources:
        processed_path = REPO_ROOT / str(source["processed_path"])
        if processed_path.suffix == ".jsonl":
            segments.extend(read_jsonl(processed_path))
    return segments


def _load_alignments(manifests: list[dict[str, object]]) -> list[dict[str, object]]:
    alignments: list[dict[str, object]] = []
    for manifest in manifests:
        for section in manifest["sections"]:
            if not section.get("source_ids"):
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
                chinese_segment_ids_json, translation_segment_ids_json, notes
            ) VALUES (
                :alignment_id, :work_id, :section_id, :source_id, :target_source_id, :alignment_type, :confidence,
                :chinese_segment_ids_json, :translation_segment_ids_json, :notes
            )
            """,
            [
                {
                    **alignment,
                    "chinese_segment_ids_json": json.dumps(alignment["chinese_segment_ids"], ensure_ascii=False),
                    "translation_segment_ids_json": json.dumps(alignment["translation_segment_ids"], ensure_ascii=False),
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
            if section.get("source_ids")
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
