from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from common import write_json

UPSTREAM_REPOSITORY_URL = "https://github.com/alexamies/chinesenotes.com"
REPOSITORY_LEVEL_LICENSE = (
    "Apache-2.0 for source code; CC BY-SA 3.0 assumed for dictionary and text files "
    "per upstream license.txt"
)
ENGLISH_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'’-]{2,}\b")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
TRANSLATOR_ATTRIBUTION_RE = re.compile(
    r"English translation|English translations|translated by|trans\.|James Legge|Herbert Giles|Burton Watson|Eric L\. Hutton|W\. K\. Liao",
    re.IGNORECASE,
)
PUBLIC_DOMAIN_RE = re.compile(r"public domain|公有领域|公有領域", re.IGNORECASE)
IGNORE_STEMS = {
    "articles",
    "calligraphy",
    "chinese_fonts",
    "collections",
    "decorative_designs",
    "documents",
    "exclude",
    "grammar",
    "html-conversion",
    "korean",
    "laoshe",
    "library",
    "modern_articles",
    "yeshengtao",
}
STEM_TO_WORK_ID = {
    "daodejing": "laozi",
    "hanfeizi": "hanfeizi",
    "liezi": "liezi",
    "liji": "liji",
    "lunyu": "lunyu",
    "mengzi": "mengzi",
    "mozi": "mozi",
    "shangshu": "shangshu",
    "shiji": "shiji",
    "shijing": "shijing",
    "sunzibingfa": "sunzi",
    "xunzi": "xunzi",
    "yijing": "yijing",
    "zhuangzi": "zhuangzi",
    "zuozhuan": "zuozhuan",
}


def _normalize_field(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped or stripped == r"\N":
        return None
    return stripped


def _read_tabular_file(path: Path) -> tuple[list[str], list[list[str | None]]]:
    comments: list[str] = []
    rows: list[list[str | None]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        if raw_line.startswith("#"):
            comments.append(raw_line[1:].strip())
            continue
        parsed_row = next(csv.reader([raw_line], delimiter="\t"))
        rows.append([_normalize_field(cell) for cell in parsed_row])
    return comments, rows


def load_collections_index(source_root: Path) -> dict[str, dict[str, str | None]]:
    collections_path = source_root / "data" / "corpus" / "collections.csv"
    if not collections_path.exists():
        return {}
    _, rows = _read_tabular_file(collections_path)
    index: dict[str, dict[str, str | None]] = {}
    for row in rows:
        if not row:
            continue
        padded = row + [None] * (9 - len(row))
        index[padded[0] or ""] = {
            "collection_file": padded[0],
            "html_gloss_file": padded[1],
            "title": padded[2],
            "description": padded[3],
            "introduction_file": padded[4],
            "language_or_script": padded[5],
            "content_format": padded[6],
            "period": padded[7],
            "category": padded[8],
        }
    return index


def infer_work_id_candidate(stem: str) -> str | None:
    return STEM_TO_WORK_ID.get(stem)


def _git_value(source_root: Path, args: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=source_root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    value = result.stdout.strip()
    return value or None


def _read_text_sample(path: Path, *, max_chars: int = 12000) -> str:
    try:
        return path.read_text(encoding="utf-8")[:max_chars]
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_chars]


def _detect_text_signals(text: str) -> dict[str, Any]:
    english_word_count = len(ENGLISH_WORD_RE.findall(text))
    chinese_char_count = len(CJK_RE.findall(text))
    return {
        "english_appears_present": english_word_count >= 8 or bool(TRANSLATOR_ATTRIBUTION_RE.search(text)),
        "chinese_appears_present": chinese_char_count >= 8,
        "english_word_count": english_word_count,
        "chinese_char_count": chinese_char_count,
    }


def _sample_corpus_paths(
    source_root: Path,
    collection_meta: dict[str, str | None],
    rows: list[list[str | None]],
) -> tuple[list[str], list[str], str, str]:
    content_paths: list[str] = []
    for row in rows:
        if row and row[0]:
            content_paths.append(row[0])
        if len(content_paths) >= 3:
            break

    intro_path = collection_meta.get("introduction_file")
    sample_paths: list[str] = []
    if intro_path:
        sample_paths.append(intro_path)
    sample_paths.extend(path for path in content_paths if path not in sample_paths)

    intro_text = ""
    if intro_path:
        intro_file = source_root / "corpus" / intro_path
        if intro_file.exists():
            intro_text = _read_text_sample(intro_file)

    content_chunks: list[str] = []
    for relative_path in content_paths:
        file_path = source_root / "corpus" / relative_path
        if file_path.exists():
            content_chunks.append(_read_text_sample(file_path))
    return sample_paths, content_paths, intro_text, "\n\n".join(content_chunks)


def _classify_record(
    *,
    stem: str,
    language_or_script: str | None,
    category: str | None,
    english_appears_present: bool,
    chinese_appears_present: bool,
) -> str:
    if stem in IGNORE_STEMS:
        return "ignore"
    if language_or_script and language_or_script.lower().startswith("modern"):
        return "ignore"
    if language_or_script == "English":
        return "ignore"
    if infer_work_id_candidate(stem):
        return "candidate"
    if chinese_appears_present or english_appears_present:
        return "needs_review"
    if category in {"poetry", "historic", "literature", "Confucian", "Taoist", "Masters Literature"}:
        return "needs_review"
    return "ignore"


def _build_notes(
    *,
    description: str | None,
    sample_paths: list[str],
    content_format: str | None,
    period: str | None,
) -> str:
    parts = []
    if description:
        parts.append(description)
    if sample_paths:
        parts.append(f"Sampled corpus paths: {', '.join(sample_paths)}.")
    if content_format:
        parts.append(f"Format hint: {content_format}.")
    if period:
        parts.append(f"Period hint: {period}.")
    return " ".join(parts) if parts else "No additional notes."


def build_inventory(source_root: Path) -> dict[str, Any]:
    data_corpus_root = source_root / "data" / "corpus"
    corpus_root = source_root / "corpus"
    collections_index = load_collections_index(source_root)
    records: list[dict[str, Any]] = []

    for metadata_path in sorted(data_corpus_root.glob("*")):
        if metadata_path.is_dir():
            continue
        upstream_relative_path = str(metadata_path.relative_to(source_root))
        stem = metadata_path.stem
        collection_meta = collections_index.get(metadata_path.name, {})
        comments: list[str] = []
        rows: list[list[str | None]] = []
        if metadata_path.suffix.lower() == ".csv":
            comments, rows = _read_tabular_file(metadata_path)
        else:
            raw_line_count = len([line for line in metadata_path.read_text(encoding="utf-8").splitlines() if line.strip()])
            comments = []
            rows = [[None]] * raw_line_count

        sample_paths, content_paths, intro_text, content_text = _sample_corpus_paths(source_root, collection_meta, rows)
        content_signals = _detect_text_signals(content_text)
        provenance_text = "\n\n".join(
            part
            for part in (
                collection_meta.get("description") or "",
                intro_text,
                content_text[:4000],
            )
            if part
        )
        displayed_title = (
            collection_meta.get("title")
            or next((comment for comment in comments if comment and "Source file" not in comment), None)
            or (rows[0][2] if rows and len(rows[0]) > 2 else None)
        )
        language_or_script = collection_meta.get("language_or_script")
        category = collection_meta.get("category")
        status = _classify_record(
            stem=stem,
            language_or_script=language_or_script,
            category=category,
            english_appears_present=content_signals["english_appears_present"],
            chinese_appears_present=content_signals["chinese_appears_present"],
        )

        records.append(
            {
                "upstream_relative_path": upstream_relative_path,
                "filename": metadata_path.name,
                "displayed_title": displayed_title,
                "collection_or_category": category or (content_paths[0].split("/")[0] if content_paths else None),
                "language_or_script": language_or_script,
                "english_appears_present": content_signals["english_appears_present"],
                "chinese_appears_present": content_signals["chinese_appears_present"],
                "translator_attribution_appears": bool(TRANSLATOR_ATTRIBUTION_RE.search(provenance_text)),
                "public_domain_notice_appears": bool(PUBLIC_DOMAIN_RE.search(provenance_text)),
                "repository_level_license_assumed": REPOSITORY_LEVEL_LICENSE,
                "rough_line_or_segment_count": len(rows),
                "likely_chintransmem_work_id_candidate": infer_work_id_candidate(stem),
                "status": status,
                "notes": _build_notes(
                    description=collection_meta.get("description"),
                    sample_paths=sample_paths,
                    content_format=collection_meta.get("content_format"),
                    period=collection_meta.get("period"),
                ),
                "sample_corpus_paths": sample_paths,
            }
        )

    record_count = len(records)
    candidate_count = sum(1 for record in records if record["status"] == "candidate")
    needs_review_count = sum(1 for record in records if record["status"] == "needs_review")
    ignore_count = sum(1 for record in records if record["status"] == "ignore")
    english_candidate_count = sum(
        1 for record in records if record["status"] != "ignore" and record["english_appears_present"]
    )

    return {
        "upstream_repository": UPSTREAM_REPOSITORY_URL,
        "upstream_commit_sha": _git_value(source_root, ["rev-parse", "HEAD"]),
        "upstream_default_branch": _git_value(source_root, ["branch", "--show-current"]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inspected_roots": ["corpus", "data/corpus"],
        "license_summary": REPOSITORY_LEVEL_LICENSE,
        "summary": {
            "record_count": record_count,
            "candidate_count": candidate_count,
            "needs_review_count": needs_review_count,
            "ignore_count": ignore_count,
            "candidate_or_review_count": candidate_count + needs_review_count,
            "english_detected_in_candidate_or_review_records": english_candidate_count,
            "corpus_file_count": sum(1 for path in corpus_root.rglob("*") if path.is_file()),
            "data_corpus_file_count": sum(1 for path in data_corpus_root.rglob("*") if path.is_file()),
        },
        "records": records,
    }


def inventory_chinesenotes(source_root: Path, output_path: Path) -> dict[str, Any]:
    payload = build_inventory(source_root)
    write_json(output_path, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inventory a local ChineseNotes checkout without importing content.")
    parser.add_argument("--source-root", required=True, help="Path to a local chinesenotes.com checkout.")
    parser.add_argument("--output", required=True, help="Path to write the JSON-compatible YAML inventory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = inventory_chinesenotes(Path(args.source_root), Path(args.output))
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
