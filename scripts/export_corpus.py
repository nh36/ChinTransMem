from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from common import (
    DEFAULT_DB_PATH,
    DEFAULT_SOURCE_LANGUAGE,
    DEFAULT_TARGET_LANGUAGE,
    DEFAULT_WORK_ID,
    connect_db,
    corpus_export_paths,
    manifest_sections,
    section_export_paths,
    write_jsonl,
)

XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"


def _combined_ref(segments: list[dict[str, object]]) -> str:
    refs = [str(segment["canonical_ref"]) for segment in segments]
    if not refs:
        return ""
    if len(refs) == 1:
        return refs[0]
    return f"{refs[0]} - {refs[-1]}"


def _combined_text(segments: list[dict[str, object]], *, joiner: str) -> str:
    return joiner.join(str(segment["text_normalized"]) for segment in segments)


def default_section_unit(work_id: str) -> str:
    if work_id == DEFAULT_WORK_ID:
        return "book"
    if work_id == "shijing":
        return "poem"
    return "section"


def load_exact_alignment_rows(
    db_path: Path | str = DEFAULT_DB_PATH,
    work_id: str = DEFAULT_WORK_ID,
    section_id: str | None = None,
) -> list[dict[str, object]]:
    with connect_db(db_path) as connection:
        if section_id is None:
            alignment_rows = connection.execute(
                """
                SELECT alignment_id, section_id, alignment_type, confidence, chinese_segment_ids_json,
                       translation_segment_ids_json, alignment_granularity, section_unit, segment_type,
                       is_coarse_alignment, coarse_alignment_reason, source_segment_count, target_segment_count
                FROM alignments
                WHERE alignment_type = 'exact_or_near_exact' AND work_id = ?
                """
                ,
                (work_id,),
            ).fetchall()
            segment_rows = connection.execute(
                """
                SELECT segment_id, section_id, canonical_ref, text_original, text_normalized, source_id, segment_order,
                       segment_type
                FROM segments
                WHERE work_id = ?
                """
                ,
                (work_id,),
            ).fetchall()
            section_order_map = {
                row["section_id"]: row["sort_key"]
                for row in connection.execute("SELECT section_id, sort_key FROM sections WHERE work_id = ?", (work_id,)).fetchall()
            }
        else:
            alignment_rows = connection.execute(
                """
                SELECT alignment_id, section_id, alignment_type, confidence, chinese_segment_ids_json,
                       translation_segment_ids_json, alignment_granularity, section_unit, segment_type,
                       is_coarse_alignment, coarse_alignment_reason, source_segment_count, target_segment_count
                FROM alignments
                WHERE alignment_type = 'exact_or_near_exact' AND work_id = ? AND section_id = ?
                """,
                (work_id, section_id),
            ).fetchall()
            segment_rows = connection.execute(
                """
                SELECT segment_id, section_id, canonical_ref, text_original, text_normalized, source_id, segment_order,
                       segment_type
                FROM segments
                WHERE work_id = ? AND section_id = ?
                """,
                (work_id, section_id),
            ).fetchall()
            section_order_map = {section_id: 0}

    segment_map = {row["segment_id"]: dict(row) for row in segment_rows}
    export_rows: list[dict[str, object]] = []
    for row in alignment_rows:
        chinese_ids = json.loads(row["chinese_segment_ids_json"])
        translation_ids = json.loads(row["translation_segment_ids_json"])
        chinese_segments = [segment_map[segment_id] for segment_id in chinese_ids]
        translation_segments = [segment_map[segment_id] for segment_id in translation_ids]
        chinese_segments.sort(key=lambda segment: segment["segment_order"])
        translation_segments.sort(key=lambda segment: segment["segment_order"])
        segment_type = row["segment_type"] or chinese_segments[0]["segment_type"]
        export_rows.append(
            {
                "alignment_id": row["alignment_id"],
                "work_id": work_id,
                "section_id": row["section_id"],
                "alignment_type": row["alignment_type"],
                "confidence": row["confidence"],
                "order": min(segment["segment_order"] for segment in chinese_segments),
                "section_unit": row["section_unit"] or default_section_unit(work_id),
                "segment_type": segment_type,
                "alignment_granularity": row["alignment_granularity"] or segment_type or "segment",
                "is_coarse_alignment": bool(row["is_coarse_alignment"]),
                "coarse_alignment_reason": row["coarse_alignment_reason"],
                "source_segment_count": row["source_segment_count"] or len(chinese_ids),
                "target_segment_count": row["target_segment_count"] or len(translation_ids),
                "chinese_ref": _combined_ref(chinese_segments),
                "chinese_text": _combined_text(chinese_segments, joiner=""),
                "translation_ref": _combined_ref(translation_segments),
                "translation_text": _combined_text(translation_segments, joiner=" "),
            }
        )

    export_rows.sort(key=lambda row: (section_order_map.get(row["section_id"], 0), row["order"]))
    return export_rows


def write_tmx(
    export_rows: list[dict[str, object]],
    tmx_output: Path | str,
    source_language: str = DEFAULT_SOURCE_LANGUAGE,
    target_language: str = DEFAULT_TARGET_LANGUAGE,
    *,
    work_id: str = DEFAULT_WORK_ID,
) -> Path:
    tmx_path = Path(tmx_output)
    tmx_path.parent.mkdir(parents=True, exist_ok=True)
    root = ET.Element("tmx", {"version": "1.4"})
    ET.SubElement(
        root,
        "header",
        {
            "creationtool": "ChinTransMem",
            "creationtoolversion": "0.2.0",
            "segtype": "sentence",
            "o-tmf": "ChinTransMem-Lunyu" if work_id == DEFAULT_WORK_ID else f"ChinTransMem-{work_id}",
            "adminlang": "en",
            "srclang": source_language,
            "datatype": "PlainText",
        },
    )
    body = ET.SubElement(root, "body")
    for row in export_rows:
        tu = ET.SubElement(body, "tu", {"tuid": str(row["alignment_id"])})
        for prop_type, prop_value in (
            ("x-work-id", row["work_id"]),
            ("x-section-id", row["section_id"]),
            ("x-section-unit", row["section_unit"]),
            ("x-segment-type", row["segment_type"]),
            ("x-alignment-granularity", row["alignment_granularity"]),
            ("x-is-coarse-alignment", str(row["is_coarse_alignment"]).lower()),
            ("x-alignment-type", row["alignment_type"]),
            ("x-confidence", f"{row['confidence']:.2f}"),
            ("x-source-segment-count", row["source_segment_count"]),
            ("x-target-segment-count", row["target_segment_count"]),
            ("x-chinese-ref", row["chinese_ref"]),
            ("x-translation-ref", row["translation_ref"]),
        ):
            prop = ET.SubElement(tu, "prop", {"type": prop_type})
            prop.text = str(prop_value)
        if row.get("coarse_alignment_reason"):
            prop = ET.SubElement(tu, "prop", {"type": "x-coarse-alignment-reason"})
            prop.text = str(row["coarse_alignment_reason"])
        source_tuv = ET.SubElement(tu, "tuv", {f"{{{XML_NAMESPACE}}}lang": source_language})
        ET.SubElement(source_tuv, "seg").text = str(row["chinese_text"])
        target_tuv = ET.SubElement(tu, "tuv", {f"{{{XML_NAMESPACE}}}lang": target_language})
        ET.SubElement(target_tuv, "seg").text = str(row["translation_text"])

    tree = ET.ElementTree(root)
    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ")
    tree.write(tmx_path, encoding="utf-8", xml_declaration=True)
    return tmx_path


def write_tabular_exports(export_rows: list[dict[str, object]], jsonl_output: Path | str, csv_output: Path | str) -> None:
    write_jsonl(jsonl_output, export_rows)
    csv_path = Path(csv_output)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "alignment_id",
                "work_id",
                "section_id",
                "section_unit",
                "segment_type",
                "alignment_granularity",
                "is_coarse_alignment",
                "coarse_alignment_reason",
                "source_segment_count",
                "target_segment_count",
                "alignment_type",
                "confidence",
                "order",
                "chinese_ref",
                "chinese_text",
                "translation_ref",
                "translation_text",
            ],
        )
        writer.writeheader()
        writer.writerows(export_rows)


def export_corpus(
    db_path: Path | str = DEFAULT_DB_PATH,
    corpus_jsonl_output: Path | str | None = None,
    corpus_csv_output: Path | str | None = None,
    corpus_tmx_output: Path | str | None = None,
    *,
    work_id: str = DEFAULT_WORK_ID,
) -> dict[str, object]:
    corpus_paths = corpus_export_paths(work_id)
    if corpus_jsonl_output is None:
        corpus_jsonl_output = corpus_paths["jsonl"]
    if corpus_csv_output is None:
        corpus_csv_output = corpus_paths["csv"]
    if corpus_tmx_output is None:
        corpus_tmx_output = corpus_paths["tmx"]

    exportable_sections = [
        section
        for section in manifest_sections(work_id)
        if section.get("tmx_status", "complete") == "complete"
    ]
    per_section: list[dict[str, object]] = []
    for section in exportable_sections:
        rows = load_exact_alignment_rows(db_path, work_id, section["section_id"])
        paths = section_export_paths(section["section_id"], work_id)
        write_tabular_exports(rows, paths["jsonl"], paths["csv"])
        write_tmx(rows, paths["tmx"], work_id=work_id)
        per_section.append(
            {
                "section_id": section["section_id"],
                "rows_exported": len(rows),
                "jsonl_output": str(paths["jsonl"]),
                "csv_output": str(paths["csv"]),
                "tmx_output": str(paths["tmx"]),
            }
        )

    corpus_rows = load_exact_alignment_rows(db_path, work_id)
    write_tabular_exports(corpus_rows, corpus_jsonl_output, corpus_csv_output)
    write_tmx(corpus_rows, corpus_tmx_output, work_id=work_id)
    return {
        "work_id": work_id,
        "section_count": len(per_section),
        "rows_exported": len(corpus_rows),
        "jsonl_output": str(corpus_jsonl_output),
        "csv_output": str(corpus_csv_output),
        "tmx_output": str(corpus_tmx_output),
        "sections": per_section,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export aligned corpus passages for a work to JSONL, CSV, and TMX.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file.")
    parser.add_argument("--work-id", default=DEFAULT_WORK_ID, help="Which work manifest to export.")
    parser.add_argument("--jsonl-output", default=None, help="Where to write the corpus JSONL export.")
    parser.add_argument("--csv-output", default=None, help="Where to write the corpus CSV export.")
    parser.add_argument("--tmx-output", default=None, help="Where to write the corpus TMX export.")
    args = parser.parse_args()

    summary = export_corpus(
        args.db,
        args.jsonl_output,
        args.csv_output,
        args.tmx_output,
        work_id=args.work_id,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
