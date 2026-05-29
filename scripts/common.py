from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "db" / "chinese_classics_tm.sqlite3"
PILOT_WORK_ID = "lunyu"
PILOT_SECTION_ID = "book-01-xueer"
PILOT_SOURCE_ID = "zhwikisource-20260529"
PILOT_TARGET_SOURCE_ID = "legge-cc-v1-1893"
PILOT_SOURCE_LANGUAGE = "zh-Hant"
PILOT_TARGET_LANGUAGE = "en"
DEFAULT_JSONL_EXPORT = REPO_ROOT / "corpus" / "exports" / "jsonl" / f"{PILOT_WORK_ID}__{PILOT_SECTION_ID}__aligned_passages.jsonl"
DEFAULT_CSV_EXPORT = REPO_ROOT / "corpus" / "exports" / "csv" / f"{PILOT_WORK_ID}__{PILOT_SECTION_ID}__aligned_passages.csv"
DEFAULT_TMX_EXPORT = REPO_ROOT / "corpus" / "exports" / "tmx" / f"{PILOT_WORK_ID}__{PILOT_SECTION_ID}__aligned_passages.tmx"
DEFAULT_QC_REPORT = REPO_ROOT / "logs" / "qc_reports" / f"{PILOT_WORK_ID}__{PILOT_SECTION_ID}__pilot_qc.json"
DEFAULT_TMX_VALIDATION_REPORT = REPO_ROOT / "logs" / "qc_reports" / f"{PILOT_WORK_ID}__{PILOT_SECTION_ID}__tmx_validation.json"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect_db(db_path: Path | str) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def load_json_compatible_yaml(path: Path | str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


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
