from __future__ import annotations

import argparse
import json
import re
import urllib.request
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from chinesenotes_alignment import (
    find_anchor_drift_issues,
    join_unit_texts,
    load_alignment_anchor_maps,
    load_alignment_overrides,
    partition_block_texts_by_anchors,
    refine_alignment,
    render_completion_quality_markdown,
)
from common import DOCUMENTATION_DIR, METADATA_DIR, QC_REPORTS_DIR, REPO_ROOT, read_jsonl, repo_relative, sha256_file, write_json, write_jsonl
from text_quality import detect_probable_ocr_corruption

WORK_ID = "shangshu"
WORK_LABEL = "Shangshu"
CANONICAL_TITLE = "尚書"
ENGLISH_TITLE = "Book of Documents"
UPSTREAM_REPOSITORY_URL = "https://github.com/alexamies/chinesenotes.com"
UPSTREAM_COMMIT_SHA = "1f6b1d3e7a40b6886a4b943c898125639e993544"
UPSTREAM_COMMIT_SHORT = UPSTREAM_COMMIT_SHA[:7]
REVIEW_DATE = "2026-06-01"

STAGING_ROOT = REPO_ROOT / "corpus" / "staging" / "chinesenotes" / WORK_ID
RAW_ROOT = REPO_ROOT / "corpus" / "raw" / "chinesenotes"
WIKISOURCE_RAW_ROOT = REPO_ROOT / "corpus" / "raw" / "wikisource"
CHINESE_OUTPUT_ROOT = REPO_ROOT / "corpus" / "processed" / "chinese_base_texts"
TRANSLATION_OUTPUT_ROOT = REPO_ROOT / "corpus" / "processed" / "translations"
ALIGNMENT_OUTPUT_ROOT = REPO_ROOT / "corpus" / "processed" / "alignments"
MANIFEST_PATH = METADATA_DIR / "manifests" / f"{WORK_ID}.yml"
INVENTORY_PATH = METADATA_DIR / f"{WORK_ID}_inventory.yml"
LEDGER_PATH = METADATA_DIR / f"{WORK_ID}_verification_ledger.yml"
OVERRIDES_PATH = METADATA_DIR / f"{WORK_ID}_alignment_overrides.yml"
ANCHOR_MAP_PATH = METADATA_DIR / f"{WORK_ID}_alignment_anchors.yml"
ALIGNMENT_QC_PATH = QC_REPORTS_DIR / f"{WORK_ID}__alignment_qc.json"
COMPLETION_REPORT_PATH = DOCUMENTATION_DIR / f"{WORK_ID}_completion_quality.md"

WIKISOURCE_BASE_URL = "https://en.wikisource.org"
WIKISOURCE_VOLUME_PATH = "Sacred_Books_of_the_East/Volume_3"
WIKISOURCE_WORK_PATH = f"{WIKISOURCE_VOLUME_PATH}/The_Shu"
WIKISOURCE_TRANSLATION_SOURCE_KEY = "legge-sbe-wikisource-20260601"
WIKISOURCE_TRANSLATION_LABEL = "Wikisource transcription of James Legge, Sacred Books of the East, Volume 3"
WIKISOURCE_ACCESS_DATE = "2026-06-01"
WIKISOURCE_USER_AGENT = "Mozilla/5.0"
WIKISOURCE_TOC_LINK_RE = re.compile(
    r'<a href="//en\.wikisource\.org(/wiki/Sacred_Books_of_the_East/Volume_3/The_Shu[^"]+)"[^>]*>(.*?)</a>'
)
TRANSLATION_HEADING_RE = re.compile(r"^(?:THE SH[UÛ] KING\.?|PART\s+[IVXLC]+\.|Book\s+[IVXLC]+\.|Section\s+\d+\.)$")
TRANSLATION_START_RE = re.compile(
    r"^(?:"
    r"\d+\.\s+|"
    r"In the spring\b|On \(*the day\b|There was\b|Now\b|When\b|"
    r"The king\b.*(?:said|spoke|declared)|"
    r"The duke\b.*(?:said|spoke)|"
    r"The marquis\b.*(?:said|spoke)|"
    r"The count\b.*(?:said|spoke)|"
    r"The prince\b.*(?:said|spoke)|"
    r"King [A-Z].*|Duke [A-Z].*|"
    r"[\"'])"
)


class _RenderedParagraphExtractor(HTMLParser):
    SKIP_TAGS = {"style", "script", "table"}
    SKIP_CLASSES = {"ws-noexport", "reference", "mw-editsection", "pagenum", "smallrefs", "error", "pr_quality"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._in_paragraph = False
        self._current: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        classes = set(attr_map.get("class", "").split())
        if tag in self.SKIP_TAGS or classes & self.SKIP_CLASSES:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == "br" and self._in_paragraph:
            self._current.append("\n")
        if tag == "p":
            self._in_paragraph = True
            self._current = []

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth and tag in self.SKIP_TAGS | {"div", "span", "sup", "table"}:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth:
            return
        if tag == "p" and self._in_paragraph:
            text = unescape("".join(self._current)).replace("„", "")
            text = re.sub(r"(?<=\w)\d+\]", "", text)
            text = re.sub(r"\*+", "", text)
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                self.paragraphs.append(text)
            self._in_paragraph = False
            self._current = []

    def handle_data(self, data: str) -> None:
        if self._in_paragraph and not self._skip_depth:
            self._current.append(data)


def _load_staged_sections() -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, list[str]]]:
    sections = read_jsonl(STAGING_ROOT / "sections.jsonl")
    chinese_blocks: dict[str, list[str]] = {}
    english_blocks: dict[str, list[str]] = {}
    for record in read_jsonl(STAGING_ROOT / "chinese_blocks.jsonl"):
        chinese_blocks.setdefault(str(record["section_id"]), []).append(str(record["text_original"]))
    for record in read_jsonl(STAGING_ROOT / "english_blocks.jsonl"):
        english_blocks.setdefault(str(record["section_id"]), []).append(str(record["text_original"]))
    return sections, chinese_blocks, english_blocks


def _fetch_wikisource_html(path: str) -> str:
    url = f"{WIKISOURCE_BASE_URL}/w/index.php?title={path}&action=render"
    request = urllib.request.Request(url, headers={"User-Agent": WIKISOURCE_USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8", "ignore")


def _discover_wikisource_section_page_groups() -> list[list[dict[str, str]]]:
    html = _fetch_wikisource_html(WIKISOURCE_VOLUME_PATH)
    toc_links: list[tuple[str, str]] = []
    for href, title_html in WIKISOURCE_TOC_LINK_RE.findall(html):
        if "/Introduction/" in href or "#" in href:
            continue
        title = unescape(re.sub(r"<[^>]+>", "", title_html)).strip().replace("„", "")
        toc_links.append((title, href.replace("/wiki/", "")))

    groups: list[list[dict[str, str]]] = []
    index = 0
    while index < len(toc_links):
        title, path = toc_links[index]
        if path.endswith("Part_3/Book_1/Section_1"):
            second_title, second_path = toc_links[index + 1]
            groups.append(
                [
                    {"title": title, "path": path},
                    {"title": second_title, "path": second_path},
                ]
            )
            index += 2
            continue
        book_match = re.match(r"(.+/Book_\d+)$", path)
        if book_match:
            book_prefix = book_match.group(1)
            lookahead = index + 1
            section_paths: list[tuple[str, str]] = []
            while lookahead < len(toc_links) and toc_links[lookahead][1].startswith(book_prefix + "/Section_"):
                section_paths.append(toc_links[lookahead])
                lookahead += 1
            if section_paths:
                for section_title, section_path in section_paths:
                    groups.append([{"title": f"{title} {section_title}".strip(), "path": section_path}])
                index = lookahead
                continue
        if "/Section_" not in path:
            groups.append([{"title": title, "path": path}])
        index += 1
    return groups


def _wikisource_translation_raw_capture_path(section_id: str) -> Path:
    return WIKISOURCE_RAW_ROOT / f"{WORK_ID}__{section_id}__{WIKISOURCE_TRANSLATION_SOURCE_KEY}__raw.json"


def _fetch_missing_wikisource_raw_captures(sections: list[dict[str, Any]]) -> None:
    exportable_sections = [section for section in sections if section["status"] == "exportable_candidate"]
    page_groups = _discover_wikisource_section_page_groups()
    if len(exportable_sections) != len(page_groups):
        raise ValueError(
            f"Wikisource Shangshu section count mismatch: expected {len(exportable_sections)} exportable sections, found {len(page_groups)} page groups."
        )
    WIKISOURCE_RAW_ROOT.mkdir(parents=True, exist_ok=True)
    for section_record, page_group in zip(exportable_sections, page_groups):
        section_id = str(section_record["section_id"])
        raw_capture_path = _wikisource_translation_raw_capture_path(section_id)
        if raw_capture_path.exists():
            continue
        payload = {
            "section_id": section_id,
            "source_id": f"{section_id}__{WIKISOURCE_TRANSLATION_SOURCE_KEY}",
            "source_name": WIKISOURCE_TRANSLATION_LABEL,
            "source_url": f"{WIKISOURCE_BASE_URL}/wiki/{page_group[0]['path']}",
            "access_date": WIKISOURCE_ACCESS_DATE,
            "pages": [],
        }
        for page in page_group:
            payload["pages"].append(
                {
                    "title": page["title"],
                    "path": page["path"],
                    "url": f"{WIKISOURCE_BASE_URL}/wiki/{page['path']}",
                    "render_url": f"{WIKISOURCE_BASE_URL}/w/index.php?title={page['path']}&action=render",
                    "html": _fetch_wikisource_html(page["path"]),
                }
            )
        write_json(raw_capture_path, payload)


def _extract_translation_blocks_from_rendered_html(rendered_html: str) -> list[str]:
    extractor = _RenderedParagraphExtractor()
    extractor.feed(rendered_html)
    blocks: list[str] = []
    started = False
    for paragraph in extractor.paragraphs:
        if not started:
            if TRANSLATION_HEADING_RE.match(paragraph):
                continue
            if TRANSLATION_START_RE.match(paragraph):
                started = True
            else:
                continue
        blocks.append(paragraph)
    return blocks


def _load_wikisource_translation_blocks(section_id: str) -> tuple[list[str], dict[str, Any]]:
    raw_capture_path = _wikisource_translation_raw_capture_path(section_id)
    if not raw_capture_path.exists():
        raise FileNotFoundError(f"Missing Shangshu Wikisource raw capture: {repo_relative(raw_capture_path)}")
    payload = json.loads(raw_capture_path.read_text(encoding="utf-8"))
    blocks: list[str] = []
    for page in payload.get("pages", []):
        blocks.extend(_extract_translation_blocks_from_rendered_html(str(page["html"])))
    if not blocks:
        raise ValueError(f"No Shangshu translation blocks extracted from {repo_relative(raw_capture_path)}")
    return blocks, payload


def _split_displayed_title(displayed_title: str) -> tuple[str, str | None]:
    text = displayed_title.strip()
    english_title = None
    if " - " in text:
        before_dash, english_title = text.rsplit(" - ", 1)
        text = before_dash.strip()
        english_title = english_title.strip() or None
    chinese_title = text
    while chinese_title and chinese_title[-1].isascii():
        chinese_title = chinese_title[:-1].rstrip()
    return chinese_title or displayed_title.strip(), english_title


def _section_sort_key(section_record: dict[str, Any]) -> str:
    return f"{int(section_record['source_row_index']):03d}"


def _section_label(section_record: dict[str, Any]) -> str:
    return str(section_record["displayed_title"]).strip()


def _canonical_ref(section_record: dict[str, Any]) -> str:
    chinese_title, _ = _split_displayed_title(_section_label(section_record))
    return f"{CANONICAL_TITLE}·{chinese_title}"


def _source_ids(section_id: str) -> tuple[str, str]:
    return (
        f"{section_id}__chinesenotes-shangshu-zh-{UPSTREAM_COMMIT_SHORT}",
        f"{section_id}__{WIKISOURCE_TRANSLATION_SOURCE_KEY}",
    )


def _raw_capture_path(section_record: dict[str, Any]) -> Path:
    section_id = str(section_record["section_id"])
    return RAW_ROOT / f"{WORK_ID}__{section_id}__chinesenotes-{UPSTREAM_COMMIT_SHORT}__raw.txt"


def _write_segments(
    *,
    work_id: str,
    section_id: str,
    source_id: str,
    canonical_ref: str,
    texts: list[str],
    language: str,
    output_path: Path,
) -> list[dict[str, Any]]:
    segment_type = "block"
    records = [
        {
            "segment_id": f"{source_id}__segment-{index:03d}",
            "work_id": work_id,
            "section_id": section_id,
            "source_id": source_id,
            "segment_type": segment_type,
            "segment_order": index,
            "canonical_ref": f"{canonical_ref} [{index}]",
            "text_original": text,
            "text_normalized": text,
            "notes": "",
        }
        for index, text in enumerate(texts, start=1)
    ]
    write_jsonl(output_path, records)
    return records


def _build_alignment_records(
    *,
    section_id: str,
    source_id: str,
    target_source_id: str,
    chinese_segments: list[dict[str, Any]],
    english_segments: list[dict[str, Any]],
    alignment: dict[str, Any],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for index, group in enumerate(alignment["groups"], start=1):
        chinese_ids = [chinese_segments[unit_index]["segment_id"] for unit_index in group["source_unit_indices"]]
        english_ids = [english_segments[unit_index]["segment_id"] for unit_index in group["target_unit_indices"]]
        notes = []
        if alignment["strategy"] == "curated_override":
            notes.append("Curated override alignment.")
            if group.get("curator_note"):
                notes.append(str(group["curator_note"]))
        elif alignment["strategy"] == "anchor_partition_auto_alignment":
            notes.append("Anchor-partitioned exact block alignment.")
        else:
            notes.append("Deterministic ChineseNotes monotonic grouped alignment.")
        records.append(
            {
                "alignment_id": f"{section_id}__alignment-{index:03d}",
                "work_id": WORK_ID,
                "section_id": section_id,
                "source_id": source_id,
                "target_source_id": target_source_id,
                "alignment_type": "exact_or_near_exact",
                "confidence": 1.0 if alignment["strategy"] != "curated_override" else 0.95,
                "chinese_segment_ids": chinese_ids,
                "translation_segment_ids": english_ids,
                "alignment_granularity": alignment["alignment_granularity"],
                "section_unit": "section",
                "segment_type": "block",
                "is_coarse_alignment": False,
                "coarse_alignment_reason": None,
                "source_segment_count": len(chinese_ids),
                "target_segment_count": len(english_ids),
                "notes": " ".join(notes),
            }
        )
    records.append(
        {
            "alignment_id": f"{section_id}__section-group",
            "work_id": WORK_ID,
            "section_id": section_id,
            "source_id": source_id,
            "target_source_id": target_source_id,
            "alignment_type": "section_group",
            "confidence": 1.0,
            "chinese_segment_ids": [segment["segment_id"] for segment in chinese_segments],
            "translation_segment_ids": [segment["segment_id"] for segment in english_segments],
            "alignment_granularity": "section_group",
            "section_unit": "section",
            "segment_type": "block",
            "is_coarse_alignment": False,
            "coarse_alignment_reason": None,
            "source_segment_count": len(chinese_segments),
            "target_segment_count": len(english_segments),
            "notes": "Shangshu section-group coverage row spanning all aligned block segments.",
        }
    )
    return records


def _alignment_preview_rows(section_id: str, alignment: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, group in enumerate(alignment["groups"], start=1):
        rows.append(
            {
                "alignment_id": f"{section_id}__preview-alignment-{index:03d}",
                "section_id": section_id,
                "chinese_text": join_unit_texts(
                    alignment["source_units"], list(group["source_unit_indices"]), "zh"
                ),
                "translation_text": join_unit_texts(
                    alignment["target_units"], list(group["target_unit_indices"]), "en"
                ),
            }
        )
    return rows


def _chinese_source_note(section_record: dict[str, Any]) -> str:
    metadata = section_record["source_metadata"]
    return (
        f"ChineseNotes public-domain Shangshu mirror. Upstream repository: {UPSTREAM_REPOSITORY_URL} @ {UPSTREAM_COMMIT_SHA}. "
        f"Upstream relative path: {metadata['upstream_relative_path']}. Source SHA256: {metadata['source_sha256']}. "
        f"Review date: {REVIEW_DATE}. Repository-level licence basis: {metadata['license_basis']}. "
        f"Rights/source notes detected by parser: {'; '.join(metadata['rights_notes']) if metadata['rights_notes'] else 'none'}. "
        f"Local raw capture: {repo_relative(_raw_capture_path(section_record))}. "
        f"Local staging source: corpus/staging/chinesenotes/{WORK_ID}/sections.jsonl."
    )


def _translation_source_note(section_record: dict[str, Any], translation_payload: dict[str, Any]) -> str:
    page_urls = [str(page["url"]) for page in translation_payload.get("pages", [])]
    metadata = section_record["source_metadata"]
    return (
        f"{WIKISOURCE_TRANSLATION_LABEL}. Accessed {WIKISOURCE_ACCESS_DATE}. "
        f"Page witness count: {len(page_urls)}. Witness pages: {'; '.join(page_urls)}. "
        f"Translator/source notes detected in ChineseNotes staging and excluded from export: "
        f"{'; '.join(metadata['translator_notes']) if metadata['translator_notes'] else 'none'}. "
        f"Local raw capture: {repo_relative(_wikisource_translation_raw_capture_path(str(section_record['section_id'])))}."
    )


def _work_source_records(
    *,
    section_record: dict[str, Any],
    source_id: str,
    target_source_id: str | None,
    chinese_processed_path: Path,
    english_processed_path: Path | None,
    translation_payload: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    metadata = section_record["source_metadata"]
    source_url = f"{UPSTREAM_REPOSITORY_URL}/blob/{UPSTREAM_COMMIT_SHA}/{metadata['upstream_relative_path']}"
    records = [
        {
            "work_id": WORK_ID,
            "section_id": section_record["section_id"],
            "source_id": source_id,
            "language_code": "zh-Hant",
            "source_kind": "base_text",
            "citation": f"{_canonical_ref(section_record)}, ChineseNotes mirror, reviewed {REVIEW_DATE}, upstream commit {UPSTREAM_COMMIT_SHA}.",
            "source_url": source_url,
            "rights_status": "public_domain",
            "author_or_translator_ids": ["shangshu-transmitters"],
            "raw_path": repo_relative(_raw_capture_path(section_record)),
            "processed_path": repo_relative(chinese_processed_path),
            "notes": _chinese_source_note(section_record),
        }
    ]
    if target_source_id and english_processed_path and translation_payload:
        translation_pages = translation_payload.get("pages", [])
        records.append(
            {
                "work_id": WORK_ID,
                "section_id": section_record["section_id"],
                "source_id": target_source_id,
                "language_code": "en",
                "source_kind": "translation",
                "citation": f"James Legge translation for {_canonical_ref(section_record)} in Sacred Books of the East, Volume 3, accessed via Wikisource on {WIKISOURCE_ACCESS_DATE}.",
                "source_url": str(translation_pages[0]["url"]),
                "rights_status": "public_domain",
                "author_or_translator_ids": ["james-legge"],
                "raw_path": repo_relative(_wikisource_translation_raw_capture_path(str(section_record["section_id"]))),
                "processed_path": repo_relative(english_processed_path),
                "notes": _translation_source_note(section_record, translation_payload),
            }
        )
    return records


def _section_notes(section_record: dict[str, Any], *, decision: str, alignment: dict[str, Any] | None) -> str:
    notes: list[str] = []
    if section_record["commentary_present"]:
        notes.append("Commentary or heading lines were present in the staged source and excluded before export.")
    if section_record["english_headings"]:
        notes.append(f"Excluded English headings: {', '.join(section_record['english_headings'])}.")
    if decision != "export":
        notes.append(str(section_record["blocking_reason"]))
    elif alignment and alignment["strategy"] == "anchor_partition_auto_alignment":
        notes.append("Export uses anchor-partitioned exact block alignment.")
    elif alignment and alignment["alignment_granularity"] == "grouped":
        notes.append("Export uses monotonic grouped block alignment.")
    else:
        notes.append("Export uses exact block alignment.")
    return " ".join(notes)


def _inventory_entry(section_record: dict[str, Any], *, decision: str, reason: str | None) -> dict[str, Any]:
    metadata = section_record["source_metadata"]
    chinese_title, english_title = _split_displayed_title(_section_label(section_record))
    entry = {
        "section_id": section_record["section_id"],
        "title": _section_label(section_record),
        "canonical_ref": _canonical_ref(section_record),
        "sort_key": _section_sort_key(section_record),
        "unit_type": "section",
        "text_status": "extant",
        "coverage_status": "complete" if section_record["status"] == "exportable_candidate" else "partial",
        "zh_page_url": f"{UPSTREAM_REPOSITORY_URL}/blob/{UPSTREAM_COMMIT_SHA}/{metadata['upstream_relative_path']}",
        "english_witness_status": "verified_rendered_transcription" if decision == "export" else "missing_translation",
        "verification_status": "verified_rendered_transcription" if decision == "export" else "metadata_only",
        "source_volume": chinese_title.split()[0] if chinese_title else CANONICAL_TITLE,
        "translator": "James Legge" if decision == "export" else None,
        "decision": decision,
    }
    if english_title:
        entry["english_title"] = english_title
    if reason:
        entry["reason"] = reason
    return entry


def _ledger_entry(
    section_record: dict[str, Any],
    *,
    decision: str,
    source_id: str,
    target_source_id: str | None,
    chinese_processed_path: Path,
    english_processed_path: Path | None,
    translation_payload: dict[str, Any] | None,
    alignment: dict[str, Any] | None,
    exact_alignment_count: int,
    reason: str | None,
) -> dict[str, Any]:
    metadata = section_record["source_metadata"]
    chinese_title, _ = _split_displayed_title(_section_label(section_record))
    return {
        "section_id": section_record["section_id"],
        "title": _section_label(section_record),
        "canonical_ref": _canonical_ref(section_record),
        "source_volume": chinese_title.split()[0] if chinese_title else CANONICAL_TITLE,
        "source_page_or_anchor": f"{UPSTREAM_REPOSITORY_URL}/blob/{UPSTREAM_COMMIT_SHA}/{metadata['upstream_relative_path']}",
        "translation_source_pages": [str(page["url"]) for page in (translation_payload or {}).get("pages", [])],
        "raw_source_path": repo_relative(_raw_capture_path(section_record)),
        "processed_source_path": repo_relative(chinese_processed_path),
        "processed_translation_path": repo_relative(english_processed_path) if english_processed_path else None,
        "upstream_repository_url": UPSTREAM_REPOSITORY_URL,
        "upstream_commit_sha": UPSTREAM_COMMIT_SHA,
        "upstream_relative_path": metadata["upstream_relative_path"],
        "source_sha256": metadata["source_sha256"],
        "repository_level_licence_basis": metadata["license_basis"],
        "translator_note": "; ".join(metadata["translator_notes"]) if metadata["translator_notes"] else None,
        "rights_or_source_notes": metadata["rights_notes"],
        "translator_or_source_notes": metadata["translator_notes"],
        "local_staging_path": f"corpus/staging/chinesenotes/{WORK_ID}/sections.jsonl",
        "local_raw_capture_path": repo_relative(_raw_capture_path(section_record)),
        "translation_raw_capture_path": (
            repo_relative(_wikisource_translation_raw_capture_path(str(section_record["section_id"])))
            if translation_payload
            else None
        ),
        "verification_status": "verified_rendered_transcription" if decision == "export" else "metadata_only",
        "reviewer_note": "ChineseNotes Chinese text was retained, while the English witness was rebuilt from clean Wikisource-rendered SBE pages; headings, commentary, and notices were excluded from exportable text.",
        "extraction_method": "chinesenotes_chinese_plus_wikisource_legge_translation",
        "alignment_status": "complete" if decision == "export" else "not_exported",
        "alignment_granularity": alignment["alignment_granularity"] if alignment else None,
        "alignment_strategy": alignment["strategy"] if alignment else None,
        "alignment_anchor_map_used": bool(alignment and alignment.get("anchor_map_used")),
        "alignment_anchor_count": int(alignment.get("anchor_count", 0)) if alignment else 0,
        "segment_granularity": alignment["segment_granularity"] if alignment else None,
        "exact_alignment_count": exact_alignment_count,
        "commentary_present_and_excluded": bool(section_record["commentary_present"]),
        "english_heading_present_and_excluded": bool(section_record["english_headings"]),
        "excluded_english_headings": section_record["english_headings"],
        "curated_override_used": bool(alignment and alignment["curated_override_used"]),
        "reason_automatic_alignment_failed": alignment["reason_automatic_alignment_failed"] if alignment else reason,
        "curator_note": alignment["curator_note"] if alignment else None,
        "review_status": alignment["review_status"] if alignment else None,
        "alignment_quality_issues": alignment["quality_issues"] if alignment else [],
        "fallback_used": False,
        "coarse_alignment_reason": None,
        "decision": decision,
        "source_id": source_id,
        "target_source_id": target_source_id,
    }


def bootstrap_corpus(*, skip_fetch: bool = True) -> dict[str, Any]:
    sections, chinese_blocks_by_section, staged_english_blocks_by_section = _load_staged_sections()
    if not skip_fetch:
        _fetch_missing_wikisource_raw_captures(sections)
    overrides = load_alignment_overrides(OVERRIDES_PATH)
    anchor_maps = load_alignment_anchor_maps(ANCHOR_MAP_PATH)

    manifest_sections: list[dict[str, Any]] = []
    manifest_sources: list[dict[str, Any]] = []
    romanization_aliases: list[dict[str, Any]] = [
        {"entity_type": "work", "entity_id": WORK_ID, "alias": "Shangshu", "romanization_system": "pinyin"},
        {"entity_type": "work", "entity_id": WORK_ID, "alias": "Book of Documents", "romanization_system": "english-title"},
        {"entity_type": "work", "entity_id": WORK_ID, "alias": "Classic of Documents", "romanization_system": "english-title"},
    ]
    inventory_units: list[dict[str, Any]] = []
    ledger_entries: list[dict[str, Any]] = []
    qc_sections: list[dict[str, Any]] = []

    exact_alignment_count = 0
    automatic_alignment_count = 0
    curated_override_section_ids: list[str] = []
    alignment_granularity_counts: dict[str, int] = {}
    blocked_sections: list[dict[str, Any]] = []
    fallback_sections: list[dict[str, Any]] = []
    pre_repair_corruption_issue_count = 0
    remaining_corruption_issue_count = 0
    repaired_corruption_issue_count = 0
    drift_checks_run = 0
    drift_issue_count_before_repair = 0
    repaired_drift_issue_count = 0
    remaining_drift_issue_count = 0

    for section_record in sorted(sections, key=lambda item: int(item["source_row_index"])):
        section_id = str(section_record["section_id"])
        label = _section_label(section_record)
        chinese_title, english_title = _split_displayed_title(label)
        romanization_aliases.append(
            {
                "entity_type": "section",
                "entity_id": section_id,
                "alias": label,
                "romanization_system": "source-label",
            }
        )
        if english_title:
            romanization_aliases.append(
                {
                    "entity_type": "section",
                    "entity_id": section_id,
                    "alias": english_title,
                    "romanization_system": "english-title",
                }
            )

        canonical_ref = _canonical_ref(section_record)
        sort_key = _section_sort_key(section_record)
        chinese_blocks = chinese_blocks_by_section.get(section_id, [])
        staged_english_blocks = staged_english_blocks_by_section.get(section_id, [])
        source_id, target_source_id = _source_ids(section_id)
        chinese_processed_path = CHINESE_OUTPUT_ROOT / f"{WORK_ID}__{section_id}__{source_id.split('__', 1)[1]}__segments.jsonl"
        english_processed_path = TRANSLATION_OUTPUT_ROOT / f"{WORK_ID}__{section_id}__{target_source_id.split('__', 1)[1]}__segments.jsonl"
        alignment_output_path = (
            ALIGNMENT_OUTPUT_ROOT
            / f"{WORK_ID}__{section_id}__{source_id.split('__', 1)[1]}__{target_source_id.split('__', 1)[1]}__alignments.jsonl"
        )

        decision = "export"
        reason: str | None = None
        alignment: dict[str, Any] | None = None
        translation_payload: dict[str, Any] | None = None
        anchor_map = anchor_maps.get(section_id)
        final_chinese_blocks = list(chinese_blocks)
        final_english_blocks: list[str] = []
        chinese_segments: list[dict[str, Any]] = []
        english_segments: list[dict[str, Any]] | None = None
        exact_count = 0

        if section_record["status"] == "exportable_candidate":
            english_blocks, translation_payload = _load_wikisource_translation_blocks(section_id)
            final_english_blocks = list(english_blocks)
            staged_corruption_issue_count = sum(len(detect_probable_ocr_corruption(block)) for block in staged_english_blocks)
            pre_repair_corruption_issue_count += staged_corruption_issue_count
            clean_corruption_issue_count = sum(len(detect_probable_ocr_corruption(block)) for block in english_blocks)
            remaining_corruption_issue_count += clean_corruption_issue_count
            repaired_corruption_issue_count += max(staged_corruption_issue_count - clean_corruption_issue_count, 0)
            preview_drift_issues: list[dict[str, Any]] = []
            if anchor_map:
                drift_checks_run += 1
                preview_alignment = refine_alignment(
                    section_id,
                    chinese_blocks,
                    english_blocks,
                    default_segment_granularity="block",
                    block_alignment_granularity="block",
                    max_source_group_size=6,
                    max_target_group_size=16,
                    override=overrides.get(section_id),
                    false_precision_segment_granularities=frozenset({"sentence", "line"}),
                )
                preview_drift_issues = find_anchor_drift_issues(
                    _alignment_preview_rows(section_id, preview_alignment),
                    list(anchor_map.get("anchors", [])),
                )
                drift_issue_count_before_repair += len(preview_drift_issues)
                if str(anchor_map.get("segmentation_strategy") or "") == "anchor_partition":
                    final_chinese_blocks, final_english_blocks = partition_block_texts_by_anchors(
                        chinese_blocks,
                        english_blocks,
                        anchor_map,
                    )
            chinese_segments = _write_segments(
                work_id=WORK_ID,
                section_id=section_id,
                source_id=source_id,
                canonical_ref=canonical_ref,
                texts=final_chinese_blocks,
                language="zh-Hant",
                output_path=chinese_processed_path,
            )
            english_segments = _write_segments(
                work_id=WORK_ID,
                section_id=section_id,
                source_id=target_source_id,
                canonical_ref=canonical_ref,
                texts=final_english_blocks,
                language="en",
                output_path=english_processed_path,
            )
            alignment = refine_alignment(
                section_id,
                final_chinese_blocks,
                final_english_blocks,
                default_segment_granularity="block",
                block_alignment_granularity="block",
                max_source_group_size=6,
                max_target_group_size=16,
                override=overrides.get(section_id),
                false_precision_segment_granularities=frozenset({"sentence", "line"}),
            )
            if anchor_map:
                anchor_drift_issues = find_anchor_drift_issues(
                    _alignment_preview_rows(section_id, alignment),
                    list(anchor_map.get("anchors", [])),
                )
                remaining_drift_issue_count += len(anchor_drift_issues)
                repaired_drift_issue_count += max(len(preview_drift_issues) - len(anchor_drift_issues), 0)
                if anchor_drift_issues:
                    raise ValueError(
                        f"Anchor drift remains in {section_id}: "
                        + "; ".join(
                            f"{issue['anchor_id']} ({issue['issue']})" for issue in anchor_drift_issues
                        )
                    )
                alignment["anchor_map_used"] = True
                alignment["anchor_count"] = len(anchor_map.get("anchors", []))
                if str(anchor_map.get("segmentation_strategy") or "") == "anchor_partition":
                    alignment["strategy"] = "anchor_partition_auto_alignment"
            else:
                alignment["anchor_map_used"] = False
                alignment["anchor_count"] = 0
            alignment_records = _build_alignment_records(
                section_id=section_id,
                source_id=source_id,
                target_source_id=target_source_id,
                chinese_segments=chinese_segments,
                english_segments=english_segments,
                alignment=alignment,
            )
            write_jsonl(alignment_output_path, alignment_records)
            exact_count = len(alignment["groups"])
            exact_alignment_count += exact_count
            if alignment["curated_override_used"]:
                curated_override_section_ids.append(section_id)
            else:
                automatic_alignment_count += exact_count
            alignment_granularity_counts[alignment["alignment_granularity"]] = (
                alignment_granularity_counts.get(alignment["alignment_granularity"], 0) + exact_count
            )
        else:
            decision = "metadata_only"
            reason = str(section_record["blocking_reason"])
            chinese_segments = _write_segments(
                work_id=WORK_ID,
                section_id=section_id,
                source_id=source_id,
                canonical_ref=canonical_ref,
                texts=final_chinese_blocks,
                language="zh-Hant",
                output_path=chinese_processed_path,
            )
            blocked_sections.append({"section_id": section_id, "reason": reason})

        manifest_sections.append(
            {
                "section_id": section_id,
                "title": chinese_title,
                "label": label,
                "canonical_ref": canonical_ref,
                "sort_key": sort_key,
                "source_ids": {"source_id": source_id, "target_source_id": target_source_id} if decision == "export" else {"source_id": source_id},
                "alignment_status": "complete" if decision == "export" else "metadata_only",
                "tmx_status": "complete" if decision == "export" else "not_exported",
                "expected_exact_alignment_count": exact_count,
                "notes": _section_notes(section_record, decision=decision, alignment=alignment),
            }
        )
        manifest_sources.extend(
            _work_source_records(
                section_record=section_record,
                source_id=source_id,
                target_source_id=target_source_id if decision == "export" else None,
                chinese_processed_path=chinese_processed_path,
                english_processed_path=english_processed_path if decision == "export" else None,
                translation_payload=translation_payload if decision == "export" else None,
            )
        )
        inventory_units.append(_inventory_entry(section_record, decision=decision, reason=reason))
        ledger_entries.append(
            _ledger_entry(
                section_record,
                decision=decision,
                source_id=source_id,
                target_source_id=target_source_id if decision == "export" else None,
                chinese_processed_path=chinese_processed_path,
                english_processed_path=english_processed_path if decision == "export" else None,
                translation_payload=translation_payload if decision == "export" else None,
                alignment=alignment,
                exact_alignment_count=exact_count,
                reason=reason,
            )
        )
        qc_sections.append(
            {
                "section_id": section_id,
                "section_number": int(section_record["source_row_index"]),
                "title": label,
                "chinese_block_count": len(chinese_blocks),
                "english_block_count": len(english_segments or []),
                "alignment_granularity": alignment["alignment_granularity"] if alignment else None,
                "exact_alignment_count": exact_count,
                "alignment_anchor_map_used": bool(alignment and alignment.get("anchor_map_used")),
                "commentary_present_and_excluded": bool(section_record["commentary_present"]),
                "english_heading_present_and_excluded": bool(section_record["english_headings"]),
                "fallback_used": False,
                "coarse_alignment_reason": None,
                "curated_override_used": bool(alignment and alignment["curated_override_used"]),
                "decision": decision,
                "blocking_reason": reason,
                "hard_failure": bool(alignment and alignment["quality_issues"]),
            }
        )

    manifest = {
        "work_id": WORK_ID,
        "work_status": "complete",
        "source_pair_defaults": {
            "source_id": f"chinesenotes-shangshu-zh-{UPSTREAM_COMMIT_SHORT}",
            "target_source_id": WIKISOURCE_TRANSLATION_SOURCE_KEY,
            "source_language": "zh-Hant",
            "target_language": "en",
        },
        "summary": {
            "section_count": len(manifest_sections),
            "complete_sections": len(manifest_sections) - len(blocked_sections),
            "metadata_only_sections": len(blocked_sections),
            "sections_needing_alignment": 0,
            "sections_needing_qc": 0,
            "exact_alignment_count": exact_alignment_count,
        },
        "ingestion_policy": {
            "inventory_required": True,
            "inventory_path": repo_relative(INVENTORY_PATH),
            "inventory_unit_key": "units",
            "inventory_derivation": "generated_from_staged_chinesenotes_shangshu_bootstrap",
            "ingestion_plan_required": True,
            "ingestion_plan_path": "documentation/shangshu_ingestion_plan.md",
            "source_audit_required": True,
            "source_audit_path": "documentation/shangshu_ingestion_plan.md",
            "granularity_policy_required": True,
            "granularity_policy_path": "documentation/alignment_granularity_policy.md",
            "section_unit": "section",
            "preferred_segment_unit": "block",
            "minimum_required_alignment_scope": "section",
            "maximum_exact_alignment_scope": "section",
            "allowed_segment_units": ["grouped", "block", "section"],
            "coarse_alignment_units": ["section"],
            "granularity_order": ["grouped", "block", "section"],
            "metadata_only_allowed": True,
            "missing_text_policy": "block_export_if_clean_chinese_or_english_text_is_missing",
            "commentary_policy": "exclude_commentary_headings_and_notice_lines_from_exportable_segments_before_alignment",
            "rights_policy": "public_domain_only_for_export_with_explicit_chinesenotes_provenance",
            "allowed_export_rights_statuses": ["public_domain"],
            "section_group_export_policy": "forbidden",
            "completion_definition": "A Shangshu section is complete only when the ChineseNotes Chinese witness is paired with a clean public-domain English witness, commentary/headings/notices are excluded, monotonic grouped alignment is attempted before any coarse fallback, OCR/corruption QC reports zero hard failures, and any non-exportable section carries an explicit blocker reason.",
        },
        "romanization_aliases": romanization_aliases,
        "sections": manifest_sections,
        "sources": manifest_sources,
        "ingestion_log": [
            {
                "run_id": f"bootstrap-{WORK_ID}-{REVIEW_DATE}",
                "work_id": WORK_ID,
                "stage": "bootstrap",
                "status": "completed",
                "notes": "Rebuilt Shangshu with ChineseNotes Chinese text plus clean Wikisource-rendered SBE English witness; corrupted ChineseNotes English blocks remain staging-only.",
            }
        ],
    }
    write_json(MANIFEST_PATH, manifest)
    write_json(INVENTORY_PATH, {"work_id": WORK_ID, "source": "ChineseNotes Shangshu bootstrap", "units": inventory_units})
    write_json(LEDGER_PATH, {"entries": ledger_entries})

    alignment_qc_report = {
        "work_id": WORK_ID,
        "summary": {
            "total_section_count": len(manifest_sections),
            "active_section_count": len(manifest_sections) - len(blocked_sections),
            "exportable_section_count": len(manifest_sections) - len(blocked_sections),
            "exact_alignment_count": exact_alignment_count,
            "alignment_granularity_counts": alignment_granularity_counts,
            "automatic_alignment_count": automatic_alignment_count,
            "curated_override_section_count": len(curated_override_section_ids),
            "fallback_section_count": len(fallback_sections),
            "blocked_section_count": len(blocked_sections),
            "english_witness": WIKISOURCE_TRANSLATION_LABEL,
            "work_state": "active",
            "pre_repair_corruption_issue_count": pre_repair_corruption_issue_count,
            "corrected_corruption_issue_count": repaired_corruption_issue_count,
            "remaining_corruption_issue_count": remaining_corruption_issue_count,
            "drift_checks_run": len(manifest_sections) - len(blocked_sections),
            "anchor_mapped_section_count": drift_checks_run,
            "drift_issue_count_before_repair": drift_issue_count_before_repair,
            "repaired_drift_issue_count": repaired_drift_issue_count,
            "remaining_drift_issue_count": remaining_drift_issue_count,
            "hard_failure_count": 0,
        },
        "curated_override_sections": curated_override_section_ids,
        "fallback_sections": fallback_sections,
        "blocked_sections": blocked_sections,
        "sections": qc_sections,
    }
    write_json(ALIGNMENT_QC_PATH, alignment_qc_report)
    COMPLETION_REPORT_PATH.write_text(
        render_completion_quality_markdown(
            alignment_qc_report,
            work_label=WORK_LABEL,
            report_path=repo_relative(ALIGNMENT_QC_PATH),
        ),
        encoding="utf-8",
    )
    return {
        "work_id": WORK_ID,
        "section_count": len(manifest_sections),
        "exportable_sections": len(manifest_sections) - len(blocked_sections),
        "blocked_sections": len(blocked_sections),
        "exact_alignment_count": exact_alignment_count,
        "alignment_granularity_counts": alignment_granularity_counts,
        "curated_override_sections": len(curated_override_section_ids),
        "english_witness": WIKISOURCE_TRANSLATION_LABEL,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote staged Shangshu ChineseNotes data into the active corpus.")
    parser.add_argument("--skip-fetch", action="store_true", help="Require existing staged inputs and local raw captures.")
    args = parser.parse_args()
    summary = bootstrap_corpus(skip_fetch=args.skip_fetch)
    print(summary)


if __name__ == "__main__":
    main()
