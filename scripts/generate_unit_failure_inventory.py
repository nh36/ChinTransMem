#!/usr/bin/env python3
"""
Run unit tests programmatically and write a failure inventory JSON and markdown summary.
Writes:
- logs/qc_reports/unit_failure_inventory.json
- documentation/unit_failure_inventory.md
"""
import json
import re
import sys
from pathlib import Path
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
# Ensure repository root is on sys.path so tests can `import scripts.*`
sys.path.insert(0, str(REPO_ROOT))
try:
    from scripts.common import QC_REPORTS_DIR, DOCUMENTATION_DIR
except Exception:
    # fallback when script executed from scripts/ context
    from common import QC_REPORTS_DIR, DOCUMENTATION_DIR

OUT_JSON = QC_REPORTS_DIR / 'unit_failure_inventory.json'
OUT_MD = DOCUMENTATION_DIR / 'unit_failure_inventory.md'

KNOWN_WORK_IDS = ['shiji', 'mozi', 'shangshu', 'liji', 'yijing', 'shijing', 'lunyu', 'mengzi']


def classify_failure_text(text: str) -> dict:
    t = text.lower()
    failure_type = 'other'
    if 'placeholder' in t:
        failure_type = 'placeholder_dependency'
    elif 'segment' in t or 'segmentation' in t:
        failure_type = 'segmentation_mismatch'
    elif 'manifest' in t and 'export' in t:
        failure_type = 'manifest_vs_export_count_mismatch'
    elif 'qc' in t and 'export' in t:
        failure_type = 'qc_vs_export_count_mismatch'
    elif 'expected' in t and '!=' in t:
        failure_type = 'manifest_vs_export_count_mismatch'
    return {'failure_type': failure_type}


def extract_counts(text: str):
    # Try to find X != Y or (expected X, got Y)
    m = re.search(r"(\d+) != (\d+)", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"expected\D*(\d+)\D*got\D*(\d+)", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def find_work_id(text: str):
    t = text.lower()
    for w in KNOWN_WORK_IDS:
        if w in t:
            return w
    return None


def main():
    loader = unittest.TestLoader()
    suite = loader.discover('tests', pattern='test_*.py')
    runner = unittest.TextTestRunner(stream=sys.stdout, verbosity=2)
    result = runner.run(suite)

    failures = []
    for testcase, tb in result.failures + result.errors:
        tid = getattr(testcase, 'id', lambda: str(testcase))()
        text = tb
        expected, actual = extract_counts(text)
        work_id = find_work_id(text) or find_work_id(tid)
        classification = classify_failure_text(text)
        affected_files = []
        for line in text.splitlines():
            m = re.search(r"File \"(.*?)/(.*\.py)\", line", line)
            if m:
                affected_files.append(m.group(2))
        failures.append({
            'test_name': tid,
            'work_id': work_id,
            'failure_type': classification['failure_type'],
            'expected_count': expected,
            'actual_count': actual,
            'affected_files': sorted(set(affected_files)),
            'traceback_snippet': '\n'.join(text.splitlines()[-6:]),
            'raw_traceback': text,
        })

    OUT = {
        'total_tests_run': result.testsRun,
        'failures': failures,
        'failure_count': len(failures),
        'errors': len(result.errors),
        'skipped': len(result.skipped),
    }

    QC_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCUMENTATION_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(OUT, ensure_ascii=False, indent=2), encoding='utf-8')

    # Markdown summary
    md_lines = [
        '# Unit failure inventory\n',
        f"Total tests run: {OUT['total_tests_run']}",
        f"Failure count: {OUT['failure_count']}",
        '',
    ]
    for f in failures:
        md_lines.append(f"- Test: {f['test_name']}")
        md_lines.append(f"  - work_id: {f['work_id']}")
        md_lines.append(f"  - failure_type: {f['failure_type']}")
        md_lines.append(f"  - expected: {f['expected_count']}, actual: {f['actual_count']}")
        if f['affected_files']:
            md_lines.append(f"  - affected_files: {', '.join(f['affected_files'])}")
        md_lines.append('')

    OUT_MD.write_text('\n'.join(md_lines), encoding='utf-8')
    print('Wrote', OUT_JSON, 'and', OUT_MD)


if __name__ == '__main__':
    main()
