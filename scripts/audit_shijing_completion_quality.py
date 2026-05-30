from __future__ import annotations

import argparse
import json
from pathlib import Path

from shijing_quality import (
    QUALITY_JSON_PATH,
    QUALITY_MARKDOWN_PATH,
    SPOTCHECK_PACKET_PATH,
    build_shijing_quality_context,
    write_shijing_quality_outputs,
)


def audit_shijing_completion_quality(
    *,
    json_output_path: Path = QUALITY_JSON_PATH,
    markdown_output_path: Path = QUALITY_MARKDOWN_PATH,
    spotcheck_output_path: Path = SPOTCHECK_PACKET_PATH,
) -> dict[str, object]:
    context = build_shijing_quality_context()
    return write_shijing_quality_outputs(
        context,
        json_output_path=json_output_path,
        markdown_output_path=markdown_output_path,
        spotcheck_output_path=spotcheck_output_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Shijing completion quality and write review artifacts.")
    parser.add_argument("--json-output", type=Path, default=QUALITY_JSON_PATH)
    parser.add_argument("--markdown-output", type=Path, default=QUALITY_MARKDOWN_PATH)
    parser.add_argument("--spotcheck-output", type=Path, default=SPOTCHECK_PACKET_PATH)
    args = parser.parse_args()
    report = audit_shijing_completion_quality(
        json_output_path=args.json_output,
        markdown_output_path=args.markdown_output,
        spotcheck_output_path=args.spotcheck_output,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["hard_failure_count"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
