from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

REPO_ROOT = Path(__file__).resolve().parent.parent
METADATA_DIR = REPO_ROOT / "metadata"
MANIFEST_PATH = METADATA_DIR / "corpus_manifest.yml"
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


def load_corpus_manifest() -> dict[str, Any]:
    return load_json_compatible_yaml(MANIFEST_PATH)


def manifest_sections() -> list[dict[str, Any]]:
    return list(load_corpus_manifest()["sections"])


def manifest_section(section_id: str) -> dict[str, Any]:
    for section in manifest_sections():
        if section["section_id"] == section_id:
            return section
    raise KeyError(f"Unknown section_id: {section_id}")


def section_source_ids(section: dict[str, Any]) -> tuple[str, str]:
    source_ids = section["source_ids"]
    return source_ids["source_id"], source_ids["target_source_id"]


def section_export_stem(section_id: str) -> str:
    return f"{DEFAULT_WORK_ID}__{section_id}__aligned_passages"


def section_export_paths(section_id: str) -> dict[str, Path]:
    stem = section_export_stem(section_id)
    return {
        "jsonl": REPO_ROOT / "corpus" / "exports" / "jsonl" / f"{stem}.jsonl",
        "csv": REPO_ROOT / "corpus" / "exports" / "csv" / f"{stem}.csv",
        "tmx": REPO_ROOT / "corpus" / "exports" / "tmx" / f"{stem}.tmx",
        "tmx_validation": REPO_ROOT / "logs" / "qc_reports" / f"{DEFAULT_WORK_ID}__{section_id}__tmx_validation.json",
    }


def corpus_export_paths() -> dict[str, Path]:
    return {
        "jsonl": DEFAULT_CORPUS_JSONL_EXPORT,
        "csv": DEFAULT_CORPUS_CSV_EXPORT,
        "tmx": DEFAULT_CORPUS_TMX_EXPORT,
        "tmx_validation": DEFAULT_CORPUS_TMX_VALIDATION_REPORT,
    }


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
