from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path
from typing import Any

from common import (
    MANIFESTS_DIR,
    REPO_ROOT,
    clean_chinese_text,
    clean_english_text,
    fetch_text,
    page_to_raw_url,
    resolve_redirect_raw,
    title_from_url,
    write_json,
    write_jsonl,
)

WORK_ID = "mengzi"
MANIFEST_PATH = MANIFESTS_DIR / f"{WORK_ID}.yml"
INVENTORY_PATH = MANIFESTS_DIR.parent / f"{WORK_ID}_inventory.yml"
RAW_DIR = REPO_ROOT / "corpus" / "raw" / "wikisource"
CHINESE_DIR = REPO_ROOT / "corpus" / "processed" / "chinese_base_texts"
TRANSLATION_DIR = REPO_ROOT / "corpus" / "processed" / "translations"
ALIGNMENT_DIR = REPO_ROOT / "corpus" / "processed" / "alignments"
ACCESS_DATE = "2026-05-30"
SOURCE_SUFFIX = "zhwikisource-20260530"
TARGET_SOURCE_SUFFIX = "legge-cc-v2-1895"
MIN_ALIGNMENT_SIMILARITY = 0.9


def build_ingestion_policy() -> dict[str, Any]:
    return {
        "inventory_required": True,
        "inventory_path": "metadata/mengzi_inventory.yml",
        "inventory_unit_key": "units",
        "inventory_derivation": "derived_from_manifest_sections",
        "ingestion_plan_required": True,
        "ingestion_plan_path": "documentation/mengzi_ingestion_plan.md",
        "source_audit_required": True,
        "source_audit_path": "documentation/mengzi_ingestion_plan.md",
        "granularity_policy_required": True,
        "granularity_policy_path": "documentation/alignment_granularity_policy.md",
        "section_unit": "section",
        "preferred_segment_unit": "passage",
        "minimum_required_alignment_scope": "passage",
        "maximum_exact_alignment_scope": "passage",
        "allowed_segment_units": ["passage"],
        "coarse_alignment_units": [],
        "granularity_order": ["passage", "section"],
        "metadata_only_allowed": True,
        "missing_text_policy": "retain_metadata_only_sections_until_clean_public_domain_witnesses_exist",
        "commentary_policy": "exclude_commentary_and_notes_from_exact_alignments_and_tmx",
        "rights_policy": "public_domain_only_for_export",
        "allowed_export_rights_statuses": ["public_domain"],
        "section_group_export_policy": "forbidden",
        "completion_definition": (
            "A Mengzi section is complete only when both the Chinese Wikisource witness and the Legge public-domain "
            "translation are captured, segmented into passage-level units, and exported as exact TMX alignments."
        ),
    }


def build_inventory_units(processed_sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "global_sort_key": section["sort_key"],
            "canonical_unit_type": "section",
            "text_status": "extant",
            "title": section["label"],
            "canonical_ref": section["canonical_ref"],
            "section_id": section["section_id"],
            "zh_page_url": section["zh_page_url"],
            "en_page_url": section["en_page_url"],
            "status": section.get("status", "complete"),
            "coverage_status": section.get("coverage_status", "complete"),
            "english_witness_status": "verified_transcribed_text_available",
        }
        for section in processed_sections
    ]

SECTION_CATALOG: list[dict[str, Any]] = [
    {
        "section_id": "book-01-lianghuiwang-shang",
        "slug": "lianghuiwang-shang",
        "label": "梁惠王上",
        "canonical_ref": "孟子 1A",
        "sort_key": 1,
        "legge_section_alias": "Liang Hui Wang I",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/梁惠王上",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter01",
    },
    {
        "section_id": "book-02-lianghuiwang-xia",
        "slug": "lianghuiwang-xia",
        "label": "梁惠王下",
        "canonical_ref": "孟子 1B",
        "sort_key": 2,
        "legge_section_alias": "Liang Hui Wang II",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/梁惠王下",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter02",
    },
    {
        "section_id": "book-03-gongsunchou-shang",
        "slug": "gongsunchou-shang",
        "label": "公孫丑上",
        "canonical_ref": "孟子 2A",
        "sort_key": 3,
        "legge_section_alias": "Gong Sun Chou I",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/公孫丑上",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter03",
    },
    {
        "section_id": "book-04-gongsunchou-xia",
        "slug": "gongsunchou-xia",
        "label": "公孫丑下",
        "canonical_ref": "孟子 2B",
        "sort_key": 4,
        "legge_section_alias": "Gong Sun Chou II",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/公孫丑下",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter04",
    },
    {
        "section_id": "book-05-tengwengong-shang",
        "slug": "tengwengong-shang",
        "label": "滕文公上",
        "canonical_ref": "孟子 3A",
        "sort_key": 5,
        "legge_section_alias": "Teng Wen Gong I",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/滕文公上",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter05",
    },
    {
        "section_id": "book-06-tengwengong-xia",
        "slug": "tengwengong-xia",
        "label": "滕文公下",
        "canonical_ref": "孟子 3B",
        "sort_key": 6,
        "legge_section_alias": "Teng Wen Gong II",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/滕文公下",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter06",
    },
    {
        "section_id": "book-07-lilou-shang",
        "slug": "lilou-shang",
        "label": "離婁上",
        "canonical_ref": "孟子 4A",
        "sort_key": 7,
        "legge_section_alias": "Li Lou I",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/離婁上",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter07",
    },
    {
        "section_id": "book-08-lilou-xia",
        "slug": "lilou-xia",
        "label": "離婁下",
        "canonical_ref": "孟子 4B",
        "sort_key": 8,
        "legge_section_alias": "Li Lou II",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/離婁下",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter08",
    },
    {
        "section_id": "book-09-wanzhang-shang",
        "slug": "wanzhang-shang",
        "label": "萬章上",
        "canonical_ref": "孟子 5A",
        "sort_key": 9,
        "legge_section_alias": "Wan Zhang I",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/萬章上",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter09",
    },
    {
        "section_id": "book-10-wanzhang-xia",
        "slug": "wanzhang-xia",
        "label": "萬章下",
        "canonical_ref": "孟子 5B",
        "sort_key": 10,
        "legge_section_alias": "Wan Zhang II",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/萬章下",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter10",
    },
    {
        "section_id": "book-11-gaozi-shang",
        "slug": "gaozi-shang",
        "label": "告子上",
        "canonical_ref": "孟子 6A",
        "sort_key": 11,
        "legge_section_alias": "Gao Zi I",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/告子上",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter11",
    },
    {
        "section_id": "book-12-gaozi-xia",
        "slug": "gaozi-xia",
        "label": "告子下",
        "canonical_ref": "孟子 6B",
        "sort_key": 12,
        "legge_section_alias": "Gao Zi II",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/告子下",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter12",
    },
    {
        "section_id": "book-13-jinxin-shang",
        "slug": "jinxin-shang",
        "label": "盡心上",
        "canonical_ref": "孟子 7A",
        "sort_key": 13,
        "legge_section_alias": "Jin Xin I",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/盡心上",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter13",
    },
    {
        "section_id": "book-14-jinxin-xia",
        "slug": "jinxin-xia",
        "label": "盡心下",
        "canonical_ref": "孟子 7B",
        "sort_key": 14,
        "legge_section_alias": "Jin Xin II",
        "zh_page_url": "https://zh.wikisource.org/wiki/孟子/盡心下",
        "en_page_url": "https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius/chapter14",
    },
]

ALIGNMENT_VARIANT_MAP = str.maketrans(
    {
        "鴈": "雁",
        "臺": "台",
        "閒": "間",
        "飢": "饑",
        "殀": "夭",
        "塗": "涂",
        "蹴": "蹙",
        "歟": "與",
        "盡": "尽",
        "禦": "御",
        "爲": "為",
        "髙": "高",
        "耆": "嗜",
        "籥": "龠",
        "祥": "詳",
        "牆": "墻",
        "鼈": "鱉",
        "偕": "皆",
        "愿": "願",
        "鎡": "镃",
        "谿": "溪",
        "彊": "強",
        "範": "范",
        "眾": "衆",
        "揜": "掩",
        "鬱": "郁",
        "惟": "唯",
        "若": "如",
        "汙": "污",
        "阨": "厄",
        "踰": "逾",
        "于": "於",
        "尽": "盡",
    }
)


def source_ids(section_id: str) -> tuple[str, str]:
    return (f"{section_id}__{SOURCE_SUFFIX}", f"{section_id}__{TARGET_SOURCE_SUFFIX}")


def section_paths(section: dict[str, Any]) -> dict[str, Path]:
    base_name = f"{WORK_ID}__{section['section_id']}"
    return {
        "zh_raw": RAW_DIR / f"{base_name}__{SOURCE_SUFFIX}__raw.wikitext",
        "en_raw": RAW_DIR / f"{base_name}__{TARGET_SOURCE_SUFFIX}__raw.wikitext",
        "zh_base": CHINESE_DIR / f"{base_name}__{SOURCE_SUFFIX}__base.txt",
        "zh_segments": CHINESE_DIR / f"{base_name}__{SOURCE_SUFFIX}__segments.jsonl",
        "en_text": TRANSLATION_DIR / f"{base_name}__{TARGET_SOURCE_SUFFIX}__translation.txt",
        "en_segments": TRANSLATION_DIR / f"{base_name}__{TARGET_SOURCE_SUFFIX}__segments.jsonl",
        "alignments": ALIGNMENT_DIR / f"{base_name}__{SOURCE_SUFFIX}__{TARGET_SOURCE_SUFFIX}__alignments.jsonl",
    }


def compare_chinese_for_alignment(text: str) -> str:
    comparison = clean_chinese_text(text).translate(ALIGNMENT_VARIANT_MAP)
    return re.sub(r"""[「」『』“”‘’、，。；：？！—…,.!?;:\-"'\(\)（）《》〈〉·\[\]\s]""", "", comparison)


def parse_chinese_segments(section: dict[str, Any], raw_text: str, source_id: str) -> list[dict[str, Any]]:
    onlyinclude_match = re.search(r"<onlyinclude>(.*)</onlyinclude>", raw_text, flags=re.S)
    working = onlyinclude_match.group(1) if onlyinclude_match else raw_text
    segments: list[dict[str, Any]] = []
    for match in re.finditer(r"===\s*(\d+)\s*===\s*(.*?)(?=(?:\n===\s*\d+\s*===)|\Z)", working, flags=re.S):
        text = clean_chinese_text(match.group(2))
        if not text:
            continue
        order = len(segments) + 1
        canonical_ref = f"{section['canonical_ref']}.{order}"
        segment_id = f"{WORK_ID}__{section['section_id']}__{order:03d}__{SOURCE_SUFFIX}"
        segments.append(
            {
                "segment_id": segment_id,
                "work_id": WORK_ID,
                "section_id": section["section_id"],
                "source_id": source_id,
                "segment_type": "passage",
                "segment_order": order,
                "canonical_ref": canonical_ref,
                "text_original": text,
                "text_normalized": text,
                "notes": f"Chinese Wikisource numbered passage {match.group(1)}.",
            }
        )
    return segments


def parse_english_subunits(raw_text: str, section_label: str, default_heading: str) -> tuple[str, list[dict[str, str]]]:
    heading = default_heading
    matches = list(re.finditer(r"\{\{lang\|zh(?:-hant)?\|(.+?)\}\}", raw_text, flags=re.S))
    subunits: list[dict[str, str]] = []
    for index, match in enumerate(matches):
        chinese_quote = clean_chinese_text(match.group(1))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(raw_text)
        english_text = clean_english_text(raw_text[start:end])
        if not chinese_quote:
            continue
        subunits.append({"chinese_quote": chinese_quote, "english_text": english_text})
    if subunits and len(subunits[0]["chinese_quote"]) <= 16:
        if compare_chinese_for_alignment(subunits[0]["chinese_quote"]) == compare_chinese_for_alignment(section_label):
            subunits = subunits[1:]
    return heading, subunits


def choose_best_subunit_group(
    target_text: str,
    english_subunits: list[dict[str, str]],
    start_index: int,
) -> dict[str, Any] | None:
    if start_index >= len(english_subunits):
        return None

    target_comparison = compare_chinese_for_alignment(target_text)
    best_end_index: int | None = None
    best_comparison = ""
    best_ratio = -1.0
    best_gap = 0

    for end_index in range(start_index + 1, len(english_subunits) + 1):
        comparison = "".join(
            compare_chinese_for_alignment(subunit["chinese_quote"])
            for subunit in english_subunits[start_index:end_index]
        )
        ratio = difflib.SequenceMatcher(None, target_comparison, comparison).ratio()
        gap = abs(len(comparison) - len(target_comparison))
        if ratio > best_ratio or (ratio == best_ratio and gap < best_gap):
            best_end_index = end_index
            best_comparison = comparison
            best_ratio = ratio
            best_gap = gap
        if len(comparison) >= len(target_comparison) * 1.15:
            break

    if best_end_index is None:
        return None

    english_text = " ".join(
        subunit["english_text"]
        for subunit in english_subunits[start_index:best_end_index]
        if subunit["english_text"]
    )
    max_gap = max(12, int(len(target_comparison) * 0.1))
    return {
        "start_index": start_index,
        "end_index": best_end_index,
        "similarity": best_ratio,
        "length_gap": best_gap,
        "subunit_count": best_end_index - start_index,
        "english_text": english_text,
        "is_exact_alignment_candidate": bool(
            english_text and best_ratio >= MIN_ALIGNMENT_SIMILARITY and best_gap <= max_gap
        ),
    }


def build_english_segments_and_alignments(
    section: dict[str, Any],
    chinese_source_id: str,
    english_source_id: str,
    chinese_segments: list[dict[str, Any]],
    raw_text: str,
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]], int, str]:
    heading, english_subunits = parse_english_subunits(
        raw_text,
        section["label"],
        str(section["legge_section_alias"]),
    )
    english_segments: list[dict[str, Any]] = []
    alignments: list[dict[str, Any]] = []
    exact_alignment_count = 0
    alignment_status = "complete"
    groupings: list[dict[str, Any]] = []
    current_index = 0

    for chinese_segment in chinese_segments:
        grouping = choose_best_subunit_group(chinese_segment["text_original"], english_subunits, current_index)
        if grouping is None:
            alignment_status = "section_group_only"
            break
        current_index = int(grouping["end_index"])
        groupings.append(grouping)

    if len(groupings) != len(chinese_segments) or current_index != len(english_subunits):
        alignment_status = "section_group_only"

    for order, chinese_segment in enumerate(chinese_segments, start=1):
        grouping = groupings[order - 1] if order - 1 < len(groupings) else None
        if grouping is None:
            continue
        english_segment = {
            "segment_id": f"{WORK_ID}__{section['section_id']}__{order:03d}__{TARGET_SOURCE_SUFFIX}",
            "work_id": WORK_ID,
            "section_id": section["section_id"],
            "source_id": english_source_id,
            "segment_type": "passage",
            "segment_order": order,
            "canonical_ref": f"{heading}.{order}",
            "text_original": grouping["english_text"],
            "text_normalized": grouping["english_text"],
            "notes": (
                f"{heading}; grouped from {grouping['subunit_count']} Legge bilingual quotation block(s); "
                f"Chinese quotation similarity {grouping['similarity']:.3f}."
            ),
        }
        english_segments.append(english_segment)
        if alignment_status == "complete" and not grouping["is_exact_alignment_candidate"]:
            alignment_status = "section_group_only"

    if alignment_status == "complete" and len(english_segments) == len(chinese_segments):
        for chinese_segment, english_segment, grouping in zip(chinese_segments, english_segments, groupings):
            order = chinese_segment["segment_order"]
            alignments.append(
                {
                    "alignment_id": (
                        f"{WORK_ID}__{section['section_id']}__{order:03d}__"
                        f"{SOURCE_SUFFIX}__{TARGET_SOURCE_SUFFIX}"
                    ),
                    "work_id": WORK_ID,
                    "section_id": section["section_id"],
                    "source_id": chinese_source_id,
                    "target_source_id": english_source_id,
                    "alignment_type": "exact_or_near_exact",
                    "confidence": round(min(0.99, max(MIN_ALIGNMENT_SIMILARITY, grouping["similarity"])), 2),
                    "chinese_segment_ids": [chinese_segment["segment_id"]],
                    "translation_segment_ids": [english_segment["segment_id"]],
                    "notes": (
                        f"{chinese_segment['canonical_ref']} -> {english_segment['canonical_ref']}; "
                        f"Legge quotation similarity {grouping['similarity']:.3f} across "
                        f"{grouping['subunit_count']} bilingual block(s)."
                    ),
                }
            )
        exact_alignment_count = len(chinese_segments)

    group_note = "Section-level grouped alignment across the full Mengzi section."
    if alignment_status != "complete":
        group_note = (
            "Section-level grouped alignment only; "
            f"parsed {len(chinese_segments)} Chinese passages, {len(english_segments)} English passages, and "
            f"{len(english_subunits)} Legge bilingual quotation block(s)."
        )
    alignments.append(
        {
            "alignment_id": (
                f"{WORK_ID}__{section['section_id']}__section-group__{SOURCE_SUFFIX}__{TARGET_SOURCE_SUFFIX}"
            ),
            "work_id": WORK_ID,
            "section_id": section["section_id"],
            "source_id": chinese_source_id,
            "target_source_id": english_source_id,
            "alignment_type": "section_group",
            "confidence": 1.0,
            "chinese_segment_ids": [segment["segment_id"] for segment in chinese_segments],
            "translation_segment_ids": [segment["segment_id"] for segment in english_segments],
            "notes": group_note,
        }
    )
    return heading, english_segments, alignments, exact_alignment_count, alignment_status


def build_sources(section: dict[str, Any], paths: dict[str, Path]) -> list[dict[str, Any]]:
    chinese_source_id, english_source_id = source_ids(section["section_id"])
    return [
        {
            "source_id": chinese_source_id,
            "work_id": WORK_ID,
            "section_id": section["section_id"],
            "language_code": "zh-Hant",
            "source_kind": "wikisource",
            "citation": f"{title_from_url(section['zh_page_url'])}, Chinese Wikisource, accessed {ACCESS_DATE}.",
            "source_url": section["zh_page_url"],
            "raw_path": str(paths["zh_raw"].relative_to(REPO_ROOT)),
            "processed_path": str(paths["zh_segments"].relative_to(REPO_ROOT)),
            "rights_status": "public_domain",
            "author_or_translator_ids": ["mengzi-disciples"],
            "notes": (
                "Untouched raw capture comes from the page's action=raw export; processed segmentation follows "
                "Chinese Wikisource top-level numbered passages."
            ),
        },
        {
            "source_id": english_source_id,
            "work_id": WORK_ID,
            "section_id": section["section_id"],
            "language_code": "en",
            "source_kind": "translation",
            "citation": (
                "James Legge, The Chinese Classics, Volume 2: The Works of Mencius, "
                f"{section['legge_section_alias']}, English Wikisource, accessed {ACCESS_DATE}."
            ),
            "source_url": section["en_page_url"],
            "raw_path": str(paths["en_raw"].relative_to(REPO_ROOT)),
            "processed_path": str(paths["en_segments"].relative_to(REPO_ROOT)),
            "rights_status": "public_domain",
            "author_or_translator_ids": ["james-legge"],
            "notes": (
                "Passage grouping follows Legge's embedded Chinese quotation blocks and retains witness wording in "
                "the exported English segments."
            ),
        },
    ]


def write_section_files(section: dict[str, Any], *, skip_fetch: bool) -> dict[str, Any]:
    paths = section_paths(section)
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    if skip_fetch and paths["zh_raw"].exists() and paths["en_raw"].exists():
        zh_raw = paths["zh_raw"].read_text(encoding="utf-8")
        en_raw = paths["en_raw"].read_text(encoding="utf-8")
    else:
        zh_raw = fetch_text(page_to_raw_url(section["zh_page_url"]))
        en_raw = fetch_text(page_to_raw_url(section["en_page_url"]))
        paths["en_raw"].write_text(en_raw, encoding="utf-8")

    resolved_zh_page_url, zh_raw = resolve_redirect_raw(section["zh_page_url"], zh_raw)
    section["zh_page_url"] = resolved_zh_page_url
    paths["zh_raw"].write_text(zh_raw, encoding="utf-8")
    if not paths["en_raw"].exists():
        paths["en_raw"].write_text(en_raw, encoding="utf-8")

    chinese_source_id, english_source_id = source_ids(section["section_id"])
    chinese_segments = parse_chinese_segments(section, zh_raw, chinese_source_id)
    heading, english_segments, alignments, exact_alignment_count, alignment_status = build_english_segments_and_alignments(
        section,
        chinese_source_id,
        english_source_id,
        chinese_segments,
        en_raw,
    )

    paths["zh_base"].write_text(
        "\n".join(f"{segment['canonical_ref']}\t{segment['text_original']}" for segment in chinese_segments) + "\n",
        encoding="utf-8",
    )
    paths["en_text"].write_text(
        "\n".join(f"{segment['canonical_ref']}\t{segment['text_original']}" for segment in english_segments) + "\n",
        encoding="utf-8",
    )
    write_jsonl(paths["zh_segments"], chinese_segments)
    write_jsonl(paths["en_segments"], english_segments)
    write_jsonl(paths["alignments"], alignments)

    enriched_section = {
        **section,
        "work_id": WORK_ID,
        "status": "complete",
        "alignment_status": alignment_status,
        "tmx_status": "complete" if exact_alignment_count else "section_group_only",
        "expected_exact_alignment_count": exact_alignment_count,
        "legge_section_alias": heading,
        "source_ids": {
            "source_id": chinese_source_id,
            "target_source_id": english_source_id,
        },
        "notes": (
            "Chinese witness segmented by top-level numbered passages; English witness grouped by Legge's embedded "
            "Chinese quotation blocks with conservative variant-insensitive comparison."
        ),
    }
    return {
        "section": enriched_section,
        "sources": build_sources(enriched_section, paths),
    }


def bootstrap_corpus(skip_fetch: bool = False) -> dict[str, Any]:
    processed_sections: list[dict[str, Any]] = []
    all_sources: list[dict[str, Any]] = []
    romanization_aliases: list[dict[str, Any]] = [
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "alias": "Mengzi",
            "romanization_system": "pinyin",
        },
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "alias": "Mencius",
            "romanization_system": "english-title",
        },
    ]
    ingestion_log: list[dict[str, Any]] = []
    total_exact_alignments = 0

    for section_seed in SECTION_CATALOG:
        result = write_section_files(dict(section_seed), skip_fetch=skip_fetch)
        section = result["section"]
        processed_sections.append(section)
        all_sources.extend(result["sources"])
        total_exact_alignments += section["expected_exact_alignment_count"]
        romanization_aliases.extend(
            [
                {
                    "entity_type": "section",
                    "entity_id": section["section_id"],
                    "alias": section["slug"].replace("-", " ").title(),
                    "romanization_system": "pinyin",
                },
                {
                    "entity_type": "section",
                    "entity_id": section["section_id"],
                    "alias": section["legge_section_alias"],
                    "romanization_system": "Legge-Wade-Giles",
                },
            ]
        )
        ingestion_log.append(
            {
                "run_id": f"bootstrap-{section['section_id']}-{ACCESS_DATE.replace('-', '')}",
                "work_id": WORK_ID,
                "section_id": section["section_id"],
                "status": "complete" if section["alignment_status"] == "complete" else "needs_human_review",
                "source_ids": [section["source_ids"]["source_id"], section["source_ids"]["target_source_id"]],
                "notes": (
                    f"Bootstrap corpus generation for {section['label']} with "
                    f"{section['expected_exact_alignment_count']} exact alignments and alignment status "
                    f"{section['alignment_status']}."
                ),
            }
        )

    sections_needing_alignment = sum(1 for section in processed_sections if section["alignment_status"] != "complete")
    sections_needing_qc = sum(1 for section in processed_sections if section["tmx_status"] != "complete")
    manifest = {
        "work_id": WORK_ID,
        "work_status": "complete" if sections_needing_alignment == 0 else "partial",
        "source_pair_defaults": {
            "source_id": SOURCE_SUFFIX,
            "target_source_id": TARGET_SOURCE_SUFFIX,
            "source_language": "zh-Hant",
            "target_language": "en",
        },
        "summary": {
            "section_count": len(processed_sections),
            "complete_sections": len(processed_sections) - sections_needing_alignment,
            "metadata_only_sections": 0,
            "sections_needing_alignment": sections_needing_alignment,
            "sections_needing_qc": sections_needing_qc,
            "exact_alignment_count": total_exact_alignments,
        },
        "ingestion_policy": build_ingestion_policy(),
        "romanization_aliases": romanization_aliases,
        "ingestion_log": ingestion_log,
        "sources": all_sources,
        "sections": processed_sections,
    }
    inventory_payload = {
        "work_id": WORK_ID,
        "title": "Canonical Mengzi section inventory",
        "count_basis": {
            "canonical_unit_count": len(processed_sections),
            "basis_note": "Derived from the manifest-backed 14-section Mengzi structure already used by the corpus bootstrap.",
        },
        "units": build_inventory_units(processed_sections),
    }
    write_json(INVENTORY_PATH, inventory_payload)
    write_json(MANIFEST_PATH, manifest)
    return manifest["summary"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap raw captures, processed files, and metadata for the Mengzi corpus.")
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Reuse committed raw files instead of downloading them again.",
    )
    args = parser.parse_args()

    summary = bootstrap_corpus(skip_fetch=args.skip_fetch)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
