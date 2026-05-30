from __future__ import annotations

import json
import re
import statistics
from pathlib import Path
from typing import Any

from common import DOCUMENTATION_DIR, QC_REPORTS_DIR, corpus_export_paths, load_work_manifest, read_jsonl

WORK_ID = "shijing"
QUALITY_JSON_PATH = QC_REPORTS_DIR / "shijing__completion_quality.json"
QUALITY_MARKDOWN_PATH = DOCUMENTATION_DIR / "shijing_completion_quality.md"
SPOTCHECK_PACKET_PATH = DOCUMENTATION_DIR / "shijing_spotcheck_packet.md"

ENGLISH_WORD_RE = re.compile(r"[A-Za-z]+(?:['’-][A-Za-z]+)?")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
QUALITY_MARKER_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("wikisource_css", re.compile(r"\.mw-parser-output|wst-anchor:target", re.I)),
    ("heading_marker", re.compile(r"\b(?:ODES OF|THE SHE KING|SHE KING|Ode \d+|St(?:anza)?\.?\s*\d+|Book \d+)\b", re.I)),
    ("page_furniture", re.compile(r"\b(?:PART\s+[IVXLC]+|Page\s+\d+|Vol\.?\s+[IVXLC]+)\b", re.I)),
    ("footnote_marker", re.compile(r"\b(?:note|notes)\b|\[\d+\]|\(\d+\)")),
    ("bracketed_editorial_note", re.compile(r"\[[^\]]+\]")),
    ("commentary_marker", re.compile(r"\b(?:commentary|preface|appendix|Mao|Ying-ta|Choo He|Zhu Xi)\b", re.I)),
    ("ocr_noise", re.compile(r"[〇^]|T4ANG|SI1AOU|PAIIT|thcde|tliere|K!ang|mu\.'-t|wiih|Tliere", re.I)),
)


def shijing_witness_metadata(english_witness: str | None) -> dict[str, Any]:
    if english_witness == "standalone_sheking":
        return {
            "english_witness_type": "standalone_wikisource",
            "english_witness_status": "verified_transcribed_text",
            "source_witness_type": "standalone Wikisource",
            "needs_human_text_review": False,
            "ocr_or_fulltext_derived": False,
        }
    if english_witness == "sbe_shih":
        return {
            "english_witness_type": "sbe_transcluded_page",
            "english_witness_status": "verified_transcribed_text",
            "source_witness_type": "SBE transcluded page",
            "needs_human_text_review": False,
            "ocr_or_fulltext_derived": False,
        }
    if english_witness == "legge_hocr":
        return {
            "english_witness_type": "fulltext_ocr_derived_witness",
            "english_witness_status": "ocr_extracted_needs_review",
            "source_witness_type": "full-text/OCR-derived witness",
            "needs_human_text_review": True,
            "ocr_or_fulltext_derived": True,
        }
    if english_witness == "legge_ocr_reviewed":
        return {
            "english_witness_type": "fulltext_ocr_derived_witness",
            "english_witness_status": "ocr_verified",
            "source_witness_type": "full-text/OCR-derived witness",
            "needs_human_text_review": False,
            "ocr_or_fulltext_derived": True,
        }
    return {
        "english_witness_type": "not_applicable",
        "english_witness_status": "not_applicable",
        "source_witness_type": "not_applicable",
        "needs_human_text_review": False,
        "ocr_or_fulltext_derived": False,
    }


def split_text_blocks(text: str) -> list[str]:
    return [block.strip() for block in re.split(r"\n\s*\n", text.strip()) if block.strip()]


def english_word_count(text: str) -> int:
    return len(ENGLISH_WORD_RE.findall(text))


def chinese_character_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def english_character_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = int(round((len(ordered) - 1) * q))
    return ordered[index]


def detect_quality_markers(text: str, *, title: str | None = None) -> list[str]:
    markers = [name for name, pattern in QUALITY_MARKER_PATTERNS if pattern.search(text)]
    if CJK_RE.search(text):
        markers.append("embedded_chinese")
    if title and title in text:
        markers.append("untranslated_chinese_title")
    return sorted(set(markers))


def source_urls_for_section(section: dict[str, Any], source_map: dict[str, dict[str, Any]]) -> list[str]:
    urls: list[str] = []
    for key in ("zh_page_url", "en_page_url", "candidate_en_page_url", "candidate_en_text_url", "candidate_en_ocr_url"):
        value = section.get(key)
        if value and value not in urls:
            urls.append(value)
    source_ids = section.get("source_ids") or {}
    for key in ("source_id", "target_source_id"):
        source = source_map.get(str(source_ids.get(key)))
        if not source:
            continue
        source_url = source.get("source_url")
        if source_url and source_url not in urls:
            urls.append(source_url)
    return urls


def build_shijing_quality_context(
    manifest: dict[str, Any] | None = None,
    export_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    manifest = manifest or load_work_manifest(WORK_ID)
    export_rows = export_rows if export_rows is not None else read_jsonl(corpus_export_paths(WORK_ID)["jsonl"])
    export_rows_by_section: dict[str, list[dict[str, Any]]] = {}
    for row in export_rows:
        export_rows_by_section.setdefault(row["section_id"], []).append(row)
    for rows in export_rows_by_section.values():
        rows.sort(key=lambda row: row.get("order", 0))

    source_map = {source["source_id"]: source for source in manifest.get("sources", [])}
    complete_sections = [section for section in manifest["sections"] if section.get("tmx_status") == "complete"]
    metadata_only_sections = [section for section in manifest["sections"] if section.get("tmx_status") != "complete"]

    section_records: list[dict[str, Any]] = []
    hard_failures: list[str] = []
    row_warning_records: list[dict[str, Any]] = []

    for row in export_rows:
        markers = detect_quality_markers(row["translation_text"])
        if markers:
            row_warning_records.append(
                {
                    "alignment_id": row["alignment_id"],
                    "section_id": row["section_id"],
                    "order": row["order"],
                    "markers": markers,
                    "alignment_granularity": row["alignment_granularity"],
                    "is_coarse_alignment": bool(row.get("is_coarse_alignment")),
                }
            )

    for section in complete_sections:
        section_id = section["section_id"]
        rows = export_rows_by_section.get(section_id, [])
        source_meta = shijing_witness_metadata(section.get("english_witness"))
        source_urls = source_urls_for_section(section, source_map)
        if not rows:
            hard_failures.append(f"{section_id}: complete section has no exact export rows.")
            continue
        if not source_urls:
            hard_failures.append(f"{section_id}: complete section has no source URLs.")
        if source_meta["source_witness_type"] == "not_applicable":
            hard_failures.append(f"{section_id}: complete section has no classified English witness.")

        chinese_text = "\n\n".join(row["chinese_text"] for row in rows)
        english_text = "\n\n".join(row["translation_text"] for row in rows)
        chinese_blocks = split_text_blocks(chinese_text)
        english_blocks = split_text_blocks(english_text)
        markers = detect_quality_markers(english_text, title=section["label"])
        has_coarse = any(bool(row.get("is_coarse_alignment")) for row in rows)
        granularity_values = sorted({row["alignment_granularity"] for row in rows})
        english_status = str(section.get("english_witness_status") or source_meta["english_witness_status"])
        needs_review = bool(section.get("needs_human_text_review", source_meta["needs_human_text_review"]))
        section_records.append(
            {
                "section_id": section_id,
                "title": section["label"],
                "canonical_ref": section["canonical_ref"],
                "major_division": section["major_division"],
                "subdivision": section["subdivision"],
                "source_witness_type": section.get("source_witness_type", source_meta["source_witness_type"]),
                "english_witness_type": section.get("english_witness_type", source_meta["english_witness_type"]),
                "english_witness_status": english_status,
                "needs_human_text_review": needs_review,
                "ocr_or_fulltext_derived": bool(section.get("ocr_or_fulltext_derived", source_meta["ocr_or_fulltext_derived"])),
                "exact_alignment_count": len(rows),
                "alignment_granularity_values": granularity_values,
                "has_coarse_alignment": has_coarse,
                "is_single_poem_alignment": len(rows) == 1 and granularity_values == ["poem"],
                "chinese_character_count": chinese_character_count(chinese_text),
                "english_character_count": english_character_count(english_text),
                "english_word_count": english_word_count(english_text),
                "chinese_stanza_count": len(chinese_blocks),
                "english_stanza_block_count": len(english_blocks),
                "english_to_chinese_length_ratio": (
                    english_character_count(english_text) / max(chinese_character_count(chinese_text), 1)
                ),
                "possible_commentary_leakage_markers": markers,
                "contains_chinese_in_english_segment": any(marker == "embedded_chinese" for marker in markers),
                "contains_untranslated_chinese_title": any(marker == "untranslated_chinese_title" for marker in markers),
                "complete_but_needs_human_text_review": section.get("status") == "complete" and needs_review,
                "notes": section.get("notes"),
                "source_urls": source_urls,
                "_chinese_text": chinese_text,
                "_english_text": english_text,
                "_rows": rows,
            }
        )

    word_counts = [section["english_word_count"] for section in section_records]
    ratios = [section["english_to_chinese_length_ratio"] for section in section_records]
    word_short_threshold = max(12, int(percentile(word_counts, 0.05)))
    word_long_threshold = max(int(percentile(word_counts, 0.95)), int(statistics.median(word_counts) * 2.0))
    ratio_low_threshold = max(0.75, percentile(ratios, 0.05))
    ratio_high_threshold = max(8.0, percentile(ratios, 0.95))

    warning_count = 0
    for section in section_records:
        short_english = section["english_word_count"] <= word_short_threshold or section["english_character_count"] <= 20
        long_english = section["english_word_count"] >= word_long_threshold
        ratio_low = section["english_to_chinese_length_ratio"] < ratio_low_threshold
        ratio_high = section["english_to_chinese_length_ratio"] > ratio_high_threshold
        possible_stanza_split = (
            section["is_single_poem_alignment"]
            and section["chinese_stanza_count"] > 1
            and section["english_stanza_block_count"] > 1
        )
        warnings: list[str] = []
        if short_english:
            warnings.append("suspiciously short English text")
        if long_english:
            warnings.append("suspiciously long English text")
        if ratio_low:
            warnings.append("suspiciously low English/Chinese length ratio")
        if ratio_high:
            warnings.append("suspiciously high English/Chinese length ratio")
        if section["possible_commentary_leakage_markers"]:
            warnings.append("possible commentary, page furniture, or OCR junk")
        if section["contains_chinese_in_english_segment"] or section["contains_untranslated_chinese_title"]:
            warnings.append("Chinese text appears inside the English segment")
        if section["complete_but_needs_human_text_review"]:
            warnings.append("complete section still needs human text review")
        if possible_stanza_split:
            warnings.append("poem-level alignment may hide recoverable stanza segmentation")
        section["suspiciously_short_english_text"] = short_english
        section["suspiciously_long_english_text"] = long_english
        section["suspiciously_extreme_length_ratio"] = ratio_low or ratio_high
        section["possible_stanza_split"] = possible_stanza_split
        section["warnings"] = warnings
        warning_count += len(warnings)

    witness_counts: dict[str, int] = {}
    witness_status_counts: dict[str, int] = {}
    for section in section_records:
        witness_counts[section["source_witness_type"]] = witness_counts.get(section["source_witness_type"], 0) + 1
        witness_status_counts[section["english_witness_status"]] = witness_status_counts.get(
            section["english_witness_status"], 0
        ) + 1

    return {
        "work_id": WORK_ID,
        "summary": {
            "complete_sections": len(section_records),
            "metadata_only_sections": len(metadata_only_sections),
            "exact_alignment_count": len(export_rows),
            "complete_sections_by_witness_type": witness_counts,
            "complete_sections_by_witness_status": witness_status_counts,
            "ocr_or_fulltext_derived_sections": sum(1 for section in section_records if section["ocr_or_fulltext_derived"]),
            "sections_needing_human_text_review": sum(
                1 for section in section_records if section["complete_but_needs_human_text_review"]
            ),
            "sections_with_coarse_alignment": sum(1 for section in section_records if section["has_coarse_alignment"]),
            "sections_with_single_poem_alignment": sum(
                1 for section in section_records if section["is_single_poem_alignment"]
            ),
            "sections_with_extreme_length_ratio": sum(
                1 for section in section_records if section["suspiciously_extreme_length_ratio"]
            ),
            "sections_with_possible_commentary_leakage": sum(
                1 for section in section_records if section["possible_commentary_leakage_markers"]
            ),
            "hard_failure_count": len(hard_failures),
            "warning_count": warning_count,
        },
        "thresholds": {
            "english_word_short_threshold": word_short_threshold,
            "english_word_long_threshold": word_long_threshold,
            "english_to_chinese_ratio_low_threshold": ratio_low_threshold,
            "english_to_chinese_ratio_high_threshold": ratio_high_threshold,
        },
        "hard_failures": hard_failures,
        "row_warnings": row_warning_records,
        "sections": section_records,
        "metadata_only_sections": [
            {
                "section_id": section["section_id"],
                "title": section["label"],
                "canonical_ref": section["canonical_ref"],
                "notes": section.get("notes"),
                "source_urls": source_urls_for_section(section, source_map),
            }
            for section in metadata_only_sections
        ],
    }


def serializable_quality_report(context: dict[str, Any]) -> dict[str, Any]:
    sections = []
    for section in context["sections"]:
        sections.append(
            {
                key: value
                for key, value in section.items()
                if key not in {"_chinese_text", "_english_text", "_rows"}
            }
        )
    return {
        "work_id": context["work_id"],
        "summary": context["summary"],
        "thresholds": context["thresholds"],
        "hard_failure_count": context["summary"]["hard_failure_count"],
        "warning_count": context["summary"]["warning_count"],
        "hard_failures": context["hard_failures"],
        "row_warnings": context["row_warnings"],
        "metadata_only_sections": context["metadata_only_sections"],
        "sections": sections,
    }


def quality_markdown(context: dict[str, Any]) -> str:
    summary = context["summary"]
    sections = context["sections"]
    worst_ratio_sections = sorted(
        sections,
        key=lambda section: max(
            section["english_to_chinese_length_ratio"],
            1 / max(section["english_to_chinese_length_ratio"], 1e-9),
        ),
        reverse=True,
    )[:10]
    most_flagged_sections = sorted(sections, key=lambda section: len(section["warnings"]), reverse=True)[:15]

    lines = [
        "# Shijing completion quality audit",
        "",
        "This report complements the structural preflight checks with plausibility and review signals for the 305 complete extant *Shijing* poems.",
        "",
        "## Summary",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| complete_sections | {summary['complete_sections']} |",
        f"| metadata_only_sections | {summary['metadata_only_sections']} |",
        f"| exact_alignment_count | {summary['exact_alignment_count']} |",
        f"| ocr_or_fulltext_derived_sections | {summary['ocr_or_fulltext_derived_sections']} |",
        f"| sections_needing_human_text_review | {summary['sections_needing_human_text_review']} |",
        f"| sections_with_coarse_alignment | {summary['sections_with_coarse_alignment']} |",
        f"| sections_with_single_poem_alignment | {summary['sections_with_single_poem_alignment']} |",
        f"| sections_with_extreme_length_ratio | {summary['sections_with_extreme_length_ratio']} |",
        f"| sections_with_possible_commentary_leakage | {summary['sections_with_possible_commentary_leakage']} |",
        f"| hard_failure_count | {summary['hard_failure_count']} |",
        f"| warning_count | {summary['warning_count']} |",
        "",
        "## Witness mix",
        "",
        "| Witness type | Complete sections |",
        "| --- | ---: |",
    ]
    for witness_type, count in sorted(summary["complete_sections_by_witness_type"].items()):
        lines.append(f"| {witness_type} | {count} |")
    lines.extend(
        [
            "",
            "## Text-review status mix",
            "",
            "| Status | Complete sections |",
            "| --- | ---: |",
        ]
    )
    for status, count in sorted(summary["complete_sections_by_witness_status"].items()):
        lines.append(f"| {status} | {count} |")

    lines.extend(
        [
            "",
            "## Thresholds",
            "",
            "| Heuristic | Value |",
            "| --- | ---: |",
            f"| english_word_short_threshold | {context['thresholds']['english_word_short_threshold']} |",
            f"| english_word_long_threshold | {context['thresholds']['english_word_long_threshold']} |",
            f"| english_to_chinese_ratio_low_threshold | {context['thresholds']['english_to_chinese_ratio_low_threshold']:.3f} |",
            f"| english_to_chinese_ratio_high_threshold | {context['thresholds']['english_to_chinese_ratio_high_threshold']:.3f} |",
            "",
            "## Most flagged sections",
            "",
            "| Section | Title | Witness | Words | Ratio | Flags |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for section in most_flagged_sections:
        lines.append(
            "| {section_id} | {title} | {witness} | {words} | {ratio:.3f} | {flags} |".format(
                section_id=section["section_id"],
                title=section["title"],
                witness=section["source_witness_type"],
                words=section["english_word_count"],
                ratio=section["english_to_chinese_length_ratio"],
                flags=", ".join(section["warnings"]) or "—",
            )
        )

    lines.extend(
        [
            "",
            "## Extreme English/Chinese ratios",
            "",
            "| Section | Title | Ratio | Witness | Notes |",
            "| --- | --- | ---: | --- | --- |",
        ]
    )
    for section in worst_ratio_sections:
        lines.append(
            "| {section_id} | {title} | {ratio:.3f} | {witness} | {notes} |".format(
                section_id=section["section_id"],
                title=section["title"],
                ratio=section["english_to_chinese_length_ratio"],
                witness=section["source_witness_type"],
                notes="; ".join(section["warnings"]) or "—",
            )
        )

    if context["hard_failures"]:
        lines.extend(["", "## Hard failures", ""])
        for failure in context["hard_failures"]:
            lines.append(f"- {failure}")
    else:
        lines.extend(["", "## Hard failures", "", "- None."])

    return "\n".join(lines) + "\n"


def _section_packet_entry(section: dict[str, Any], category: str) -> dict[str, Any]:
    return {
        "entry_key": f"section:{section['section_id']}",
        "entry_type": "section",
        "category": category,
        "section_id": section["section_id"],
        "title": section["title"],
        "canonical_ref": section["canonical_ref"],
        "alignment_granularity": ", ".join(section["alignment_granularity_values"]),
        "is_coarse_alignment": section["has_coarse_alignment"],
        "notes": "; ".join(section["warnings"]) or (section.get("notes") or "—"),
        "chinese_text": section["_chinese_text"],
        "english_text": section["_english_text"],
        "source_urls": section["source_urls"],
    }


def _alignment_packet_entry(
    row: dict[str, Any],
    section_map: dict[str, dict[str, Any]],
    *,
    category: str,
) -> dict[str, Any]:
    section = section_map[row["section_id"]]
    return {
        "entry_key": f"alignment:{row['alignment_id']}",
        "entry_type": "alignment",
        "category": category,
        "section_id": row["section_id"],
        "title": section["title"],
        "canonical_ref": section["canonical_ref"],
        "alignment_granularity": row["alignment_granularity"],
        "is_coarse_alignment": bool(row.get("is_coarse_alignment")),
        "notes": section.get("notes") or "—",
        "chinese_text": row["chinese_text"],
        "english_text": row["translation_text"],
        "source_urls": section["source_urls"],
    }


def build_spotcheck_packet_markdown(context: dict[str, Any]) -> str:
    section_map = {section["section_id"]: section for section in context["sections"]}
    metadata_only_map = {section["section_id"]: section for section in context["metadata_only_sections"]}
    export_rows = [row for section in context["sections"] for row in section["_rows"]]
    section_items: dict[str, dict[str, Any]] = {}
    categories: dict[str, list[str]] = {}

    def add_item(item: dict[str, Any]) -> None:
        key = item["entry_key"]
        categories.setdefault(item["category"], [])
        if key not in section_items:
            section_items[key] = {**item, "categories": [item["category"]]}
        elif item["category"] not in section_items[key]["categories"]:
            section_items[key]["categories"].append(item["category"])
        if key not in categories[item["category"]]:
            categories[item["category"]].append(key)

    for section in sorted(
        (section for section in context["sections"] if section["subdivision"] == "周南"),
        key=lambda section: section["canonical_ref"],
    ):
        add_item(_section_packet_entry(section, "All Zhou Nan poems"))

    for section_id in sorted(metadata_only_map):
        section = metadata_only_map[section_id]
        add_item(
            {
                "entry_key": f"metadata:{section_id}",
                "entry_type": "metadata_only",
                "category": "All title-only lost-text metadata entries",
                "section_id": section["section_id"],
                "title": section["title"],
                "canonical_ref": section["canonical_ref"],
                "alignment_granularity": "metadata_only",
                "is_coarse_alignment": False,
                "notes": section.get("notes") or "Non-exportable metadata-only title.",
                "chinese_text": "_No extant Chinese poem text; title-only canonical entry._",
                "english_text": "_No exportable English text; entry remains metadata-only._",
                "source_urls": section["source_urls"],
                "categories": [],
            }
        )

    shortest_rows = sorted(export_rows, key=lambda row: english_word_count(row["translation_text"]))[:10]
    longest_rows = sorted(export_rows, key=lambda row: english_word_count(row["translation_text"]), reverse=True)[:10]
    for row in shortest_rows:
        add_item(_alignment_packet_entry(row, section_map, category="Ten shortest exported English segments"))
    for row in longest_rows:
        add_item(_alignment_packet_entry(row, section_map, category="Ten longest exported English segments"))

    for section in sorted(
        (
            section
            for section in context["sections"]
            if section["has_coarse_alignment"] or "poem" in section["alignment_granularity_values"]
        ),
        key=lambda section: section["canonical_ref"],
    ):
        add_item(_section_packet_entry(section, "All poem-level/coarse alignments"))

    seen_subdivisions: set[tuple[str, str]] = set()
    for section in sorted(context["sections"], key=lambda section: section["canonical_ref"]):
        key = (section["major_division"], section["subdivision"])
        if key in seen_subdivisions:
            continue
        seen_subdivisions.add(key)
        add_item(_section_packet_entry(section, f"Subdivision example: {section['major_division']} / {section['subdivision']}"))

    for section in sorted(
        (section for section in context["sections"] if section["suspiciously_extreme_length_ratio"]),
        key=lambda section: section["english_to_chinese_length_ratio"],
    ):
        add_item(_section_packet_entry(section, "Sections with extreme English/Chinese length ratios"))

    ordered_items = sorted(
        section_items.values(),
        key=lambda item: (
            item["entry_type"] != "metadata_only",
            item["section_id"],
            item["alignment_granularity"],
            item["entry_key"],
        ),
    )
    lines = [
        "# Shijing spot-check packet",
        "",
        "This packet is a human-review sample built from the completed Shijing corpus without manually correcting any passage text.",
        "",
        "## Category coverage",
        "",
        "| Category | Entries |",
        "| --- | ---: |",
    ]
    for category, keys in sorted(categories.items()):
        lines.append(f"| {category} | {len(keys)} |")

    lines.extend(["", "## Detailed entries", ""])
    for item in ordered_items:
        lines.extend(
            [
                f"### {item['section_id']} — {item['title']}",
                "",
                f"- Categories: {', '.join(sorted(item['categories']))}",
                f"- section_id: `{item['section_id']}`",
                f"- canonical_ref: `{item['canonical_ref']}`",
                f"- alignment_granularity: `{item['alignment_granularity']}`",
                f"- is_coarse_alignment: `{str(item['is_coarse_alignment']).lower()}`",
                f"- notes: {item['notes']}",
                "- source URLs:",
            ]
        )
        if item["source_urls"]:
            for url in item["source_urls"]:
                lines.append(f"  - {url}")
        else:
            lines.append("  - _No source URL recorded._")
        lines.extend(
            [
                "",
                "#### Chinese text",
                "",
                "```text",
                item["chinese_text"],
                "```",
                "",
                "#### English text",
                "",
                "```text",
                item["english_text"],
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def write_shijing_quality_outputs(
    context: dict[str, Any],
    *,
    json_output_path: Path = QUALITY_JSON_PATH,
    markdown_output_path: Path = QUALITY_MARKDOWN_PATH,
    spotcheck_output_path: Path = SPOTCHECK_PACKET_PATH,
) -> dict[str, Any]:
    report = serializable_quality_report(context)
    json_output_path.parent.mkdir(parents=True, exist_ok=True)
    json_output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_output_path.write_text(quality_markdown(context), encoding="utf-8")
    spotcheck_output_path.parent.mkdir(parents=True, exist_ok=True)
    spotcheck_output_path.write_text(build_spotcheck_packet_markdown(context), encoding="utf-8")
    return report
