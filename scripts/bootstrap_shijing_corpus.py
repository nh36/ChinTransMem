from __future__ import annotations

import argparse
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from common import (
    MANIFESTS_DIR,
    REPO_ROOT,
    clean_wikitext,
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
STANDALONE_TARGET_SOURCE_SUFFIX = "legge-sheking-1871"
SBE_TARGET_SOURCE_SUFFIX = "legge-sbe-v3-1879"

ZH_INDEX_URL = "https://zh.wikisource.org/wiki/詩經"
ZH_INDEX_RAW_PATH = RAW_DIR / f"{WORK_ID}__index__{SOURCE_SUFFIX}__raw.wikitext"
SBE_ALLPAGES_URL = (
    "https://en.wikisource.org/w/api.php?"
    "action=query&list=allpages&apprefix=Sacred%20Books%20of%20the%20East/Volume%203/The%20Shih"
    "&apnamespace=0&aplimit=max&format=json"
)
SBE_CATALOG_PATH = RAW_DIR / f"{WORK_ID}__catalog__{SBE_TARGET_SOURCE_SUFFIX}__allpages.json"

MAJOR_DIVISION_CODES = {
    "國風": "guofeng",
    "小雅": "xiaoya",
    "大雅": "daya",
    "頌": "song",
}

SUBDIVISION_CODES = {
    "周南": "zhounan",
    "召南": "zhaonan",
    "邶風": "beifeng",
    "鄘風": "yongfeng",
    "衛風": "weifeng",
    "王風": "wangfeng",
    "鄭風": "zhengfeng",
    "齊風": "qifeng",
    "魏風": "weifeng-state",
    "唐風": "tangfeng",
    "秦風": "qinfeng",
    "陳風": "chenfeng",
    "檜風": "kuaifeng",
    "曹風": "caofeng",
    "豳風": "binfeng",
    "鹿鳴之什": "luming",
    "南有嘉魚之什": "nanyoujiayu",
    "鴻雁之什": "hongyan",
    "鴻鴈之什": "hongyan",
    "節南山之什": "jienanshan",
    "谷風之什": "gufeng",
    "甫田之什": "futian",
    "魚藻之什": "yuzao",
    "文王之什": "wenwang",
    "生民之什": "shengmin",
    "蕩之什": "dang",
    "清廟之什": "qingmiao",
    "臣工之什": "chengong",
    "閔予小子之什": "minyuxiaozi",
    "周頌": "zhousong",
    "魯頌": "lusong",
    "商頌": "shangsong",
}

SECTION_CATALOG: list[dict[str, Any]] = [
    {
        "section_id": "guofeng-zhounan-001-guanju",
        "label": "關雎",
        "canonical_ref": "詩經·國風·周南·001",
        "sort_key": 1,
        "major_division": "國風",
        "subdivision": "周南",
        "poem_number": 1,
        "legge_section_alias": "Guan ju",
        "pinyin_alias": "Guān Jū",
        "zh_page_url": "https://zh.wikisource.org/wiki/詩經/關雎",
        "zh_section_heading": "國風‧周南‧關雎",
        "en_page_url": "https://en.wikisource.org/wiki/Guan_ju",
        "en_page_title": "Guan ju",
        "target_source_suffix": STANDALONE_TARGET_SOURCE_SUFFIX,
        "english_witness": "standalone_sheking",
    }
]


class BlockCenterExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.blocks: list[list[str]] = []
        self._capture_depth = 0
        self._current_parts: list[str] = []
        self._current_block_lines: list[str] = []
        self._current_paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "div" and "wst-block-center" in (attributes.get("class") or ""):
            self._capture_depth += 1
            return
        if self._capture_depth == 0:
            return
        if tag == "br":
            self._current_parts.append("\n")
        elif tag == "p":
            self._current_parts = []

    def handle_endtag(self, tag: str) -> None:
        if self._capture_depth == 0:
            return
        if tag == "p":
            paragraph = html.unescape("".join(self._current_parts))
            cleaned_lines = [normalize_english_line(line) for line in paragraph.splitlines()]
            lines = [line for line in cleaned_lines if line]
            if lines:
                self._current_paragraphs.append("\n".join(lines))
            self._current_parts = []
        elif tag == "div":
            self._capture_depth -= 1
            if self._capture_depth == 0 and self._current_paragraphs:
                self.blocks.append(self._current_paragraphs)
                self._current_paragraphs = []
                self._current_block_lines = []

    def handle_data(self, data: str) -> None:
        if self._capture_depth > 0:
            self._current_parts.append(data)


def request_text(url: str, *, retries: int = 5) -> str:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; CopilotCLI/1.0)"}
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                body = response.read().decode("utf-8")
                time.sleep(0.5)
                return body
        except urllib.error.HTTPError as exc:
            last_error = exc
            if attempt == retries - 1:
                break
            retry_after = exc.headers.get("Retry-After")
            if retry_after and retry_after.isdigit():
                time.sleep(int(retry_after))
            elif exc.code == 429:
                time.sleep(15 * (attempt + 1))
            else:
                time.sleep(2**attempt)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == retries - 1:
                break
            time.sleep(2**attempt)
    raise RuntimeError(f"Could not fetch {url}") from last_error


def fetch_cached_text(url: str, path: Path, *, skip_fetch: bool) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    if skip_fetch:
        raise FileNotFoundError(f"Missing cached raw capture: {path}")
    text = request_text(url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def fetch_rendered_html(page_title: str, path: Path, *, skip_fetch: bool) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    if skip_fetch:
        raise FileNotFoundError(f"Missing cached rendered HTML: {path}")
    params = urllib.parse.urlencode({"action": "parse", "page": page_title, "prop": "text", "format": "json"})
    html_text = request_text(f"https://en.wikisource.org/w/api.php?{params}")
    payload = json.loads(html_text)
    rendered_html = payload["parse"]["text"]["*"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(rendered_html, encoding="utf-8")
    return rendered_html


def source_ids(section: dict[str, Any]) -> tuple[str, str]:
    target_suffix = section["target_source_suffix"]
    return (f"{section['section_id']}__{SOURCE_SUFFIX}", f"{section['section_id']}__{target_suffix}")


def section_paths(section: dict[str, Any]) -> dict[str, Path]:
    base_name = f"{WORK_ID}__{section['section_id']}"
    target_suffix = section["target_source_suffix"]
    paths = {
        "zh_raw": RAW_DIR / f"{base_name}__{SOURCE_SUFFIX}__raw.wikitext",
        "en_raw": RAW_DIR / f"{base_name}__{target_suffix}__raw.wikitext",
        "zh_base": CHINESE_DIR / f"{base_name}__{SOURCE_SUFFIX}__base.txt",
        "zh_segments": CHINESE_DIR / f"{base_name}__{SOURCE_SUFFIX}__segments.jsonl",
        "en_text": TRANSLATION_DIR / f"{base_name}__{target_suffix}__translation.txt",
        "en_segments": TRANSLATION_DIR / f"{base_name}__{target_suffix}__segments.jsonl",
        "alignments": ALIGNMENT_DIR / f"{base_name}__{SOURCE_SUFFIX}__{target_suffix}__alignments.jsonl",
    }
    if section["english_witness"] == "sbe_shih":
        paths["en_rendered"] = RAW_DIR / f"{base_name}__{target_suffix}__rendered.html"
    return paths


def url_for_page(base_url: str, page_title: str) -> str:
    encoded_title = urllib.parse.quote(page_title.replace(" ", "_"), safe="/():")
    return f"{base_url}/{encoded_title}"


def fetch_sbe_page_titles(*, skip_fetch: bool) -> list[str]:
    raw_catalog = fetch_cached_text(SBE_ALLPAGES_URL, SBE_CATALOG_PATH, skip_fetch=skip_fetch)
    payload = json.loads(raw_catalog)
    return sorted(page["title"] for page in payload["query"]["allpages"] if "/Ode " in page["title"])


def parse_chinese_catalog(*, skip_fetch: bool) -> list[dict[str, Any]]:
    raw_text = fetch_cached_text(page_to_raw_url(ZH_INDEX_URL), ZH_INDEX_RAW_PATH, skip_fetch=skip_fetch)
    entries: list[dict[str, Any]] = []
    major_division = ""
    collection = ""
    subdivision = ""
    subdivision_counts: dict[tuple[str, str], int] = {}
    sort_key = 0
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        major_match = re.fullmatch(r"==\s*([^=]+?)\s*==", line)
        if major_match:
            major_label = clean_wikitext(major_match.group(1)).strip()
            if major_label in {"周頌", "魯頌", "商頌"}:
                major_division = "頌"
                collection = major_label
                subdivision = major_label
            else:
                major_division = major_label
                collection = major_label
            continue
        subdivision_match = re.search(r"'''([^']+)'''", line)
        if subdivision_match:
            subdivision = clean_wikitext(subdivision_match.group(1)).strip()
            continue
        if not line.startswith("#"):
            continue
        link_match = re.search(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]", line)
        if not link_match:
            continue
        target = link_match.group(1)
        label = clean_wikitext(link_match.group(2) or target.split("/")[-1]).strip()
        if target.startswith("/"):
            page_title = f"詩經{target}"
        elif target.startswith("詩經/"):
            page_title = target
        else:
            page_title = f"詩經/{target}"
        sort_key += 1
        key = (major_division, subdivision)
        subdivision_counts[key] = subdivision_counts.get(key, 0) + 1
        entries.append(
            {
                "sort_key": sort_key,
                "major_division": major_division,
                "collection": collection,
                "subdivision": subdivision,
                "label": label,
                "page_title": page_title,
                "page_url": url_for_page("https://zh.wikisource.org/wiki", page_title),
                "local_index": subdivision_counts[key],
                "canonical_ref": f"詩經·{major_division}·{subdivision}·{subdivision_counts[key]:03d}",
                "zh_section_heading": f"{major_division}‧{subdivision}‧{label}",
            }
        )
    return entries


def map_sbe_page_title(title: str, chinese_catalog: list[dict[str, Any]]) -> dict[str, Any]:
    guofeng_books = []
    xiaoya = []
    daya = []
    zhousong = []
    lusong = []
    shangsong = []
    current_subdivision = None
    current_book: list[dict[str, Any]] = []
    for poem in chinese_catalog:
        if poem["major_division"] == "國風":
            if poem["subdivision"] != current_subdivision:
                if current_book:
                    guofeng_books.append(current_book)
                current_book = []
                current_subdivision = poem["subdivision"]
            current_book.append(poem)
        elif poem["major_division"] == "小雅":
            xiaoya.append(poem)
        elif poem["major_division"] == "大雅":
            daya.append(poem)
        elif poem["collection"] == "周頌":
            zhousong.append(poem)
        elif poem["collection"] == "魯頌":
            lusong.append(poem)
        elif poem["collection"] == "商頌":
            shangsong.append(poem)
    if current_book:
        guofeng_books.append(current_book)

    states_match = re.search(r"Lessons from the States/Book (\d+)/Ode (\d+)", title)
    if states_match:
        book_index = int(states_match.group(1)) - 1
        ode_index = int(states_match.group(2)) - 1
        return guofeng_books[book_index][ode_index]

    xiaoya_match = re.search(r"The Minor Odes of the Kingdom/Decade (\d+)/Ode (\d+)", title)
    if xiaoya_match:
        absolute_index = (int(xiaoya_match.group(1)) - 1) * 10 + int(xiaoya_match.group(2)) - 1
        return xiaoya[absolute_index]

    daya_match = re.search(r"The Major Odes of the Kingdom/Decade (\d+)/Ode (\d+)", title)
    if daya_match:
        absolute_index = (int(daya_match.group(1)) - 1) * 10 + int(daya_match.group(2)) - 1
        return daya[absolute_index]

    zhousong_match = re.search(
        r"Odes of the Temple and the Altar/The Sacrificial Odes of Kâu/Decade (\d+)/Ode (\d+)",
        title,
    )
    if zhousong_match:
        absolute_index = (int(zhousong_match.group(1)) - 1) * 10 + int(zhousong_match.group(2)) - 1
        return zhousong[absolute_index]

    lusong_match = re.search(r"Odes of the Temple and the Altar/The Praise Odes of Lû/Ode (\d+)", title)
    if lusong_match:
        return lusong[int(lusong_match.group(1)) - 1]

    shangsong_match = re.search(
        r"Odes of the Temple and the Altar/The Sacrificial Odes of Shang/Ode (\d+)",
        title,
    )
    if shangsong_match:
        return shangsong[int(shangsong_match.group(1)) - 1]

    raise ValueError(f"Could not map SBE page title: {title}")


def build_section_seed(poem: dict[str, Any], *, en_page_title: str, english_witness: str) -> dict[str, Any]:
    if poem["sort_key"] == 1 and english_witness == "standalone_sheking":
        return dict(SECTION_CATALOG[0])
    section_id = (
        f"{MAJOR_DIVISION_CODES[poem['major_division']]}-"
        f"{SUBDIVISION_CODES[poem['subdivision']]}-"
        f"{poem['local_index']:03d}"
    )
    target_suffix = STANDALONE_TARGET_SOURCE_SUFFIX if english_witness == "standalone_sheking" else SBE_TARGET_SOURCE_SUFFIX
    en_page_url = (
        "https://en.wikisource.org/wiki/Guan_ju"
        if english_witness == "standalone_sheking"
        else url_for_page("https://en.wikisource.org/wiki", en_page_title)
    )
    return {
        "section_id": section_id,
        "label": poem["label"],
        "canonical_ref": poem["canonical_ref"],
        "sort_key": poem["sort_key"],
        "major_division": poem["major_division"],
        "subdivision": poem["subdivision"],
        "poem_number": poem["local_index"],
        "legge_section_alias": poem["label"],
        "zh_page_url": poem["page_url"],
        "zh_section_heading": poem["zh_section_heading"],
        "en_page_url": en_page_url,
        "en_page_title": en_page_title,
        "target_source_suffix": target_suffix,
        "english_witness": english_witness,
    }


def build_section_catalog(*, skip_fetch: bool) -> list[dict[str, Any]]:
    chinese_catalog = parse_chinese_catalog(skip_fetch=skip_fetch)
    mapped_sections = [dict(SECTION_CATALOG[0])]
    seen_sort_keys = {1}
    for page_title in fetch_sbe_page_titles(skip_fetch=skip_fetch):
        poem = map_sbe_page_title(page_title, chinese_catalog)
        if poem["sort_key"] in seen_sort_keys:
            continue
        mapped_sections.append(build_section_seed(poem, en_page_title=page_title, english_witness="sbe_shih"))
        seen_sort_keys.add(poem["sort_key"])
    mapped_sections.sort(key=lambda section: section["sort_key"])
    return mapped_sections


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


def extract_named_wikitext_section(raw_text: str, heading: str) -> str:
    lines = raw_text.splitlines()
    heading_regex = re.compile(rf"^(=+)\s*{re.escape(heading)}\s*\1\s*$")
    start_index = None
    heading_level = None
    for index, line in enumerate(lines):
        match = heading_regex.match(line.strip())
        if match:
            start_index = index + 1
            heading_level = len(match.group(1))
            break
    if start_index is None:
        return raw_text
    section_lines: list[str] = []
    for line in lines[start_index:]:
        stripped = line.strip()
        heading_match = re.match(r"^(=+)\s*[^=].*?\s*\1\s*$", stripped)
        if heading_match and heading_level is not None and len(heading_match.group(1)) <= heading_level:
            break
        section_lines.append(line)
    return "\n".join(section_lines)


def extract_chinese_poem_blocks(raw_text: str, section: dict[str, Any]) -> list[str]:
    section_text = extract_named_wikitext_section(raw_text, section["zh_section_heading"])
    if "<poem" in section_text:
        return clean_poem_blocks(extract_poem_markup(section_text))
    blocks: list[list[str]] = []
    current_block: list[str] = []
    for raw_line in section_text.splitlines():
        stripped = raw_line.strip()
        if stripped.startswith(":"):
            cleaned = clean_wikitext(stripped.lstrip(":").strip()).strip()
            if not cleaned:
                if current_block:
                    blocks.append(current_block)
                    current_block = []
                continue
            if cleaned.startswith("《") and cleaned.endswith("句。"):
                continue
            current_block.append(cleaned)
        elif not stripped and current_block:
            blocks.append(current_block)
            current_block = []
    if current_block:
        blocks.append(current_block)
    cleaned_blocks = ["\n".join(block) for block in blocks if block]
    if not cleaned_blocks:
        raise ValueError(f"Could not extract Chinese stanza blocks for {section['section_id']}")
    return cleaned_blocks


def normalize_english_line(line: str) -> str:
    normalized = html.unescape(line)
    normalized = normalized.replace("\xa0", " ")
    normalized = re.sub(r"\[\s*\d+\s*\]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def normalize_transliteration_spacing(text: str) -> str:
    tokens = text.split()
    if not tokens:
        return ""
    combined: list[str] = []
    current = tokens[0]
    for token in tokens[1:]:
        if len(current) <= 2 and len(token) <= 2 and re.search(r"[A-Za-zÀ-ÿ]", current) and re.search(r"[A-Za-zÀ-ÿ]", token):
            current += token
            continue
        combined.append(current)
        current = token
    combined.append(current)
    return " ".join(combined)


def extract_rendered_text_lines(rendered_html: str) -> list[str]:
    stripped = re.sub(r"<style.*?</style>", " ", rendered_html, flags=re.S)
    stripped = re.sub(r"<sup.*?</sup>", " ", stripped, flags=re.S)
    stripped = re.sub(r"<br ?/?>", "\n", stripped)
    stripped = re.sub(r"<[^>]+>", " ", stripped)
    lines = [normalize_english_line(line) for line in stripped.splitlines()]
    return [line for line in lines if line]


def extract_sbe_poem_blocks(rendered_html: str) -> list[str]:
    extractor = BlockCenterExtractor()
    extractor.feed(rendered_html)
    if not extractor.blocks:
        raise ValueError("Could not find a rendered Shijing poem block.")
    best_block = max(extractor.blocks, key=lambda paragraphs: sum(len(paragraph.splitlines()) for paragraph in paragraphs))
    return [paragraph for paragraph in best_block if paragraph]


def extract_english_poem_blocks(
    section: dict[str, Any],
    *,
    raw_text: str,
    rendered_html: str | None,
) -> tuple[list[str], str, str | None, str | None]:
    if section["english_witness"] == "standalone_sheking":
        return extract_english_poem_blocks_from_raw(raw_text), section["legge_section_alias"], section.get("pinyin_alias"), None
    if rendered_html is None:
        raise ValueError(f"Missing rendered HTML for SBE witness {section['section_id']}")
    lines = extract_rendered_text_lines(rendered_html)
    heading_line = next((line for line in lines if line.startswith("Ode ")), "")
    title_match = re.match(r"^Ode\s+\d+(?:,\s*([^\.]+))?\.\s*(.*?)\.\s*$", heading_line)
    selection_text = title_match.group(1).strip() if title_match and title_match.group(1) else None
    legge_title = normalize_transliteration_spacing(title_match.group(2).strip()) if title_match else section["label"]
    pinyin_match = next(
        (
            re.match(rf"^(.+?)\s*\(\s*{re.escape(section['label'])}\s*\)\s+corresponds to", line)
            for line in lines
            if f"({section['label']})" in line or f"( {section['label']} )" in line
        ),
        None,
    )
    pinyin_alias = pinyin_match.group(1).strip() if pinyin_match else None
    return extract_sbe_poem_blocks(rendered_html), legge_title, pinyin_alias, selection_text


def extract_english_poem_blocks_from_raw(raw_text: str) -> list[str]:
    poem_matches = re.findall(r"<poem[^>]*>(.*?)</poem>", raw_text, flags=re.S)
    for poem_markup in poem_matches:
        blocks = clean_poem_blocks(poem_markup)
        if blocks:
            return blocks
    raise ValueError("Could not find an English <poem> block with content.")


def poem_lines(blocks: list[str]) -> list[str]:
    return [line for block in blocks for line in block.splitlines() if line.strip()]


def chunk_lines(lines: list[str], chunk_size: int) -> list[str]:
    return ["\n".join(lines[index : index + chunk_size]) for index in range(0, len(lines), chunk_size)]


def parse_stanza_selection(selection_text: str | None) -> list[int] | None:
    if not selection_text or "Stanza" not in selection_text:
        return None
    stanza_text = re.sub(r"^Stanzas?\s+", "", selection_text).strip()
    stanza_text = stanza_text.replace(" and ", ", ")
    stanza_text = stanza_text.replace(";", ",")
    selected: list[int] = []
    for fragment in [piece.strip() for piece in stanza_text.split(",") if piece.strip()]:
        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", fragment)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            selected.extend(range(start, end + 1))
            continue
        number_match = re.fullmatch(r"(\d+)", fragment)
        if number_match:
            selected.append(int(number_match.group(1)))
    return selected or None


def select_chinese_excerpt(chinese_blocks: list[str], stanza_selection: list[int] | None) -> list[str]:
    if stanza_selection is None:
        return chinese_blocks
    max_index = max(stanza_selection)
    if max_index > len(chinese_blocks):
        return chinese_blocks
    return [chinese_blocks[index - 1] for index in stanza_selection]


def build_segments_and_alignments(
    section: dict[str, Any],
    chinese_source_id: str,
    english_source_id: str,
    chinese_blocks: list[str],
    english_blocks: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], int, str, str]:
    if len(chinese_blocks) == len(english_blocks):
        segment_type = "stanza"
        chinese_segments_text = chinese_blocks
        english_segments_text = english_blocks
        section_note = "Aligned stanza by stanza from matching Chinese and English poem blocks."
    elif len(english_blocks) > len(chinese_blocks):
        chinese_lines = poem_lines(chinese_blocks)
        chunk_size = len(chinese_lines) // len(english_blocks) if english_blocks else 0
        if chunk_size and len(chinese_lines) % len(english_blocks) == 0 and chunk_size <= 8:
            segment_type = "stanza"
            chinese_segments_text = chunk_lines(chinese_lines, chunk_size)
            english_segments_text = english_blocks
            section_note = (
                f"Aligned at stanza level by splitting the Chinese text into {chunk_size}-line units to match "
                "Legge's printed stanza blocks."
            )
        else:
            segment_type = "poem"
            chinese_segments_text = ["\n\n".join(chinese_blocks)]
            english_segments_text = ["\n\n".join(english_blocks)]
            section_note = "Fell back to poem-level alignment because Chinese and English stanza counts did not match cleanly."
    else:
        segment_type = "poem"
        chinese_segments_text = ["\n\n".join(chinese_blocks)]
        english_segments_text = ["\n\n".join(english_blocks)]
        section_note = "Fell back to poem-level alignment because Chinese and English stanza counts did not match cleanly."

    chinese_segments: list[dict[str, Any]] = []
    english_segments: list[dict[str, Any]] = []
    alignments: list[dict[str, Any]] = []

    for order, (zh_text, en_text) in enumerate(zip(chinese_segments_text, english_segments_text), start=1):
        chinese_segment_id = f"{WORK_ID}__{section['section_id']}__{order:03d}__{SOURCE_SUFFIX}"
        english_segment_id = f"{WORK_ID}__{section['section_id']}__{order:03d}__{section['target_source_suffix']}"
        canonical_ref = f"{section['canonical_ref']}.{order}"
        confidence = 0.99 if segment_type == "stanza" else 0.95
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
                    f"{WORK_ID}__{section['section_id']}__{order:03d}__{SOURCE_SUFFIX}__{section['target_source_suffix']}"
                ),
                "work_id": WORK_ID,
                "section_id": section["section_id"],
                "source_id": chinese_source_id,
                "target_source_id": english_source_id,
                "alignment_type": "exact_or_near_exact",
                "confidence": confidence,
                "chinese_segment_ids": [chinese_segment_id],
                "translation_segment_ids": [english_segment_id],
                "notes": f"{segment_type.title()}-level Shijing alignment for {section['label']} block {order}.",
            }
        )

    alignments.append(
        {
            "alignment_id": (
                f"{WORK_ID}__{section['section_id']}__section-group__{SOURCE_SUFFIX}__{section['target_source_suffix']}"
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
    return chinese_segments, english_segments, alignments, len(chinese_segments), segment_type, section_note


def build_sources(section: dict[str, Any], paths: dict[str, Path]) -> list[dict[str, Any]]:
    chinese_source_id, english_source_id = source_ids(section)
    english_notes = (
        "Processed segmentation preserves the stanza blocks printed on Legge's standalone She King page."
        if section["english_witness"] == "standalone_sheking"
        else (
            "Untouched raw capture preserves the transcluded English Wikisource page, while segmentation uses cached "
            "rendered HTML because the raw wikitext is only a <pages> transclusion."
        )
    )
    if section.get("stanza_selection"):
        english_notes += f" This witness is excerpted and only covers stanza selection {section['stanza_selection']}."
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
                "Untouched raw capture comes from the page's action=raw export; processed segmentation keeps the poem text "
                "separate from translation and extracts subsection headings when multiple poems share a Chinese page."
            ),
        },
        {
            "source_id": english_source_id,
            "work_id": WORK_ID,
            "section_id": section["section_id"],
            "language_code": "en",
            "source_kind": "translation",
            "citation": (
                f"James Legge, The She King, '{section['legge_section_alias']}', English Wikisource, accessed {ACCESS_DATE}."
                if section["english_witness"] == "standalone_sheking"
                else (
                    f"James Legge, The Shih, Sacred Books of the East, Vol. III, '{section['legge_section_alias']}', "
                    f"English Wikisource, accessed {ACCESS_DATE}."
                )
            ),
            "source_url": section["en_page_url"],
            "raw_path": str(paths["en_raw"].relative_to(REPO_ROOT)),
            "processed_path": str(paths["en_segments"].relative_to(REPO_ROOT)),
            "rights_status": "public_domain",
            "author_or_translator_ids": ["james-legge"],
            "notes": english_notes,
        },
    ]


def write_section_files(section: dict[str, Any], *, skip_fetch: bool) -> dict[str, Any]:
    paths = section_paths(section)
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)

    zh_raw = fetch_cached_text(page_to_raw_url(section["zh_page_url"]), paths["zh_raw"], skip_fetch=skip_fetch)
    resolved_zh_page_url, zh_raw = resolve_redirect_raw(section["zh_page_url"], zh_raw)
    section["zh_page_url"] = resolved_zh_page_url
    paths["zh_raw"].write_text(zh_raw, encoding="utf-8")

    en_raw = fetch_cached_text(page_to_raw_url(section["en_page_url"]), paths["en_raw"], skip_fetch=skip_fetch)
    paths["en_raw"].write_text(en_raw, encoding="utf-8")

    rendered_html = None
    if section["english_witness"] == "sbe_shih":
        rendered_html = fetch_rendered_html(section["en_page_title"], paths["en_rendered"], skip_fetch=skip_fetch)

    chinese_source_id, english_source_id = source_ids(section)
    chinese_blocks = extract_chinese_poem_blocks(zh_raw, section)
    english_blocks, legge_title, pinyin_alias, selection_text = extract_english_poem_blocks(
        section,
        raw_text=en_raw,
        rendered_html=rendered_html,
    )
    stanza_selection = parse_stanza_selection(selection_text)
    chinese_blocks = select_chinese_excerpt(chinese_blocks, stanza_selection)
    chinese_segments, english_segments, alignments, exact_alignment_count, segment_type, alignment_note = (
        build_segments_and_alignments(
            section,
            chinese_source_id,
            english_source_id,
            chinese_blocks,
            english_blocks,
        )
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
        "legge_section_alias": legge_title,
        "pinyin_alias": pinyin_alias or section.get("pinyin_alias"),
        "stanza_selection": selection_text,
        "notes": alignment_note,
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

    for section_seed in build_section_catalog(skip_fetch=skip_fetch):
        result = write_section_files(dict(section_seed), skip_fetch=skip_fetch)
        section = result["section"]
        processed_sections.append(section)
        all_sources.extend(result["sources"])
        total_exact_alignments += section["expected_exact_alignment_count"]
        romanization_aliases.append(
            {
                "entity_type": "section",
                "entity_id": section["section_id"],
                "alias": section["legge_section_alias"],
                "romanization_system": "Legge-title",
            }
        )
        if section.get("pinyin_alias"):
            romanization_aliases.append(
                {
                    "entity_type": "section",
                    "entity_id": section["section_id"],
                    "alias": section["pinyin_alias"],
                    "romanization_system": "pinyin",
                }
            )
        ingestion_log.append(
            {
                "run_id": f"bootstrap-{section['section_id']}-{ACCESS_DATE.replace('-', '')}",
                "work_id": WORK_ID,
                "section_id": section["section_id"],
                "status": "complete",
                "source_ids": [section["source_ids"]["source_id"], section["source_ids"]["target_source_id"]],
                "notes": (
                    f"Bootstrap Shijing generation for {section['label']} with "
                    f"{section['expected_exact_alignment_count']} exact {section['segment_type']} alignments."
                ),
            }
        )

    manifest = {
        "work_id": WORK_ID,
        "work_status": "partial",
        "source_pair_defaults": {
            "source_id": SOURCE_SUFFIX,
            "target_source_id": SBE_TARGET_SOURCE_SUFFIX,
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
