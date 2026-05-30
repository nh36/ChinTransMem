from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from common import (
    MANIFESTS_DIR,
    REPO_ROOT,
    clean_wikitext,
    fetch_text,
    page_to_raw_url,
    resolve_redirect_raw,
    title_from_url,
    write_json,
    write_jsonl,
)

WORK_ID = "shijing"
MANIFEST_PATH = MANIFESTS_DIR / f"{WORK_ID}.yml"
RAW_DIR = REPO_ROOT / "corpus" / "raw" / "wikisource"
CHINESE_DIR = REPO_ROOT / "corpus" / "processed" / "chinese_base_texts"
TRANSLATION_DIR = REPO_ROOT / "corpus" / "processed" / "translations"
ALIGNMENT_DIR = REPO_ROOT / "corpus" / "processed" / "alignments"
ACCESS_DATE = "2026-05-30"
SOURCE_SUFFIX = "zhwikisource-20260530"
TARGET_SOURCE_SUFFIX = "legge-sheking-1871"

SECTION_CATALOG: list[dict[str, Any]] = [
    {
        "section_id": "guofeng-zhounan-001-guanju",
        "slug": "guofeng-zhounan-001-guanju",
        "label": "關雎",
        "canonical_ref": "詩經·國風·周南·001",
        "sort_key": 1,
        "major_division": "國風",
        "subdivision": "周南",
        "poem_number": 1,
        "legge_section_alias": "Guan ju",
        "zh_page_url": "https://zh.wikisource.org/wiki/詩經/關雎",
        "en_page_url": "https://en.wikisource.org/wiki/Guan_ju",
    }
]


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


def extract_poem_markup(raw_text: str) -> str:
    onlyinclude_match = re.search(r"<onlyinclude>(.*)</onlyinclude>", raw_text, flags=re.S)
    working = onlyinclude_match.group(1) if onlyinclude_match else raw_text
    poem_match = re.search(r"<poem[^>]*>(.*?)</poem>", working, flags=re.S)
    if not poem_match:
        raise ValueError("Could not find <poem> block in raw page.")
    return poem_match.group(1)


def clean_poem_blocks(poem_markup: str) -> list[str]:
    blocks: list[list[str]] = []
    current_block: list[str] = []
    for raw_line in poem_markup.splitlines():
        line = raw_line.strip()
        if line.startswith(":"):
            line = line[1:].strip()
        cleaned = clean_wikitext(line).strip()
        if not cleaned:
            if current_block:
                blocks.append(current_block)
                current_block = []
            continue
        current_block.append(cleaned)
    if current_block:
        blocks.append(current_block)
    return ["\n".join(block) for block in blocks]


def poem_lines(blocks: list[str]) -> list[str]:
    return [line for block in blocks for line in block.splitlines() if line.strip()]


def chunk_lines(lines: list[str], chunk_size: int) -> list[str]:
    return ["\n".join(lines[index : index + chunk_size]) for index in range(0, len(lines), chunk_size)]


def extract_english_poem_blocks(raw_text: str) -> list[str]:
    poem_matches = re.findall(r"<poem[^>]*>(.*?)</poem>", raw_text, flags=re.S)
    for poem_markup in poem_matches:
        blocks = clean_poem_blocks(poem_markup)
        if blocks:
            return blocks
    raise ValueError("Could not find an English <poem> block with content.")


def build_segments_and_alignments(
    section: dict[str, Any],
    chinese_source_id: str,
    english_source_id: str,
    chinese_blocks: list[str],
    english_blocks: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int, str]:
    if len(chinese_blocks) == len(english_blocks):
        segment_type = "stanza"
        chinese_segments_text = chinese_blocks
        english_segments_text = english_blocks
        section_note = "Aligned stanza by stanza from matching Chinese and English poem blocks."
    elif len(english_blocks) > len(chinese_blocks):
        chinese_lines = poem_lines(chinese_blocks)
        if len(chinese_lines) % len(english_blocks) == 0 and len(chinese_lines) // len(english_blocks) == 2:
            segment_type = "stanza"
            chinese_segments_text = chunk_lines(chinese_lines, 2)
            english_segments_text = english_blocks
            section_note = (
                "Aligned at couplet-sized stanza level by splitting the Chinese poem into two-line units to match "
                "Legge's printed stanza blocks."
            )
        else:
            segment_type = "poem"
            chinese_segments_text = ["\n\n".join(chinese_blocks)]
            english_segments_text = ["\n\n".join(english_blocks)]
            section_note = (
                "Fell back to poem-level alignment because Chinese and English stanza counts did not match cleanly."
            )
    else:
        segment_type = "poem"
        chinese_segments_text = ["\n\n".join(chinese_blocks)]
        english_segments_text = ["\n\n".join(english_blocks)]
        section_note = (
            "Fell back to poem-level alignment because Chinese and English stanza counts did not match cleanly."
        )

    chinese_segments: list[dict[str, Any]] = []
    english_segments: list[dict[str, Any]] = []
    alignments: list[dict[str, Any]] = []

    for order, (zh_text, en_text) in enumerate(zip(chinese_segments_text, english_segments_text), start=1):
        chinese_segment_id = f"{WORK_ID}__{section['section_id']}__{order:03d}__{SOURCE_SUFFIX}"
        english_segment_id = f"{WORK_ID}__{section['section_id']}__{order:03d}__{TARGET_SOURCE_SUFFIX}"
        canonical_ref = f"{section['canonical_ref']}.{order}"
        chinese_segments.append(
            {
                "segment_id": chinese_segment_id,
                "work_id": WORK_ID,
                "section_id": section["section_id"],
                "source_id": chinese_source_id,
                "segment_type": segment_type,
                "segment_order": order,
                "canonical_ref": canonical_ref,
                "text_original": zh_text,
                "text_normalized": zh_text,
                "notes": f"{section['label']} Chinese {segment_type} {order}.",
            }
        )
        english_segments.append(
            {
                "segment_id": english_segment_id,
                "work_id": WORK_ID,
                "section_id": section["section_id"],
                "source_id": english_source_id,
                "segment_type": segment_type,
                "segment_order": order,
                "canonical_ref": f"{section['legge_section_alias']}.{order}",
                "text_original": en_text,
                "text_normalized": en_text,
                "notes": f"{section['legge_section_alias']} English {segment_type} {order}.",
            }
        )
        alignments.append(
            {
                "alignment_id": (
                    f"{WORK_ID}__{section['section_id']}__{order:03d}__{SOURCE_SUFFIX}__{TARGET_SOURCE_SUFFIX}"
                ),
                "work_id": WORK_ID,
                "section_id": section["section_id"],
                "source_id": chinese_source_id,
                "target_source_id": english_source_id,
                "alignment_type": "exact_or_near_exact",
                "confidence": 0.99,
                "chinese_segment_ids": [chinese_segment_id],
                "translation_segment_ids": [english_segment_id],
                "notes": f"{segment_type.title()}-level Shijing alignment for {section['label']} block {order}.",
            }
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
            "notes": section_note,
        }
    )
    return chinese_segments, english_segments, alignments, len(chinese_segments), segment_type


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
            "author_or_translator_ids": ["shijing-anthologists"],
            "notes": (
                "Untouched raw capture comes from the page's action=raw export; processed segmentation keeps the "
                "poem text separate from translation and, when needed, splits larger Chinese stanza blocks into "
                "two-line units to match the public-domain English witness."
            ),
        },
        {
            "source_id": english_source_id,
            "work_id": WORK_ID,
            "section_id": section["section_id"],
            "language_code": "en",
            "source_kind": "translation",
            "citation": f"James Legge, The She King, '{section['legge_section_alias']}', English Wikisource, accessed {ACCESS_DATE}.",
            "source_url": section["en_page_url"],
            "raw_path": str(paths["en_raw"].relative_to(REPO_ROOT)),
            "processed_path": str(paths["en_segments"].relative_to(REPO_ROOT)),
            "rights_status": "public_domain",
            "author_or_translator_ids": ["james-legge"],
            "notes": "Processed segmentation preserves the stanza blocks printed on Legge's standalone poem page.",
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

    resolved_zh_page_url, zh_raw = resolve_redirect_raw(section["zh_page_url"], zh_raw)
    section["zh_page_url"] = resolved_zh_page_url
    paths["zh_raw"].write_text(zh_raw, encoding="utf-8")
    paths["en_raw"].write_text(en_raw, encoding="utf-8")

    chinese_source_id, english_source_id = source_ids(section["section_id"])
    chinese_blocks = clean_poem_blocks(extract_poem_markup(zh_raw))
    english_blocks = extract_english_poem_blocks(en_raw)
    chinese_segments, english_segments, alignments, exact_alignment_count, segment_type = build_segments_and_alignments(
        section,
        chinese_source_id,
        english_source_id,
        chinese_blocks,
        english_blocks,
    )

    paths["zh_base"].write_text(
        "\n\n".join(segment["text_original"] for segment in chinese_segments) + "\n",
        encoding="utf-8",
    )
    paths["en_text"].write_text(
        "\n\n".join(segment["text_original"] for segment in english_segments) + "\n",
        encoding="utf-8",
    )
    write_jsonl(paths["zh_segments"], chinese_segments)
    write_jsonl(paths["en_segments"], english_segments)
    write_jsonl(paths["alignments"], alignments)

    enriched_section = {
        **section,
        "work_id": WORK_ID,
        "status": "complete",
        "alignment_status": "complete",
        "tmx_status": "complete",
        "segment_type": segment_type,
        "expected_exact_alignment_count": exact_alignment_count,
        "source_ids": {
            "source_id": chinese_source_id,
            "target_source_id": english_source_id,
        },
        "notes": (
            f"Shijing pilot poem aligned at {segment_type}-level while preserving 國風 / 周南 / poem hierarchy in metadata."
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
            "alias": "Shijing",
            "romanization_system": "pinyin",
        },
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "alias": "Shi Jing",
            "romanization_system": "pinyin",
        },
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "alias": "Classic of Poetry",
            "romanization_system": "english-title",
        },
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "alias": "Book of Poetry",
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
                    "alias": section["legge_section_alias"],
                    "romanization_system": "Legge-title",
                },
                {
                    "entity_type": "section",
                    "entity_id": section["section_id"],
                    "alias": "Guan Ju",
                    "romanization_system": "pinyin",
                },
            ]
        )
        ingestion_log.append(
            {
                "run_id": f"bootstrap-{section['section_id']}-{ACCESS_DATE.replace('-', '')}",
                "work_id": WORK_ID,
                "section_id": section["section_id"],
                "status": "complete",
                "source_ids": [section["source_ids"]["source_id"], section["source_ids"]["target_source_id"]],
                "notes": (
                    f"Bootstrap Shijing pilot generation for {section['label']} with "
                    f"{section['expected_exact_alignment_count']} exact {section['segment_type']} alignments."
                ),
            }
        )

    manifest = {
        "work_id": WORK_ID,
        "work_status": "partial",
        "source_pair_defaults": {
            "source_id": SOURCE_SUFFIX,
            "target_source_id": TARGET_SOURCE_SUFFIX,
            "source_language": "zh-Hant",
            "target_language": "en",
        },
        "summary": {
            "section_count": len(processed_sections),
            "complete_sections": len(processed_sections),
            "metadata_only_sections": 0,
            "sections_needing_alignment": 0,
            "sections_needing_qc": 0,
            "exact_alignment_count": total_exact_alignments,
        },
        "romanization_aliases": romanization_aliases,
        "ingestion_log": ingestion_log,
        "sources": all_sources,
        "sections": processed_sections,
    }
    write_json(MANIFEST_PATH, manifest)
    return manifest["summary"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap raw captures, processed files, and metadata for the Shijing corpus.")
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Reuse local raw captures instead of downloading them again.",
    )
    args = parser.parse_args()

    summary = bootstrap_corpus(skip_fetch=args.skip_fetch)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
