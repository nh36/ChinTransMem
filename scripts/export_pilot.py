from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from common import (
    DEFAULT_CSV_EXPORT,
    DEFAULT_DB_PATH,
    DEFAULT_JSONL_EXPORT,
    DEFAULT_TMX_EXPORT,
    PILOT_SECTION_ID,
    PILOT_SOURCE_LANGUAGE,
    PILOT_TARGET_LANGUAGE,
    connect_db,
    write_jsonl,
)

XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"


def load_exact_alignment_rows(db_path: Path | str = DEFAULT_DB_PATH) -> list[dict[str, object]]:
    with connect_db(db_path) as connection:
        rows = connection.execute(
            """
            SELECT alignment_id, alignment_type, confidence, chinese_segment_ids_json, translation_segment_ids_json
            FROM alignments
            WHERE section_id = ?
            ORDER BY alignment_id
            """,
            (PILOT_SECTION_ID,),
        ).fetchall()
        segment_rows = connection.execute(
            """
            SELECT segment_id, canonical_ref, text_original, text_normalized, source_id, segment_order
            FROM segments
            WHERE section_id = ?
            """,
            (PILOT_SECTION_ID,),
        ).fetchall()

    segment_map = {row["segment_id"]: dict(row) for row in segment_rows}
    export_rows: list[dict[str, object]] = []

    for row in rows:
        chinese_ids = json.loads(row["chinese_segment_ids_json"])
        translation_ids = json.loads(row["translation_segment_ids_json"])
        if len(chinese_ids) != 1 or len(translation_ids) != 1:
            continue

        chinese_segment = segment_map[chinese_ids[0]]
        translation_segment = segment_map[translation_ids[0]]
        export_rows.append(
            {
                "alignment_id": row["alignment_id"],
                "alignment_type": row["alignment_type"],
                "confidence": row["confidence"],
                "order": chinese_segment["segment_order"],
                "chinese_ref": chinese_segment["canonical_ref"],
                "chinese_text": chinese_segment["text_normalized"],
                "translation_ref": translation_segment["canonical_ref"],
                "translation_text": translation_segment["text_normalized"],
            }
        )

    return export_rows


def write_tmx(
    export_rows: list[dict[str, object]],
    tmx_output: Path | str = DEFAULT_TMX_EXPORT,
    source_language: str = PILOT_SOURCE_LANGUAGE,
    target_language: str = PILOT_TARGET_LANGUAGE,
) -> Path:
    tmx_path = Path(tmx_output)
    tmx_path.parent.mkdir(parents=True, exist_ok=True)

    root = ET.Element("tmx", {"version": "1.4"})
    ET.SubElement(
        root,
        "header",
        {
            "creationtool": "ChinTransMem",
            "creationtoolversion": "0.1.0",
            "segtype": "sentence",
            "o-tmf": "ChinTransMem-Pilot",
            "adminlang": "en",
            "srclang": source_language,
            "datatype": "PlainText",
        },
    )
    body = ET.SubElement(root, "body")

    for row in export_rows:
        tu = ET.SubElement(body, "tu", {"tuid": str(row["alignment_id"])})
        for prop_type, prop_value in (
            ("x-alignment-type", row["alignment_type"]),
            ("x-confidence", f"{row['confidence']:.2f}"),
            ("x-chinese-ref", row["chinese_ref"]),
            ("x-translation-ref", row["translation_ref"]),
        ):
            prop = ET.SubElement(tu, "prop", {"type": prop_type})
            prop.text = str(prop_value)

        source_tuv = ET.SubElement(tu, "tuv", {f"{{{XML_NAMESPACE}}}lang": source_language})
        source_seg = ET.SubElement(source_tuv, "seg")
        source_seg.text = str(row["chinese_text"])

        target_tuv = ET.SubElement(tu, "tuv", {f"{{{XML_NAMESPACE}}}lang": target_language})
        target_seg = ET.SubElement(target_tuv, "seg")
        target_seg.text = str(row["translation_text"])

    tree = ET.ElementTree(root)
    if hasattr(ET, "indent"):
        ET.indent(tree, space="  ")
    tree.write(tmx_path, encoding="utf-8", xml_declaration=True)
    return tmx_path


def export_pilot(
    db_path: Path | str = DEFAULT_DB_PATH,
    jsonl_output: Path | str = DEFAULT_JSONL_EXPORT,
    csv_output: Path | str = DEFAULT_CSV_EXPORT,
    tmx_output: Path | str = DEFAULT_TMX_EXPORT,
) -> dict[str, object]:
    export_rows = load_exact_alignment_rows(db_path)
    write_jsonl(jsonl_output, export_rows)

    csv_path = Path(csv_output)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "alignment_id",
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
    write_tmx(export_rows, tmx_output)

    return {
        "jsonl_output": str(jsonl_output),
        "csv_output": str(csv_output),
        "tmx_output": str(tmx_output),
        "rows_exported": len(export_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export aligned Lunyu plus Legge pilot passages.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file.")
    parser.add_argument("--jsonl-output", default=str(DEFAULT_JSONL_EXPORT), help="Where to write the JSONL export.")
    parser.add_argument("--csv-output", default=str(DEFAULT_CSV_EXPORT), help="Where to write the CSV export.")
    parser.add_argument("--tmx-output", default=str(DEFAULT_TMX_EXPORT), help="Where to write the TMX export.")
    args = parser.parse_args()

    summary = export_pilot(args.db, args.jsonl_output, args.csv_output, args.tmx_output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
