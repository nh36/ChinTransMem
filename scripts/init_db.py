from __future__ import annotations

import argparse
from pathlib import Path

from common import DEFAULT_DB_PATH, REPO_ROOT, connect_db

SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"


def initialize_database(db_path: Path | str = DEFAULT_DB_PATH) -> Path:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect_db(db_path) as connection:
        connection.executescript(schema_sql)
    return Path(db_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the SQLite schema for the ChinTransMem pilot.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file.")
    args = parser.parse_args()

    db_path = initialize_database(args.db)
    print(f"Initialized schema at {db_path}")


if __name__ == "__main__":
    main()
