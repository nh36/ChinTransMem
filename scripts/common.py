from __future__ import annotations

import html
import hashlib
import json
import re
import sqlite3
import urllib.parse
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
METADATA_DIR = REPO_ROOT / "metadata"
MANIFESTS_DIR = METADATA_DIR / "manifests"
DOCUMENTATION_DIR = REPO_ROOT / "documentation"
QC_REPORTS_DIR = REPO_ROOT / "logs" / "qc_reports"
AI_REVIEWS_DIR = REPO_ROOT / "logs" / "ai_reviews"
CANDIDATE_CORPUS_DIR = REPO_ROOT / "corpus" / "candidates"
LEGACY_DEFAULT_MANIFEST_PATH = METADATA_DIR / "corpus_manifest.yml"
DEFAULT_DB_PATH = REPO_ROOT / "db" / "chinese_classics_tm.sqlite3"
DEFAULT_WORK_ID = "lunyu"
DEFAULT_SOURCE_LANGUAGE = "zh-Hant"
DEFAULT_TARGET_LANGUAGE = "en"
DEFAULT_CORPUS_EXPORT_STEM = f"{DEFAULT_WORK_ID}__all__aligned_passages"
DEFAULT_CORPUS_JSONL_EXPORT = REPO_ROOT / "corpus" / "exports" / "jsonl" / f"{DEFAULT_CORPUS_EXPORT_STEM}.jsonl"
DEFAULT_CORPUS_CSV_EXPORT = REPO_ROOT / "corpus" / "exports" / "csv" / f"{DEFAULT_CORPUS_EXPORT_STEM}.csv"
DEFAULT_CORPUS_TMX_EXPORT = REPO_ROOT / "corpus" / "exports" / "tmx" / f"{DEFAULT_CORPUS_EXPORT_STEM}.tmx"
DEFAULT_CORPUS_QC_REPORT = REPO_ROOT / "logs" / "qc_reports" / f"{DEFAULT_WORK_ID}__corpus_qc.json"
DEFAULT_CORPUS_TMX_VALIDATION_REPORT = REPO_ROOT / "logs" / "qc_reports" / f"{DEFAULT_WORK_ID}__corpus_tmx_validation.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@contextmanager
def connect_db(db_path: Path | str) -> Iterator[sqlite3.Connection]:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def load_json_compatible_yaml(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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
    index = 0
    while index < len(body):
        if body[index : index + 2] == "{{":
            braces += 1
            current.append("{{")
            index += 2
            continue
        if body[index : index + 2] == "}}" and braces > 0:
            braces -= 1
            current.append("}}")
            index += 2
            continue
        if body[index : index + 2] == "[[":
            brackets += 1
            current.append("[[")
            index += 2
            continue
        if body[index : index + 2] == "]]" and brackets > 0:
            brackets -= 1
            current.append("]]")
            index += 2
            continue
        if body[index] == "|" and braces == 0 and brackets == 0:
            args.append("".join(current))
            current = []
            index += 1
            continue
        current.append(body[index])
        index += 1
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


def _normalize_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    work_id = str(manifest["work_id"])
    normalized = dict(manifest)
    normalized["sections"] = [
        {**section, "work_id": section.get("work_id", work_id)}
        for section in manifest.get("sections", [])
    ]
    return normalized


def work_manifest_path(work_id: str = DEFAULT_WORK_ID) -> Path:
    candidate = MANIFESTS_DIR / f"{work_id}.yml"
    if candidate.exists():
        return candidate
    if work_id == DEFAULT_WORK_ID:
        return LEGACY_DEFAULT_MANIFEST_PATH
    raise FileNotFoundError(candidate)


def load_work_manifest(work_id: str = DEFAULT_WORK_ID) -> dict[str, Any]:
    return _normalize_manifest(load_json_compatible_yaml(work_manifest_path(work_id)))


def load_work_manifests() -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    seen_work_ids: set[str] = set()
    if MANIFESTS_DIR.exists():
        for path in sorted(MANIFESTS_DIR.glob("*.yml")):
            manifest = load_json_compatible_yaml(path)
            normalized = _normalize_manifest(manifest)
            manifests.append(normalized)
            seen_work_ids.add(str(normalized["work_id"]))
    if DEFAULT_WORK_ID not in seen_work_ids and LEGACY_DEFAULT_MANIFEST_PATH.exists():
        manifests.append(_normalize_manifest(load_json_compatible_yaml(LEGACY_DEFAULT_MANIFEST_PATH)))
    manifests.sort(key=lambda manifest: (manifest["work_id"] != DEFAULT_WORK_ID, manifest["work_id"]))
    return manifests


def load_corpus_manifest() -> dict[str, Any]:
    return load_work_manifest(DEFAULT_WORK_ID)


def manifest_sections(work_id: str = DEFAULT_WORK_ID) -> list[dict[str, Any]]:
    return list(load_work_manifest(work_id)["sections"])


def resolve_repo_path(path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return REPO_ROOT / candidate


def manifest_ingestion_policy(work_id: str = DEFAULT_WORK_ID, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    current_manifest = load_work_manifest(work_id) if manifest is None else manifest
    policy = current_manifest.get("ingestion_policy")
    if not isinstance(policy, dict):
        raise KeyError(f"Manifest {current_manifest['work_id']} is missing an ingestion_policy block.")
    return policy


def work_inventory_path(work_id: str = DEFAULT_WORK_ID, manifest: dict[str, Any] | None = None) -> Path:
    policy = manifest_ingestion_policy(work_id, manifest)
    return resolve_repo_path(policy["inventory_path"])


def load_work_inventory(work_id: str = DEFAULT_WORK_ID, manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    inventory_path = work_inventory_path(work_id, manifest)
    return load_json_compatible_yaml(inventory_path)


def inventory_units(
    inventory_payload: dict[str, Any],
    work_id: str = DEFAULT_WORK_ID,
    manifest: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    policy = manifest_ingestion_policy(work_id, manifest)
    unit_key = str(policy.get("inventory_unit_key", "units"))
    units = inventory_payload.get(unit_key)
    if not isinstance(units, list):
        raise KeyError(f"Inventory for {work_id} is missing the '{unit_key}' unit list.")
    return list(units)


def work_coverage_paths(work_id: str = DEFAULT_WORK_ID) -> dict[str, Path]:
    return {
        "json": QC_REPORTS_DIR / f"{work_id}__coverage_audit.json",
        "markdown": DOCUMENTATION_DIR / f"{work_id}_coverage_audit.md",
    }


def work_granularity_report_path(work_id: str = DEFAULT_WORK_ID) -> Path:
    return QC_REPORTS_DIR / f"{work_id}__granularity_qc.json"


def load_sources(work_id: str | None = None) -> list[dict[str, Any]]:
    sources = load_json_compatible_yaml(METADATA_DIR / "sources.yml")
    if work_id is None:
        return list(sources)
    return [source for source in sources if source["work_id"] == work_id]


def manifest_section(section_id: str, work_id: str = DEFAULT_WORK_ID) -> dict[str, Any]:
    for section in manifest_sections(work_id):
        if section["section_id"] == section_id:
            return section
    raise KeyError(f"Unknown section_id: {section_id}")


def section_source_ids(section: dict[str, Any]) -> tuple[str, str]:
    source_ids = section["source_ids"]
    return source_ids["source_id"], source_ids["target_source_id"]


def work_export_stem(work_id: str = DEFAULT_WORK_ID) -> str:
    return f"{work_id}__all__aligned_passages"


def work_batch_mapping_path(work_id: str = DEFAULT_WORK_ID) -> Path:
    return METADATA_DIR / f"{work_id}_batch_mapping.yml"


def load_work_batch_mapping(work_id: str = DEFAULT_WORK_ID) -> dict[str, Any]:
    path = work_batch_mapping_path(work_id)
    if not path.exists():
        return {"work_id": work_id, "batches": []}
    return load_json_compatible_yaml(path)


def scope_key(work_id: str = DEFAULT_WORK_ID, batch_id: str | None = None) -> str:
    if not batch_id:
        return work_id
    return f"{work_id}__{batch_id}"


def scope_report_stem(work_id: str = DEFAULT_WORK_ID, batch_id: str | None = None) -> str:
    if not batch_id:
        return work_id
    return f"{work_id}__{batch_id}"


def section_export_stem(section_id: str, work_id: str = DEFAULT_WORK_ID) -> str:
    return f"{work_id}__{section_id}__aligned_passages"


def section_export_paths(section_id: str, work_id: str = DEFAULT_WORK_ID) -> dict[str, Path]:
    stem = section_export_stem(section_id, work_id)
    return {
        "jsonl": REPO_ROOT / "corpus" / "exports" / "jsonl" / f"{stem}.jsonl",
        "csv": REPO_ROOT / "corpus" / "exports" / "csv" / f"{stem}.csv",
        "tmx": REPO_ROOT / "corpus" / "exports" / "tmx" / f"{stem}.tmx",
        "tmx_validation": REPO_ROOT / "logs" / "qc_reports" / f"{work_id}__{section_id}__tmx_validation.json",
    }


def corpus_export_paths(work_id: str = DEFAULT_WORK_ID) -> dict[str, Path]:
    stem = work_export_stem(work_id)
    return {
        "jsonl": REPO_ROOT / "corpus" / "exports" / "jsonl" / f"{stem}.jsonl",
        "csv": REPO_ROOT / "corpus" / "exports" / "csv" / f"{stem}.csv",
        "tmx": REPO_ROOT / "corpus" / "exports" / "tmx" / f"{stem}.tmx",
        "tmx_validation": REPO_ROOT / "logs" / "qc_reports" / f"{work_id}__corpus_tmx_validation.json",
    }


def candidate_work_dir(work_id: str = DEFAULT_WORK_ID, batch_id: str | None = None) -> Path:
    root = CANDIDATE_CORPUS_DIR / work_id
    if batch_id:
        return root / batch_id
    return root


def candidate_section_export_paths(
    section_id: str,
    work_id: str = DEFAULT_WORK_ID,
    batch_id: str | None = None,
) -> dict[str, Path]:
    stem = section_export_stem(section_id, work_id)
    root = candidate_work_dir(work_id, batch_id)
    return {
        "jsonl": root / "exports" / "jsonl" / f"{stem}.jsonl",
        "csv": root / "exports" / "csv" / f"{stem}.csv",
        "tmx": root / "exports" / "tmx" / f"{stem}.tmx",
        "tmx_validation": root / "reports" / "tmx_validation" / f"{stem}.json",
    }


def candidate_corpus_export_paths(work_id: str = DEFAULT_WORK_ID, batch_id: str | None = None) -> dict[str, Path]:
    stem = work_export_stem(work_id)
    root = candidate_work_dir(work_id, batch_id)
    report_stem = scope_report_stem(work_id, batch_id)
    return {
        "jsonl": root / "exports" / "jsonl" / f"{stem}.jsonl",
        "csv": root / "exports" / "csv" / f"{stem}.csv",
        "tmx": root / "exports" / "tmx" / f"{stem}.tmx",
        "tmx_validation": root / "reports" / "tmx_validation" / f"{report_stem}__corpus_tmx_validation.json",
    }


def candidate_state_path(work_id: str = DEFAULT_WORK_ID, batch_id: str | None = None) -> Path:
    return candidate_work_dir(work_id, batch_id) / "candidate_state.json"


def candidate_alignment_snapshot_path(work_id: str = DEFAULT_WORK_ID, batch_id: str | None = None) -> Path:
    return candidate_work_dir(work_id, batch_id) / "reports" / f"{scope_report_stem(work_id, batch_id)}__alignment_qc.json"


def repair_log_suffix(work_id: str = DEFAULT_WORK_ID) -> str:
    if work_id == "shiji":
        return "witness_repair_log"
    return "ocr_repair_log"


def candidate_repair_log_path(work_id: str = DEFAULT_WORK_ID, batch_id: str | None = None) -> Path:
    return candidate_work_dir(work_id, batch_id) / "repair_logs" / f"{scope_report_stem(work_id, batch_id)}__{repair_log_suffix(work_id)}.json"


def candidate_qc_report_path(work_id: str = DEFAULT_WORK_ID, batch_id: str | None = None) -> Path:
    return QC_REPORTS_DIR / f"{scope_report_stem(work_id, batch_id)}__candidate_qc.json"


def candidate_ai_review_path(work_id: str = DEFAULT_WORK_ID, batch_id: str | None = None) -> Path:
    return AI_REVIEWS_DIR / f"{scope_report_stem(work_id, batch_id)}__alignment_review.jsonl"


def candidate_report_path(work_id: str = DEFAULT_WORK_ID, batch_id: str | None = None) -> Path:
    if not batch_id:
        return DOCUMENTATION_DIR / f"{work_id}_candidate_report.md"
    return DOCUMENTATION_DIR / f"{work_id}_{batch_id}_candidate_report.md"


def read_jsonl(path: Path | str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def write_jsonl(path: Path | str, records: Iterable[dict[str, Any]]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(json.dumps(record, ensure_ascii=False) for record in records)
    output_path.write_text(f"{payload}\n", encoding="utf-8")


def write_json(path: Path | str, payload: Any) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_relative(path: Path | str) -> str:
    return str(Path(path).resolve().relative_to(REPO_ROOT))
