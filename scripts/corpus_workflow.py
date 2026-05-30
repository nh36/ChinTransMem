from __future__ import annotations

import argparse
import json

from common import DEFAULT_DB_PATH, DEFAULT_WORK_ID, corpus_export_paths
from export_corpus import export_corpus
from import_corpus import import_corpus
from init_db import initialize_database
from qc_corpus import run_qc
from validate_tmx import validate_all_tmx_exports


def run_workflow(work_id: str = DEFAULT_WORK_ID) -> dict[str, object]:
    export_paths = corpus_export_paths(work_id)
    qc_report_path = export_paths["tmx_validation"].with_name(f"{work_id}__corpus_qc.json")
    initialize_database(DEFAULT_DB_PATH)
    import_summary = import_corpus(DEFAULT_DB_PATH)
    export_summary = export_corpus(DEFAULT_DB_PATH, work_id=work_id)
    tmx_validation_summary = validate_all_tmx_exports(DEFAULT_DB_PATH, export_paths["tmx_validation"], work_id=work_id)
    qc_summary = run_qc(DEFAULT_DB_PATH, qc_report_path, work_id=work_id)
    return {
        "db_path": str(DEFAULT_DB_PATH),
        "work_id": work_id,
        "import": import_summary,
        "export": export_summary,
        "tmx_validation": tmx_validation_summary,
        "qc_status": qc_summary["status"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full corpus workflow for a work manifest.")
    parser.add_argument("--work-id", default=DEFAULT_WORK_ID, help="Which work manifest to export and QC.")
    args = parser.parse_args()
    print(json.dumps(run_workflow(args.work_id), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
