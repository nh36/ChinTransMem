from __future__ import annotations

import json
from pathlib import Path

from audit_work_coverage import audit_work_coverage


def audit_shijing_coverage(
    json_output_path: Path | None = None,
    markdown_output_path: Path | None = None,
) -> dict[str, object]:
    return audit_work_coverage(
        "shijing",
        json_output_path=json_output_path,
        markdown_output_path=markdown_output_path,
    )


def main() -> None:
    report = audit_shijing_coverage()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
