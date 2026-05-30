from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from common import DEFAULT_DB_PATH, DEFAULT_WORK_ID, connect_db, load_work_manifest, manifest_sections
from export_corpus import load_exact_alignment_rows


def manifest_section_map(work_id: str) -> dict[str, dict[str, object]]:
    return {section["section_id"]: section for section in manifest_sections(work_id)}


class CorpusApiHandler(BaseHTTPRequestHandler):
    db_path = DEFAULT_DB_PATH

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._write_json({"status": "ok", "db_path": str(self.db_path)})
            return
        if parsed.path == "/works":
            self._write_json({"works": self._list_works()})
            return
        if parsed.path == "/sections":
            self._write_json(
                {
                    "sections": [
                        self._serialize_manifest_section(section)
                        for section in manifest_sections(DEFAULT_WORK_ID)
                    ]
                }
            )
            return

        work_sections_prefix = "/works/"
        if parsed.path.startswith(work_sections_prefix):
            segments = [segment for segment in parsed.path.strip("/").split("/") if segment]
            if len(segments) == 3 and segments[0] == "works" and segments[2] == "sections":
                work_id = segments[1]
                try:
                    self._write_json({"work_id": work_id, "sections": self._list_sections(work_id)})
                except FileNotFoundError:
                    self._write_json({"error": "not_found"}, status=404)
                return
            if len(segments) == 5 and segments[0] == "works" and segments[2] == "sections" and segments[4] == "passages":
                work_id = segments[1]
                section_id = segments[3]
                self._write_work_passages(work_id, section_id)
                return

        if parsed.path.startswith("/sections/") and parsed.path.endswith("/passages"):
            section_id = parsed.path.removeprefix("/sections/").removesuffix("/passages").strip("/")
            self._write_work_passages(DEFAULT_WORK_ID, section_id, compatibility_route=True)
            return

        self._write_json({"error": "not_found"}, status=404)

    def _list_works(self) -> list[dict[str, object]]:
        with connect_db(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT work_id, canonical_title, english_title, work_type, language_code, default_citation, notes
                FROM works
                ORDER BY work_id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def _list_sections(self, work_id: str) -> list[dict[str, object]]:
        load_work_manifest(work_id)
        return [self._serialize_manifest_section(section) for section in manifest_sections(work_id)]

    def _serialize_manifest_section(self, section: dict[str, object]) -> dict[str, object]:
        return {
            "section_id": section["section_id"],
            "work_id": section["work_id"],
            "label": section["label"],
            "canonical_ref": section["canonical_ref"],
            "alignment_status": section.get("alignment_status", "metadata_only"),
            "tmx_status": section.get("tmx_status", "metadata_only"),
            "expected_exact_alignment_count": section.get("expected_exact_alignment_count", 0),
        }

    def _write_work_passages(self, work_id: str, section_id: str, *, compatibility_route: bool = False) -> None:
        try:
            section_map = manifest_section_map(work_id)
        except FileNotFoundError:
            self._write_json({"error": "not_found"}, status=404)
            return
        if section_id not in section_map:
            self._write_json({"error": "not_found"}, status=404)
            return
        payload = {
            "work_id": work_id,
            "section_id": section_id,
            "rows": load_exact_alignment_rows(self.db_path, work_id, section_id),
        }
        if compatibility_route:
            payload.pop("work_id")
        self._write_json(payload)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _write_json(self, payload: dict[str, object], status: int = 200) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def serve_api(db_path: Path | str = DEFAULT_DB_PATH, host: str = "127.0.0.1", port: int = 8000) -> None:
    handler = type("ConfiguredCorpusApiHandler", (CorpusApiHandler,), {"db_path": Path(db_path)})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Serving corpus API on http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a read-only API for the translation-memory corpus.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", default=8000, type=int, help="Port to bind.")
    args = parser.parse_args()

    serve_api(args.db, args.host, args.port)


if __name__ == "__main__":
    main()
