from __future__ import annotations

import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from common import (
    DEFAULT_DB_PATH,
    DEFAULT_SOURCE_LANGUAGE,
    DEFAULT_TARGET_LANGUAGE,
    DEFAULT_WORK_ID,
    corpus_export_paths,
    manifest_sections,
    section_export_paths,
    write_json,
)
from export_corpus import load_exact_alignment_rows

XML_NAMESPACE = "http://www.w3.org/XML/1998/namespace"


def validate_tmx_file(
    db_path: Path | str,
    tmx_path: Path | str,
    report_output: Path | str,
    section_id: str | None = None,
    *,
    work_id: str = DEFAULT_WORK_ID,
) -> dict[str, object]:
    export_rows = load_exact_alignment_rows(db_path, work_id, section_id)
    expected_rows = {str(row["alignment_id"]): row for row in export_rows}
    tree = ET.parse(tmx_path)
    root = tree.getroot()
    if root.tag != "tmx":
        raise ValueError(f"Expected TMX root element, found {root.tag}")

    header = root.find("header")
    body = root.find("body")
    if header is None or body is None:
        raise ValueError("TMX document must include both header and body elements")
    if header.attrib.get("srclang") != DEFAULT_SOURCE_LANGUAGE:
        raise ValueError(f"Unexpected srclang: {header.attrib.get('srclang')}")

    tus = body.findall("tu")
    actual_tuids: list[str] = []
    seen_tuids: set[str] = set()
    for tu in tus:
        tuid = tu.attrib.get("tuid")
        if not tuid:
            raise ValueError("TMX translation units must include a tuid")
        if tuid in seen_tuids:
            raise ValueError(f"Duplicate TMX tuid detected: {tuid}")
        if tuid not in expected_rows:
            raise ValueError(f"Unexpected TMX tuid detected: {tuid}")
        seen_tuids.add(tuid)
        actual_tuids.append(tuid)

        props = {prop.attrib.get("type"): (prop.text or "") for prop in tu.findall("prop")}
        for required_prop in (
            "x-work-id",
            "x-section-id",
            "x-section-unit",
            "x-segment-type",
            "x-alignment-granularity",
            "x-is-coarse-alignment",
            "x-alignment-type",
            "x-confidence",
            "x-chinese-ref",
            "x-translation-ref",
        ):
            if not props.get(required_prop):
                raise ValueError(f"TMX translation unit {tuid} is missing prop {required_prop}")

        tuv_by_lang = {tuv.attrib.get(f"{{{XML_NAMESPACE}}}lang"): tuv for tuv in tu.findall("tuv")}
        if set(tuv_by_lang) != {DEFAULT_SOURCE_LANGUAGE, DEFAULT_TARGET_LANGUAGE}:
            raise ValueError(f"TMX translation unit {tuid} has unexpected language set: {sorted(tuv_by_lang)}")

        expected_row = expected_rows[tuid]
        source_seg = tuv_by_lang[DEFAULT_SOURCE_LANGUAGE].findtext("seg", default="")
        target_seg = tuv_by_lang[DEFAULT_TARGET_LANGUAGE].findtext("seg", default="")
        if source_seg != expected_row["chinese_text"]:
            raise ValueError(f"TMX source segment mismatch for {tuid}")
        if target_seg != expected_row["translation_text"]:
            raise ValueError(f"TMX target segment mismatch for {tuid}")

    expected_tuids = [str(row["alignment_id"]) for row in export_rows]
    if actual_tuids != expected_tuids:
        raise ValueError("TMX translation units do not match the expected export order")

    report = {
        "status": "pass",
        "tmx_path": str(tmx_path),
        "work_id": work_id,
        "section_id": section_id,
        "tu_count": len(tus),
        "source_language": DEFAULT_SOURCE_LANGUAGE,
        "target_language": DEFAULT_TARGET_LANGUAGE,
    }
    write_json(report_output, report)
    return report


def validate_all_tmx_exports(
    db_path: Path | str = DEFAULT_DB_PATH,
    report_output: Path | str | None = None,
    *,
    work_id: str = DEFAULT_WORK_ID,
) -> dict[str, object]:
    corpus_paths = corpus_export_paths(work_id)
    if report_output is None:
        report_output = corpus_paths["tmx_validation"]
    section_reports: list[dict[str, object]] = []
    for section in manifest_sections(work_id):
        if section.get("tmx_status", "complete") != "complete":
            continue
        paths = section_export_paths(section["section_id"], work_id)
        section_reports.append(
            validate_tmx_file(
                db_path,
                paths["tmx"],
                paths["tmx_validation"],
                section["section_id"],
                work_id=work_id,
            )
        )

    corpus_report = validate_tmx_file(
        db_path,
        corpus_paths["tmx"],
        corpus_paths["tmx_validation"],
        None,
        work_id=work_id,
    )
    report = {
        "status": "pass",
        "work_id": work_id,
        "section_count": len(section_reports),
        "sections": section_reports,
        "corpus": corpus_report,
    }
    write_json(report_output, report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate TMX exports for a work against the SQLite corpus data.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file.")
    parser.add_argument("--work-id", default=DEFAULT_WORK_ID, help="Which work manifest to validate.")
    parser.add_argument(
        "--report-output",
        default=None,
        help="Where to write the overall TMX validation report.",
    )
    args = parser.parse_args()

    report = validate_all_tmx_exports(args.db, args.report_output, work_id=args.work_id)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
