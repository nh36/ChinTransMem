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

from common import DEFAULT_DB_PATH, PILOT_SECTION_ID
from export_pilot import load_exact_alignment_rows


class PilotApiHandler(BaseHTTPRequestHandler):
    db_path = DEFAULT_DB_PATH

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._write_json({"status": "ok", "db_path": str(self.db_path)})
            return

        if parsed.path == f"/sections/{PILOT_SECTION_ID}/passages":
            self._write_json(
                {
                    "section_id": PILOT_SECTION_ID,
                    "rows": load_exact_alignment_rows(self.db_path),
                }
            )
            return

        self._write_json({"error": "not_found"}, status=404)

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
    handler = type("ConfiguredPilotApiHandler", (PilotApiHandler,), {"db_path": Path(db_path)})
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Serving pilot API on http://{host}:{port}")
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve a thin read-only API for the Lunyu plus Legge pilot.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    parser.add_argument("--port", default=8000, type=int, help="Port to bind.")
    args = parser.parse_args()

    serve_api(args.db, args.host, args.port)


if __name__ == "__main__":
    main()
