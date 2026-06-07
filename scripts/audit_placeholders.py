#!/usr/bin/env python3
"""
Audit auto-created placeholder sources and segments and write a diagnostic report.
Writes:
- logs/qc_reports/placeholder_integrity_audit.json
- documentation/placeholder_integrity_audit.md
"""
from pathlib import Path
import json
import sqlite3
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
# Ensure repository root is on sys.path so `import scripts.*` works from tests and tools
sys.path.insert(0, str(REPO_ROOT))
try:
    from scripts.common import METADATA_DIR, QC_REPORTS_DIR, DOCUMENTATION_DIR, load_json_compatible_yaml, load_sources, manifest_sections
except Exception:
    from common import METADATA_DIR, QC_REPORTS_DIR, DOCUMENTATION_DIR, load_json_compatible_yaml, load_sources, manifest_sections

DB_PATH = REPO_ROOT / 'db' / 'chinese_classics_tm.sqlite3'

OUT_JSON = QC_REPORTS_DIR / 'placeholder_integrity_audit.json'
OUT_MD = DOCUMENTATION_DIR / 'placeholder_integrity_audit.md'


def find_placeholder_sources(sources):
    placeholders = []
    for s in sources:
        notes = str(s.get('notes') or '')
        if re.search(r'placeholder', notes, flags=re.I) or re.search(r'auto-?created', notes, flags=re.I) or re.search(r'auto-?persisted', notes, flags=re.I):
            placeholders.append(s)
    return placeholders


def connect_db(path: Path):
    if not path.exists():
        return None
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def get_segments_for_source(conn, source_id):
    cur = conn.cursor()
    cur.execute('SELECT segment_id, section_id, source_id, notes FROM segments WHERE source_id = ?', (source_id,))
    return [dict(r) for r in cur.fetchall()]


def get_all_alignments_for_work(conn, work_id):
    cur = conn.cursor()
    cur.execute('SELECT alignment_id, section_id, source_id, target_source_id, chinese_segment_ids_json, translation_segment_ids_json FROM alignments WHERE work_id = ?', (work_id,))
    rows = []
    for r in cur.fetchall():
        row = dict(r)
        # parse JSON arrays safely
        for key in ('chinese_segment_ids_json', 'translation_segment_ids_json'):
            try:
                row[key] = json.loads(row.get(key) or '[]')
            except Exception:
                row[key] = []
        rows.append(row)
    return rows


def find_alignments_referencing_segments(alignments, segment_ids):
    matches = []
    segset = set(segment_ids)
    for a in alignments:
        if segset.intersection(a.get('chinese_segment_ids_json', []) or []) or segset.intersection(a.get('translation_segment_ids_json', []) or []):
            matches.append({'alignment_id': a['alignment_id'], 'section_id': a['section_id']})
    return matches


def main():
    METADATA_SOURCES = METADATA_DIR / 'sources.yml'
    if not METADATA_SOURCES.exists():
        print('metadata/sources.yml not found; aborting')
        sys.exit(1)
    sources = load_json_compatible_yaml(METADATA_SOURCES)
    placeholders = find_placeholder_sources(sources)

    conn = connect_db(DB_PATH)
    results = {'placeholders': [], 'placeholder_segments': [], 'summary': {}}
    total_placeholder_sources = 0
    placeholders_used_by_active = 0
    placeholders_used_only_by_blocked = 0

    # Preload manifests by work_id
    manifests = {}
    for s in sources:
        works = manifests.keys()
    # We'll lazily load manifests when needed

    for p in placeholders:
        total_placeholder_sources += 1
        work_id = p.get('work_id')
        source_id = p.get('source_id')
        processed_path = p.get('processed_path') or p.get('raw_path') or None
        processed_exists = False
        if processed_path:
            processed_exists = (REPO_ROOT / processed_path).exists()
        placeholder_entry = {
            'source_id': source_id,
            'work_id': work_id,
            'section_id': p.get('section_id'),
            'inferred_processed_path': processed_path,
            'processed_exists': processed_exists,
            'notes': p.get('notes'),
            'alignments': [],
            'appears_in_active_exportable_sections': False,
            'appears_only_in_blocked_sections': False,
            'recommended_action': None,
        }
        if conn:
            segments = get_segments_for_source(conn, source_id)
            segment_ids = [s['segment_id'] for s in segments]
            alignments = get_all_alignments_for_work(conn, work_id)
            refs = find_alignments_referencing_segments(alignments, segment_ids)
            # Also include alignments whose source_id or target_source_id equal the source_id
            direct_refs = [ {'alignment_id': a['alignment_id'], 'section_id': a['section_id']} for a in alignments if a.get('source_id')==source_id or a.get('target_source_id')==source_id]
            all_refs = { (r['alignment_id'], r['section_id']) for r in (refs + direct_refs) }
            placeholder_entry['alignments'] = [ {'alignment_id': r[0], 'section_id': r[1]} for r in sorted(all_refs) ]
            # Determine whether referenced sections are active/exportable
            active_flag = False
            blocked_flag = False
            if all_refs:
                manifest = None
                try:
                    manifest = load_json_compatible_yaml(METADATA_DIR / 'manifests' / f"{work_id}.yml")
                except Exception:
                    manifest = None
                section_tmx = {}
                if manifest:
                    for sec in manifest.get('sections', []):
                        section_tmx[sec.get('section_id')] = sec.get('tmx_status')
                for _aid, secid in all_refs:
                    status = section_tmx.get(secid, 'not_ready')
                    if status == 'complete':
                        active_flag = True
                    else:
                        blocked_flag = True
                placeholder_entry['appears_in_active_exportable_sections'] = active_flag
                placeholder_entry['appears_only_in_blocked_sections'] = (not active_flag and blocked_flag)
                if active_flag:
                    placeholder_entry['recommended_action'] = 'replace_with_authoritative_source_record_or_repair_alignment_references'
                    placeholders_used_by_active += 1
                elif blocked_flag:
                    placeholder_entry['recommended_action'] = 'safe_diagnostic_only_or_blocker_review'
                    placeholders_used_only_by_blocked += 1
                else:
                    placeholder_entry['recommended_action'] = 'safe_diagnostic_only'
        results['placeholders'].append(placeholder_entry)

    # Find placeholder segments (segments that were auto-created)
    if conn:
        cur = conn.cursor()
        cur.execute("SELECT segment_id, section_id, source_id, notes FROM segments WHERE lower(coalesce(notes,'')) LIKE '%placeholder%'")
        segrows = cur.fetchall()
        for r in segrows:
            results['placeholder_segments'].append({'segment_id': r['segment_id'], 'section_id': r['section_id'], 'source_id': r['source_id'], 'notes': r['notes']})

    results['summary'] = {
        'total_placeholder_sources_found': total_placeholder_sources,
        'placeholders_used_by_active_exportable_material': placeholders_used_by_active,
        'placeholders_used_by_blocked_only': placeholders_used_only_by_blocked,
        'placeholder_segments_found': len(results['placeholder_segments'])
    }

    QC_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCUMENTATION_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

    # Write a brief markdown summary
    md_lines = [
        '# Placeholder integrity audit\n',
        f"Total placeholder sources found: {results['summary']['total_placeholder_sources_found']}",
        f"Placeholders referenced by active/exportable material: {results['summary']['placeholders_used_by_active_exportable_material']}",
        f"Placeholders used only by blocked/metadata-only material: {results['summary']['placeholders_used_by_blocked_only']}",
        f"Placeholder segments found in DB: {results['summary']['placeholder_segments_found']}",
        '\n## Details\n'
    ]
    for p in results['placeholders']:
        md_lines.append(f"- source_id: {p['source_id']} (work: {p['work_id']}, section: {p['section_id']})")
        md_lines.append(f"  - processed_exists: {p['processed_exists']}")
        md_lines.append(f"  - appears_in_active_exportable_sections: {p['appears_in_active_exportable_sections']}")
        md_lines.append(f"  - appears_only_in_blocked_sections: {p['appears_only_in_blocked_sections']}")
        md_lines.append(f"  - recommended_action: {p['recommended_action']}")
        md_lines.append('')
    OUT_MD.write_text('\n'.join(md_lines), encoding='utf-8')
    print('Wrote', OUT_JSON, 'and', OUT_MD)


if __name__ == '__main__':
    main()
