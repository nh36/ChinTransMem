from __future__ import annotations

import json

from common import DEFAULT_DB_PATH, DEFAULT_CORPUS_QC_REPORT, DEFAULT_CORPUS_TMX_VALIDATION_REPORT
from export_corpus import export_corpus
from import_corpus import import_corpus
from init_db import initialize_database
from qc_corpus import run_qc
from validate_tmx import validate_all_tmx_exports


def run_workflow() -> dict[str, object]:
    initialize_database(DEFAULT_DB_PATH)
    import_summary = import_corpus(DEFAULT_DB_PATH)
    export_summary = export_corpus(DEFAULT_DB_PATH)
    tmx_validation_summary = validate_all_tmx_exports(DEFAULT_DB_PATH, DEFAULT_CORPUS_TMX_VALIDATION_REPORT)
    qc_summary = run_qc(DEFAULT_DB_PATH, DEFAULT_CORPUS_QC_REPORT)
    return {
        "db_path": str(DEFAULT_DB_PATH),
        "import": import_summary,
        "export": export_summary,
        "tmx_validation": tmx_validation_summary,
        "qc_status": qc_summary["status"],
    }


def main() -> None:
    print(json.dumps(run_workflow(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
