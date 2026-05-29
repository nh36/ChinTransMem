from __future__ import annotations

import json

from common import (
    DEFAULT_CSV_EXPORT,
    DEFAULT_DB_PATH,
    DEFAULT_JSONL_EXPORT,
    DEFAULT_QC_REPORT,
    DEFAULT_TMX_EXPORT,
    DEFAULT_TMX_VALIDATION_REPORT,
)
from export_pilot import export_pilot
from import_lunyu_legge_pilot import import_pilot
from init_db import initialize_database
from qc_pilot import run_qc
from validate_tmx import validate_tmx_export


def run_workflow() -> dict[str, object]:
    initialize_database(DEFAULT_DB_PATH)
    import_summary = import_pilot(DEFAULT_DB_PATH)
    export_summary = export_pilot(DEFAULT_DB_PATH, DEFAULT_JSONL_EXPORT, DEFAULT_CSV_EXPORT, DEFAULT_TMX_EXPORT)
    tmx_validation_summary = validate_tmx_export(DEFAULT_DB_PATH, DEFAULT_TMX_EXPORT, DEFAULT_TMX_VALIDATION_REPORT)
    qc_summary = run_qc(DEFAULT_DB_PATH, DEFAULT_QC_REPORT)
    return {
        "db_path": str(DEFAULT_DB_PATH),
        "import": import_summary,
        "export": export_summary,
        "tmx_validation": tmx_validation_summary,
        "qc_status": qc_summary["status"],
        "many_to_many_alignment_ids": qc_summary["many_to_many_alignment_ids"],
    }


def main() -> None:
    print(json.dumps(run_workflow(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
