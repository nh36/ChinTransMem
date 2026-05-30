from __future__ import annotations

import argparse
from pathlib import Path

from common import DEFAULT_DB_PATH, REPO_ROOT, connect_db

SCHEMA_PATH = REPO_ROOT / "db" / "schema.sql"
ALIGNMENT_COLUMN_MIGRATIONS = {
    "alignment_granularity": "ALTER TABLE alignments ADD COLUMN alignment_granularity TEXT",
    "section_unit": "ALTER TABLE alignments ADD COLUMN section_unit TEXT",
    "segment_type": "ALTER TABLE alignments ADD COLUMN segment_type TEXT",
    "is_coarse_alignment": "ALTER TABLE alignments ADD COLUMN is_coarse_alignment INTEGER NOT NULL DEFAULT 0",
    "coarse_alignment_reason": "ALTER TABLE alignments ADD COLUMN coarse_alignment_reason TEXT",
    "source_segment_count": "ALTER TABLE alignments ADD COLUMN source_segment_count INTEGER",
    "target_segment_count": "ALTER TABLE alignments ADD COLUMN target_segment_count INTEGER",
}


def initialize_database(db_path: Path | str = DEFAULT_DB_PATH) -> Path:
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    with connect_db(db_path) as connection:
        connection.executescript(schema_sql)
        existing_columns = {
            row["name"] for row in connection.execute("PRAGMA table_info(alignments)").fetchall()
        }
        for column_name, statement in ALIGNMENT_COLUMN_MIGRATIONS.items():
            if column_name not in existing_columns:
                connection.execute(statement)
    return Path(db_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the SQLite schema for the ChinTransMem corpus.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Path to the SQLite database file.")
    args = parser.parse_args()

    db_path = initialize_database(args.db)
    print(f"Initialized schema at {db_path}")


if __name__ == "__main__":
    main()
