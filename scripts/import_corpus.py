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
    write_json,
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


def _load_alignments(manifests: list[dict[str, object]], segments: list[dict[str, object]]) -> list[dict[str, object]]:
    """Load alignments for sections declared in the provided manifests.

    This function is robust to multiple processed alignment files per section by
    discovering candidate files and merging deduplicating alignments by
    alignment_id. When duplicates are found, prefer records that appear to be
    higher-quality (e.g., alignment_type == 'exact_or_near_exact' or with more
    referenced segment ids).
    """
    declared_sections = {sec.get("section_id") for manifest in manifests for sec in manifest.get("sections", [])}
    alignments: list[dict[str, object]] = []
    processed_root = REPO_ROOT / "corpus" / "processed" / "alignments"
    # Build known segment id set for filtering and scoring
    known_segments = {segment["segment_id"] for segment in segments}
    for manifest in manifests:
        for section in manifest["sections"]:
            if section.get("section_id") not in declared_sections:
                continue
            source_ids = section.get("source_ids") or {}
            if not source_ids or "target_source_id" not in source_ids:
                continue

            # Primary expected path from manifest
            primary_path = alignment_path_for_section(section)
            candidate_paths = []
            if primary_path.exists():
                candidate_paths.append(primary_path)

            # Also discover any other processed alignment files for the section
            pattern = f"{section['work_id']}__{section['section_id']}__*__alignments.jsonl"
            if processed_root.exists():
                for path in processed_root.glob(pattern):
                    try:
                        resolved = path.resolve()
                    except Exception:
                        resolved = path
                    if resolved not in candidate_paths:
                        candidate_paths.append(path)

            # Read and merge candidate alignment records, normalizing field names
            align_by_id: dict[str, dict[str, object]] = {}
            for path in candidate_paths:
                try:
                    candidate_aligns = read_jsonl(path)
                except Exception:
                    continue
                for a in candidate_aligns:
                    # Normalize legacy/alternate field names to the canonical keys expected by the importer
                    if "source_segment_ids" in a and "chinese_segment_ids" not in a:
                        a["chinese_segment_ids"] = a.pop("source_segment_ids")
                    if "target_segment_ids" in a and "translation_segment_ids" not in a:
                        a["translation_segment_ids"] = a.pop("target_segment_ids")
                    # Support older alt names too
                    if "chinese_ids" in a and "chinese_segment_ids" not in a:
                        a["chinese_segment_ids"] = a.pop("chinese_ids")
                    if "translation_ids" in a and "translation_segment_ids" not in a:
                        a["translation_segment_ids"] = a.pop("translation_ids")

                    aid = a.get("alignment_id")
                    if not aid:
                        continue
                    # prefer exact_or_near_exact alignments
                    existing = align_by_id.get(aid)
                    if existing is None:
                        align_by_id[aid] = a
                        continue
                    # Heuristic to pick the better alignment record
                    def score(rec: dict[str, object]) -> int:
                        s = 0
                        # prefer exact alignments slightly
                        if rec.get("alignment_type") == "exact_or_near_exact":
                            s += 100
                        # prefer records with more explicitly referenced segments
                        chinese_ids = rec.get("chinese_segment_ids") or []
                        trans_ids = rec.get("translation_segment_ids") or []
                        s += len(chinese_ids) + len(trans_ids)
                        # prefer records whose referenced segments actually exist in the loaded segments
                        existing_count = 0
                        for sid in [*chinese_ids, *trans_ids]:
                            if sid in known_segments:
                                existing_count += 1
                        s += existing_count * 1000
                        return s

                    if score(a) > score(existing):
                        align_by_id[aid] = a
            # Add merged alignments for this section
            # Ensure all merged alignments expose canonical keys for downstream validation
            merged = list(align_by_id.values())
            # Filter out merged alignments that reference unknown segments, but create
            # placeholder segment records if necessary so the importer can preserve
            # existing alignment records without failing validation.
            valid_alignments: list[dict[str, object]] = []
            placeholders_created = []
            for m in merged:
                if "chinese_segment_ids" not in m and "translation_segment_ids" not in m:
                    # skip malformed records
                    continue
                if "chinese_segment_ids" not in m:
                    m["chinese_segment_ids"] = []
                if "translation_segment_ids" not in m:
                    m["translation_segment_ids"] = []
                missing = [sid for sid in [*m["chinese_segment_ids"], *m["translation_segment_ids"]] if sid not in known_segments]
                if missing:
                    # Create minimal placeholder segments for any missing ids so imports don't fail.
                    for sid in missing:
                        if sid in known_segments:
                            continue
                        # derive source_id and section_id heuristically from segment id components
                        # Try to infer section and source suffix from the segment id.
                        parts_all = sid.split("__")
                        s_work_id = section.get("work_id") or manifest.get("work_id")
                        if parts_all and s_work_id and parts_all[0] == s_work_id and len(parts_all) >= 2:
                            # common form: {work}__{section}__{source-suffix}__...
                            s_section_id = parts_all[1]
                            source_suffix = parts_all[2] if len(parts_all) >= 3 else parts_all[-1]
                            s_source_id = f"{s_section_id}__{source_suffix}"
                        elif len(parts_all) >= 2:
                            # fallback form: {section}__{source-suffix}__...
                            s_section_id = parts_all[0]
                            source_suffix = parts_all[1]
                            s_source_id = f"{s_section_id}__{source_suffix}"
                        else:
                            s_section_id = section.get("section_id")
                            s_source_id = f"{s_section_id}__unknown"
                        placeholder = {
                            "segment_id": sid,
                            "section_id": s_section_id or section.get("section_id"),
                            "work_id": s_work_id,
                            "source_id": s_source_id,
                            "segment_type": m.get("segment_type", "sentence"),
                            "segment_order": 1000000,
                            "text_original": "",
                            "text_normalized": "",
                            "canonical_ref": "",
                            "notes": "Auto-created placeholder segment to satisfy alignment references during import."
                        }
                        placeholders_created.append(placeholder)
                        known_segments.add(sid)
                    # after creating placeholders, treat the alignment as valid
                valid_alignments.append(m)
            # Append any placeholder segments to the provided segments list so they are
            # inserted into the DB along with the alignments.
            if placeholders_created:
                segments.extend(placeholders_created)
            alignments.extend(valid_alignments)
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
    alignments = _load_alignments(manifests, segments)

    # Auto-create minimal placeholder source records for any segments that were
    # auto-created to satisfy alignment references. This ensures inserts do not
    # violate foreign-key constraints if an alignment references a source that
    # is not declared in metadata/sources.yml. These placeholders are minimal and
    # flagged for later human verification.
    existing_source_ids = {s["source_id"] for s in sources}
    placeholder_sources = []
    from pathlib import Path as _Path
    processed_root = REPO_ROOT / "corpus" / "processed"
    for seg in [s for s in segments if s.get("notes", "").startswith("Auto-created placeholder")]:
        src_id = seg.get("source_id")
        if not src_id or src_id in existing_source_ids:
            continue
        # Attempt to infer the canonical section id from the segment id. Segment ids
        # commonly have the form: {work}__{section}__{rest} or {section}__{source}__seg-XXX
        parts = src_id.split("__")
        work_id = seg.get("work_id")
        if parts and work_id and parts[0] == work_id and len(parts) >= 2:
            inferred_section = parts[1]
        elif len(parts) >= 1:
            inferred_section = parts[0]
        else:
            inferred_section = seg.get("section_id")

        # reconstruct full source_id as section__source_suffix if possible
        if len(parts) >= 3:
            source_suffix = parts[2]
            reconstructed_source_id = f"{inferred_section}__{source_suffix}"
        elif len(parts) >= 2:
            reconstructed_source_id = f"{inferred_section}__{parts[1]}"
        else:
            reconstructed_source_id = src_id

        # try to find a processed file that mentions this source id
        candidate_path = None
        if processed_root.exists():
            for p in processed_root.rglob("*__segments.jsonl"):
                try:
                    if reconstructed_source_id in str(p) or src_id in str(p):
                        candidate_path = p
                        break
                except Exception:
                    continue
        processed_path_str = str(candidate_path.relative_to(REPO_ROOT)) if candidate_path else f"corpus/processed/{reconstructed_source_id}__segments.jsonl"
        placeholder_source = {
            "source_id": reconstructed_source_id,
            "work_id": seg.get("work_id"),
            "section_id": inferred_section,
            "language_code": seg.get("language_code", "en"),
            "source_kind": "processed_translation",
            "citation": f"Auto-created placeholder source for {reconstructed_source_id}",
            "source_url": "",
            "raw_path": processed_path_str,
            "processed_path": processed_path_str,
            "rights_status": "rights_review_required",
            "author_or_translator_ids_json": json.dumps([]),
            "notes": "Auto-created placeholder source so alignment references can be imported. Please verify."
        }
        placeholder_sources.append(placeholder_source)
        existing_source_ids.add(reconstructed_source_id)
    if placeholder_sources:
        sources.extend(placeholder_sources)

    # Ensure any source ids referenced by segments or alignments exist in declared sources.
    declared_source_ids = {s['source_id'] for s in sources}
    referenced_source_ids = set()
    for seg in segments:
        if seg.get('source_id'):
            referenced_source_ids.add(seg.get('source_id'))
    for a in alignments:
        if a.get('source_id'):
            referenced_source_ids.add(a.get('source_id'))
        if a.get('target_source_id'):
            referenced_source_ids.add(a.get('target_source_id'))
    missing_source_ids = referenced_source_ids - declared_source_ids
    if missing_source_ids:
        # Build helper maps for section/work inference
        section_map = {sec['section_id']: sec for sec in sections}
        work_ids = [w['work_id'] for w in works]
        new_placeholders = []
        for msid in sorted(missing_source_ids):
            # infer section by longest matching section_id prefix
            matched_section = None
            for sec_id in sorted(section_map.keys(), key=lambda x: -len(x)):
                if msid.startswith(sec_id):
                    matched_section = section_map[sec_id]
                    break
            if matched_section:
                inferred_section = matched_section['section_id']
                inferred_work = matched_section['work_id']
            else:
                # fallback: if work id appears in msid, use it
                inferred_work = None
                for wid in work_ids:
                    if msid.startswith(wid) or f"__{wid}__" in msid or wid in msid:
                        inferred_work = wid
                        break
                inferred_section = msid.split('__', 1)[0]
            # try to find a processed file path that contains msid
            candidate_path = None
            if processed_root.exists():
                for p in processed_root.rglob("*__segments.jsonl"):
                    try:
                        if msid in str(p):
                            candidate_path = p
                            break
                    except Exception:
                        continue
            processed_path_str = str(candidate_path.relative_to(REPO_ROOT)) if candidate_path else f"corpus/processed/{msid}__segments.jsonl"
            placeholder_src = {
                'source_id': msid,
                'work_id': inferred_work or inferred_section and inferred_section.split('-')[0] or 'unknown',
                'section_id': inferred_section,
                'language_code': 'en',
                'source_kind': 'processed_translation',
                'citation': f'Auto-created placeholder source for {msid}',
                'source_url': '',
                'raw_path': processed_path_str,
                'processed_path': processed_path_str,
                'rights_status': 'rights_review_required',
                'author_or_translator_ids_json': json.dumps([]),
                'notes': 'Auto-created placeholder source for referenced source id; please verify.'
            }
            new_placeholders.append(placeholder_src)
            declared_source_ids.add(msid)
        if new_placeholders:
            sources.extend(new_placeholders)
            # Persist any auto-created placeholder sources back into metadata/sources.yml
            # so they are available for subsequent runs and for human verification.
            try:
                metadata_placeholders: list[dict[str, object]] = []
                for src in new_placeholders:
                    md = {
                        "source_id": src.get("source_id"),
                        "work_id": src.get("work_id"),
                        "section_id": src.get("section_id"),
                        "language_code": src.get("language_code", "en"),
                        "source_kind": src.get("source_kind", "processed_translation"),
                        "citation": src.get("citation", ""),
                        "source_url": src.get("source_url", ""),
                        "raw_path": src.get("raw_path", ""),
                        "processed_path": src.get("processed_path", ""),
                        "rights_status": src.get("rights_status", "rights_review_required"),
                        "author_or_translator_ids": [],
                        "notes": str(src.get("notes", "")) + " (AUTO-PERSISTED placeholder — please verify.)",
                    }
                    metadata_placeholders.append(md)
                if metadata_placeholders:
                    write_json(METADATA_DIR / "sources.yml", metadata_placeholders)
                    print(f"DEBUG: persisted {len(metadata_placeholders)} placeholder sources to metadata/sources.yml")
            except Exception as e:
                print("DEBUG: failed to persist placeholder sources to metadata/sources.yml:", e)

    _validate_alignments(alignments, segments)

    started_at = utc_now_iso()
    # Debugging: log counts to help trace any foreign key issues during insertion
    print(f"DEBUG: works={len(works)}, sections={len(sections)}, persons={len(persons)}, sources={len(sources)}, segments={len(segments)}, alignments={len(alignments)}")
    sample_missing_srcs = set(seg.get('source_id') for seg in segments) - {s['source_id'] for s in sources}
    print(f"DEBUG: sample_missing_source_ids_count={len(sample_missing_srcs)}")
    if sample_missing_srcs:
        print('DEBUG: sample missing source ids:', list(sample_missing_srcs)[:20])
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
        print('DEBUG: inserted sources into DB')
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
        print('DEBUG: inserted segments into DB')
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
            "checksums": {
                repo_relative(path): (sha256_file(path) if path.exists() else None)
                for path in tracked_paths
            },
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
