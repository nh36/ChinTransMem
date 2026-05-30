from __future__ import annotations

import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from common import REPO_ROOT, load_json_compatible_yaml, write_json, write_jsonl

MANIFEST_PATH = REPO_ROOT / "metadata" / "corpus_manifest.yml"
WORKS_PATH = REPO_ROOT / "metadata" / "works.yml"
SECTIONS_PATH = REPO_ROOT / "metadata" / "sections.yml"
PERSONS_PATH = REPO_ROOT / "metadata" / "persons.yml"
SOURCES_PATH = REPO_ROOT / "metadata" / "sources.yml"
RIGHTS_PATH = REPO_ROOT / "metadata" / "rights.yml"
ALIASES_PATH = REPO_ROOT / "metadata" / "romanization_aliases.yml"
INGESTION_LOG_PATH = REPO_ROOT / "metadata" / "ingestion_log.yml"
RAW_DIR = REPO_ROOT / "corpus" / "raw" / "wikisource"
CHINESE_DIR = REPO_ROOT / "corpus" / "processed" / "chinese_base_texts"
TRANSLATION_DIR = REPO_ROOT / "corpus" / "processed" / "translations"
ALIGNMENT_DIR = REPO_ROOT / "corpus" / "processed" / "alignments"
ACCESS_DATE = "2026-05-29"


def page_to_raw_url(page_url: str) -> str:
    parsed = urllib.parse.urlparse(page_url)
    title = urllib.parse.unquote(parsed.path.removeprefix("/wiki/"))
    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            "/w/index.php",
            "",
            urllib.parse.urlencode({"title": title, "action": "raw"}),
            "",
        )
    )


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "ChinTransMem bootstrap"})
    with urllib.request.urlopen(request) as response:
        return response.read().decode("utf-8")


def split_template_args(body: str) -> list[str]:
    args: list[str] = []
    current: list[str] = []
    braces = 0
    brackets = 0
    i = 0
    while i < len(body):
        if body[i : i + 2] == "{{":
            braces += 1
            current.append("{{")
            i += 2
            continue
        if body[i : i + 2] == "}}" and braces > 0:
            braces -= 1
            current.append("}}")
            i += 2
            continue
        if body[i : i + 2] == "[[":
            brackets += 1
            current.append("[[")
            i += 2
            continue
        if body[i : i + 2] == "]]" and brackets > 0:
            brackets -= 1
            current.append("]]")
            i += 2
            continue
        if body[i] == "|" and braces == 0 and brackets == 0:
            args.append("".join(current))
            current = []
            i += 1
            continue
        current.append(body[i])
        i += 1
    args.append("".join(current))
    return args


def replace_template(body: str) -> str:
    parts = split_template_args(body)
    name = parts[0].strip().lower()
    args = [part.strip() for part in parts[1:]]
    if name.startswith("另") or name in {"補字", "僞字", "僞字？"}:
        return args[0] if args else ""
    if name in {"small", "smaller", "sc", "lang", "nowrap", "center", "right", "left"}:
        return args[-1] if args else ""
    if name == "ruby":
        return args[0] if args else ""
    if name.startswith("*") or name in {"·", "-"}:
        return "".join(args)
    if name in {"efn", "note", "refn", "sfn"}:
        return ""
    return args[-1] if args else ""


def expand_templates(text: str) -> str:
    pattern = re.compile(r"\{\{([^{}]*)\}\}")
    while True:
        updated = pattern.sub(lambda match: replace_template(match.group(1)), text)
        if updated == text:
            return text
        text = updated


def normalize_variant_markup(text: str) -> str:
    def variant_choice(match: re.Match[str]) -> str:
        body = match.group(1)
        if ";" in body:
            options = [item.strip() for item in body.split(";") if item.strip()]
            for option in options:
                if ":" in option and "hant" in option.lower():
                    return option.split(":", 1)[1].strip()
            first = options[0]
            return first.split(":", 1)[1].strip() if ":" in first else first
        return body

    return re.sub(r"-\{([^{}]+)\}-", variant_choice, text)


def clean_wikitext(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    text = normalize_variant_markup(text)
    text = expand_templates(text)
    text = re.sub(r"\[\[(?:[^|\]]+\|)?([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[https?://[^\s\]]+\s+([^\]]+)\]", r"\1", text)
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("'''", "").replace("''", "")
    text = html.unescape(text)
    text = text.replace("\u3000", " ").replace("&nbsp;", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def clean_chinese_text(text: str) -> str:
    cleaned = clean_wikitext(text)
    cleaned = cleaned.replace("\n", "")
    cleaned = re.sub(r"\s+", "", cleaned)
    return cleaned.strip(" ")


def clean_english_text(text: str) -> str:
    cleaned = clean_wikitext(text)
    paragraphs = [paragraph.strip() for paragraph in cleaned.split("\n") if paragraph.strip()]
    normalized_paragraphs = [re.sub(r"^\d+\.\s*", "", paragraph) for paragraph in paragraphs]
    return re.sub(r"\s+", " ", " ".join(normalized_paragraphs)).strip()


def title_from_url(page_url: str) -> str:
    return urllib.parse.unquote(urllib.parse.urlparse(page_url).path.removeprefix("/wiki/"))


def page_url_from_title(example_page_url: str, title: str) -> str:
    parsed = urllib.parse.urlparse(example_page_url)
    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            f"/wiki/{urllib.parse.quote(title, safe='/')}",
            "",
            "",
            "",
        )
    )


def redirect_target_title(raw_text: str) -> str | None:
    match = re.match(r"#(?:重定向|redirect)\s*\[\[([^|\]#]+)", raw_text.strip(), flags=re.I)
    if not match:
        return None
    return match.group(1).strip()


def resolve_redirect_raw(page_url: str, raw_text: str) -> tuple[str, str]:
    redirect_title = redirect_target_title(raw_text)
    if redirect_title is None:
        return page_url, raw_text
    resolved_page_url = page_url_from_title(page_url, redirect_title)
    return resolved_page_url, fetch_text(page_to_raw_url(resolved_page_url))


def source_ids(section_id: str, manifest: dict[str, Any]) -> tuple[str, str]:
    defaults = manifest["source_pair_defaults"]
    return (
        f"{section_id}__{defaults['source_id']}",
        f"{section_id}__{defaults['target_source_id']}",
    )


def parse_chinese_segments(section: dict[str, Any], raw_text: str, source_id: str) -> list[dict[str, Any]]:
    onlyinclude_match = re.search(r"<onlyinclude>(.*)</onlyinclude>", raw_text, flags=re.S)
    working = onlyinclude_match.group(1) if onlyinclude_match else raw_text
    segments: list[dict[str, Any]] = []
    pattern = re.compile(r'<div id="([^"]+)"[^>]*>.*?</div>\s*(.*?)(?=\n\s*<div id="|\s*</onlyinclude>|\Z)', flags=re.S)
    for block_id, block_text in pattern.findall(working):
        text = clean_chinese_text(block_text)
        if not text:
            continue
        order = len(segments) + 1
        canonical_ref = f"論語 {section['sort_key']}.{order}"
        segment_id = f"lunyu__{section['section_id']}__{order:03d}__zhwikisource-20260529"
        segments.append(
            {
                "segment_id": segment_id,
                "work_id": "lunyu",
                "section_id": section["section_id"],
                "source_id": source_id,
                "segment_type": "saying",
                "segment_order": order,
                "canonical_ref": canonical_ref,
                "text_original": text,
                "text_normalized": text,
                "notes": f"Chinese Wikisource element id {block_id}.",
            }
        )
    return segments


def strip_embedded_chinese_blocks(raw_text: str) -> str:
    return re.sub(r"\{\{lang(?: block)?\|zh(?:-hant)?\|.*?\}\}\s*", "", raw_text, flags=re.S)


def split_numbered_english_subparts(block_text: str) -> list[str]:
    matches = list(re.finditer(r"(?:^|\n)\s*(\d+)\.\s*", block_text, flags=re.M))
    if len(matches) < 2:
        return []
    parts: list[str] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(block_text)
        part = block_text[start:end].strip()
        if part:
            parts.append(part)
    return parts


def parse_english_segments(
    section: dict[str, Any],
    raw_text: str,
    source_id: str,
    expected_segment_count: int | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    heading_match = re.search(r"^==\s*The Analects\.\s*(.*?)\s*==", raw_text, flags=re.M)
    if heading_match:
        heading = heading_match.group(1).strip()
    else:
        section_match = re.search(r"^\|\s*section\s*=\s*(.+)$", raw_text, flags=re.M)
        heading = section_match.group(1).strip() if section_match else f"Book {section['sort_key']}"

    english_only = strip_embedded_chinese_blocks(raw_text)
    segments: list[dict[str, Any]] = []
    chapter_matches = list(
        re.finditer(
            r"\{\{sc\|Chapter\}\}\s+([IVXLCDM]+)\.?\s*(.*?)(?=\n\s*\{\{sc\|Chapter\}\}\s+[IVXLCDM]+\.?|\Z)",
            english_only,
            flags=re.S,
        )
    )
    chapter_blocks: list[tuple[str, list[str]]] = []
    for match in chapter_matches:
        book_roman = match.group(1)
        block_text = match.group(2).strip()
        block_parts = [block_text]
        if (
            expected_segment_count is not None
            and len(chapter_matches) + 1 == expected_segment_count
        ):
            if match is chapter_matches[-1]:
                numbered_parts = split_numbered_english_subparts(block_text)
                if len(numbered_parts) == 2:
                    block_parts = numbered_parts
            elif section["section_id"] == "book-05-gongyechang" and match is chapter_matches[0]:
                numbered_parts = split_numbered_english_subparts(block_text)
                if len(numbered_parts) == 2:
                    block_parts = numbered_parts
        chapter_blocks.append((book_roman, block_parts))
    for book_roman, block_parts in chapter_blocks:
        for subpart_index, block_text in enumerate(block_parts, start=1):
            cleaned = clean_english_text(block_text)
            if not cleaned:
                continue
            order = len(segments) + 1
            canonical_ref = f"Analects {book_roman}.{subpart_index}" if len(block_parts) > 1 else f"Analects {book_roman}.{order}"
            segment_id = f"lunyu__{section['section_id']}__{order:03d}__legge-cc-v1-1893"
            segments.append(
                {
                    "segment_id": segment_id,
                    "work_id": "lunyu",
                    "section_id": section["section_id"],
                    "source_id": source_id,
                    "segment_type": "saying",
                    "segment_order": order,
                    "canonical_ref": canonical_ref,
                    "text_original": cleaned,
                    "text_normalized": cleaned,
                    "notes": f"{heading}; Chapter {book_roman}.",
                }
            )
    return heading, segments


def build_alignments(
    section: dict[str, Any],
    chinese_source_id: str,
    english_source_id: str,
    chinese_segments: list[dict[str, Any]],
    english_segments: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, str]:
    alignments: list[dict[str, Any]] = []
    exact_alignment_count = 0
    alignment_status = "section_group_only"
    if chinese_segments and len(chinese_segments) == len(english_segments):
        alignment_status = "complete"
        for order, (chinese_segment, english_segment) in enumerate(zip(chinese_segments, english_segments), start=1):
            alignments.append(
                {
                    "alignment_id": f"lunyu__{section['section_id']}__{order:03d}__zhwikisource-20260529__legge-cc-v1-1893",
                    "work_id": "lunyu",
                    "section_id": section["section_id"],
                    "source_id": chinese_source_id,
                    "target_source_id": english_source_id,
                    "alignment_type": "exact_or_near_exact",
                    "confidence": 0.99,
                    "chinese_segment_ids": [chinese_segment["segment_id"]],
                    "translation_segment_ids": [english_segment["segment_id"]],
                    "notes": f"{chinese_segment['canonical_ref']} -> {english_segment['canonical_ref']}.",
                }
            )
        exact_alignment_count = len(chinese_segments)

    group_note = "Section-level grouped alignment across the full book."
    if alignment_status != "complete":
        group_note = (
            "Section-level grouped alignment only; "
            f"parsed {len(chinese_segments)} Chinese segments and {len(english_segments)} English segments."
        )
    alignments.append(
        {
            "alignment_id": f"lunyu__{section['section_id']}__section-group__zhwikisource-20260529__legge-cc-v1-1893",
            "work_id": "lunyu",
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
    return alignments, exact_alignment_count, alignment_status


def section_paths(section: dict[str, Any]) -> dict[str, Path]:
    base_name = f"lunyu__{section['section_id']}"
    return {
        "zh_raw": RAW_DIR / f"{base_name}__zhwikisource-20260529__raw.wikitext",
        "en_raw": RAW_DIR / f"{base_name}__legge-cc-v1-1893__raw.wikitext",
        "zh_base": CHINESE_DIR / f"{base_name}__zhwikisource-20260529__base.txt",
        "zh_segments": CHINESE_DIR / f"{base_name}__zhwikisource-20260529__segments.jsonl",
        "en_text": TRANSLATION_DIR / f"{base_name}__legge-cc-v1-1893__translation.txt",
        "en_segments": TRANSLATION_DIR / f"{base_name}__legge-cc-v1-1893__segments.jsonl",
        "alignments": ALIGNMENT_DIR / f"{base_name}__zhwikisource-20260529__legge-cc-v1-1893__alignments.jsonl",
    }


def build_sources(section: dict[str, Any], manifest: dict[str, Any], heading: str, paths: dict[str, Path]) -> list[dict[str, Any]]:
    chinese_source_id, english_source_id = source_ids(section["section_id"], manifest)
    return [
        {
            "source_id": chinese_source_id,
            "work_id": "lunyu",
            "section_id": section["section_id"],
            "language_code": manifest["source_pair_defaults"]["source_language"],
            "source_kind": "wikisource",
            "citation": f"{title_from_url(section['zh_page_url'])}, Chinese Wikisource, accessed {ACCESS_DATE}.",
            "source_url": section["zh_page_url"],
            "raw_path": str(paths["zh_raw"].relative_to(REPO_ROOT)),
            "processed_path": str(paths["zh_segments"].relative_to(REPO_ROOT)),
            "rights_status": "public_domain",
            "author_or_translator_ids": ["confucius-disciples"],
            "notes": "Untouched raw capture comes from the page's action=raw export.",
        },
        {
            "source_id": english_source_id,
            "work_id": "lunyu",
            "section_id": section["section_id"],
            "language_code": manifest["source_pair_defaults"]["target_language"],
            "source_kind": "translation",
            "citation": f"James Legge, The Chinese Classics, Volume 1: Confucian Analects, {heading}, via English Wikisource.",
            "source_url": section["en_page_url"],
            "raw_path": str(paths["en_raw"].relative_to(REPO_ROOT)),
            "processed_path": str(paths["en_segments"].relative_to(REPO_ROOT)),
            "rights_status": "public_domain",
            "author_or_translator_ids": ["james-legge"],
            "notes": "English Wikisource hosts the public-domain translation page for this book.",
        },
    ]


def write_section_files(
    section: dict[str, Any],
    manifest: dict[str, Any],
    skip_fetch: bool,
) -> dict[str, Any]:
    section = dict(section)
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

    chinese_source_id, english_source_id = source_ids(section["section_id"], manifest)
    chinese_segments = parse_chinese_segments(section, zh_raw, chinese_source_id)
    heading, english_segments = parse_english_segments(
        section,
        en_raw,
        english_source_id,
        expected_segment_count=len(chinese_segments),
    )
    alignments, exact_alignment_count, alignment_status = build_alignments(
        section,
        chinese_source_id,
        english_source_id,
        chinese_segments,
        english_segments,
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

    enriched_section = dict(section)
    enriched_section["legge_section_alias"] = heading
    enriched_section["alignment_status"] = alignment_status
    enriched_section["tmx_status"] = "complete" if exact_alignment_count else "section_group_only"
    enriched_section["expected_exact_alignment_count"] = exact_alignment_count
    enriched_section["source_ids"] = {
        "source_id": chinese_source_id,
        "target_source_id": english_source_id,
    }

    return {
        "section": enriched_section,
        "sources": build_sources(section, manifest, heading, paths),
        "chinese_segments": chinese_segments,
        "english_segments": english_segments,
        "alignments": alignments,
    }


def ensure_static_metadata() -> None:
    if not WORKS_PATH.exists():
        write_json(
            WORKS_PATH,
            [
                {
                    "work_id": "lunyu",
                    "canonical_title": "論語",
                    "english_title": "Confucian Analects",
                    "work_type": "classical_text",
                    "language_code": "zh-Hant",
                    "default_citation": "論語",
                    "notes": "Full Lunyu public-domain corpus aligned against James Legge's translation.",
                }
            ],
        )
    if not PERSONS_PATH.exists():
        write_json(
            PERSONS_PATH,
            [
                {
                    "person_id": "confucius-disciples",
                    "display_name": "孔子的弟子與再傳弟子",
                    "romanized_name": "Confucius's students and subsequent transmitters",
                    "roles": ["compiler"],
                    "notes": "Authority string follows the Chinese Wikisource attribution for 論語.",
                },
                {
                    "person_id": "james-legge",
                    "display_name": "James Legge",
                    "romanized_name": "James Legge",
                    "roles": ["translator"],
                    "notes": "Translator of The Chinese Classics, Volume 1.",
                },
            ],
        )
    if not RIGHTS_PATH.exists():
        write_json(
            RIGHTS_PATH,
            [
                {
                    "rights_id": "public_domain",
                    "label": "Public domain",
                    "description": "Source text can be stored and redistributed in full.",
                },
                {
                    "rights_id": "metadata_only",
                    "label": "Metadata only",
                    "description": "Only bibliographic metadata may be stored until rights are cleared.",
                },
            ],
        )


def bootstrap_corpus(skip_fetch: bool = False) -> dict[str, Any]:
    ensure_static_metadata()
    manifest = load_json_compatible_yaml(MANIFEST_PATH)
    processed_sections: list[dict[str, Any]] = []
    all_sources: list[dict[str, Any]] = []
    sections_metadata: list[dict[str, Any]] = []
    aliases: list[dict[str, Any]] = [
        {
            "entity_type": "work",
            "entity_id": "lunyu",
            "alias": "Lunyu",
            "romanization_system": "pinyin",
        },
        {
            "entity_type": "work",
            "entity_id": "lunyu",
            "alias": "Analects",
            "romanization_system": "english-title",
        },
    ]
    ingestion_log: list[dict[str, Any]] = []
    total_exact_alignments = 0

    for section in manifest["sections"]:
        result = write_section_files(section, manifest, skip_fetch=skip_fetch)
        processed_sections.append(result["section"])
        all_sources.extend(result["sources"])
        total_exact_alignments += result["section"]["expected_exact_alignment_count"]
        sections_metadata.append(
            {
                "section_id": result["section"]["section_id"],
                "work_id": "lunyu",
                "parent_section_id": None,
                "label": result["section"]["label"],
                "canonical_ref": result["section"]["canonical_ref"],
                "sort_key": result["section"]["sort_key"],
                "notes": f"Chinese Wikisource labels this section {result['section']['label']}; Legge labels the same unit {result['section']['legge_section_alias']}.",
            }
        )
        aliases.extend(
            [
                {
                    "entity_type": "section",
                    "entity_id": result["section"]["section_id"],
                    "alias": result["section"]["slug"].replace("-", " ").title(),
                    "romanization_system": "pinyin",
                },
                {
                    "entity_type": "section",
                    "entity_id": result["section"]["section_id"],
                    "alias": result["section"]["legge_section_alias"].replace("Book ", "").strip(),
                    "romanization_system": "Legge-Wade-Giles",
                },
            ]
        )
        ingestion_log.append(
            {
                "run_id": f"bootstrap-{result['section']['section_id']}-{ACCESS_DATE.replace('-', '')}",
                "work_id": "lunyu",
                "section_id": result["section"]["section_id"],
                "status": "complete",
                "source_ids": [
                    result["section"]["source_ids"]["source_id"],
                    result["section"]["source_ids"]["target_source_id"],
                ],
                "notes": (
                    f"Bootstrap corpus generation for {result['section']['label']} with "
                    f"{result['section']['expected_exact_alignment_count']} exact alignments and "
                    f"alignment status {result['section']['alignment_status']}."
                ),
            }
        )

    sections_needing_alignment = sum(1 for section in processed_sections if section["alignment_status"] != "complete")
    sections_needing_qc = sum(1 for section in processed_sections if section["tmx_status"] != "complete")
    manifest["sections"] = processed_sections
    manifest["summary"] = {
        "section_count": len(processed_sections),
        "complete_sections": len(processed_sections) - sections_needing_alignment,
        "metadata_only_sections": 0,
        "sections_needing_alignment": sections_needing_alignment,
        "sections_needing_qc": sections_needing_qc,
        "exact_alignment_count": total_exact_alignments,
    }

    write_json(MANIFEST_PATH, manifest)
    write_json(SECTIONS_PATH, sections_metadata)
    write_json(SOURCES_PATH, all_sources)
    write_json(ALIASES_PATH, aliases)
    write_json(INGESTION_LOG_PATH, ingestion_log)
    return manifest["summary"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Bootstrap raw captures, processed files, and metadata for the full Lunyu corpus.")
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
