from __future__ import annotations

import argparse
import csv
import re
import urllib.request
from pathlib import Path
from typing import Any

from chinesenotes_alignment import render_completion_quality_markdown
from common import REPO_ROOT, load_json_compatible_yaml, repo_relative, sha256_file, write_json, write_jsonl
from ingest_chinesenotes_work import PUBLIC_DOMAIN_RE, TRANSLATOR_ATTRIBUTION_RE, _extract_notice_lines, _parse_section_body

WORK_ID = "mozi"
WORK_LABEL = "Mozi"
CANONICAL_TITLE_ZH = "墨子"
CANONICAL_TITLE_EN = "Mozi"
UPSTREAM_REPOSITORY_URL = "https://github.com/alexamies/chinesenotes.com"
UPSTREAM_COMMIT_SHA = "1f6b1d3e7a40b6886a4b943c898125639e993544"
UPSTREAM_COMMIT_SHORT = UPSTREAM_COMMIT_SHA[:7]
UPSTREAM_INDEX_PATH = "data/corpus/mozi.csv"
UPSTREAM_INTRO_PATH = "corpus/mozi/mozi000.txt"
UPSTREAM_RAW_BASE_URL = f"https://raw.githubusercontent.com/alexamies/chinesenotes.com/{UPSTREAM_COMMIT_SHA}/"
UPSTREAM_BLOB_BASE_URL = f"{UPSTREAM_REPOSITORY_URL}/blob/{UPSTREAM_COMMIT_SHA}/"
REVIEW_DATE = "2026-06-01"
RAW_DIR = REPO_ROOT / "corpus" / "raw" / "chinesenotes"
STAGING_DIR = REPO_ROOT / "corpus" / "staging" / "chinesenotes" / WORK_ID
ZH_SEGMENTS_DIR = REPO_ROOT / "corpus" / "processed" / "chinese_base_texts"
MANIFEST_PATH = REPO_ROOT / "metadata" / "manifests" / f"{WORK_ID}.yml"
INVENTORY_PATH = REPO_ROOT / "metadata" / f"{WORK_ID}_inventory.yml"
LEDGER_PATH = REPO_ROOT / "metadata" / f"{WORK_ID}_verification_ledger.yml"
ALIGNMENT_QC_PATH = REPO_ROOT / "logs" / "qc_reports" / f"{WORK_ID}__alignment_qc.json"
COMPLETION_REPORT_PATH = REPO_ROOT / "documentation" / f"{WORK_ID}_completion_quality.md"
CHINESENOTES_WORK_MAPPING_PATH = REPO_ROOT / "metadata" / "chinesenotes_work_mapping.yml"

TITLE_RE = re.compile(r"^(卷[^ ]+)\s+(.+?)\s+Book\s+\d+\s+-\s+(.+)$")

WORK_LEVEL_BLOCKER_NOTE = (
    "No clean exportable public-domain English witness was verified for Mozi. "
    "ChineseNotes embeds English in only two chapter files and that mirror remains tied to the upstream text-file licence; "
    "English Wikisource hosts Translation:Mozi as a CC BY-SA / GFDL community translation; "
    "Chinese Text Project mixes Yi-Pao Mei's 1929 translation with A. C. Graham's 1978 Canons and military-chapter translations; "
    "Mei (1893-1960) is not yet worldwide public domain. "
    "Mozi therefore remains metadata-only until a clean public-domain chapter witness is captured and verified."
)

ENGLISH_WITNESS_SUMMARY = (
    "No exportable public-domain English witness verified; ChineseNotes English is incomplete, "
    "Wikisource Translation:Mozi is CC BY-SA/GFDL, and Chinese Text Project mixes Mei 1929 with Graham 1978."
)


def _slugify_ascii(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", value).strip("-").lower()
    return slug or "section"


def _fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8")


def _ensure_text_capture(path: Path, url: str, *, skip_fetch: bool) -> None:
    if path.exists():
        return
    if skip_fetch:
        raise FileNotFoundError(f"Missing local raw capture: {repo_relative(path)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_fetch_text(url), encoding="utf-8")


def _load_source_rows(csv_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    row_index = 0
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter="\t")
        for raw_row in reader:
            if not raw_row or raw_row[0].startswith("#"):
                continue
            row_index += 1
            padded = raw_row + [""] * (3 - len(raw_row))
            rows.append(
                {
                    "row_index": row_index,
                    "source_relative_path": padded[0].strip(),
                    "html_relative_path": padded[1].strip(),
                    "displayed_title": padded[2].strip(),
                }
            )
    return rows


def _parse_displayed_title(displayed_title: str) -> tuple[str, str, str]:
    match = TITLE_RE.match(displayed_title.strip())
    if match is not None:
        return match.group(1), match.group(2), match.group(3)
    english_title = displayed_title.split(" - ", 1)[1].strip() if " - " in displayed_title else displayed_title.strip()
    return "", displayed_title.strip(), english_title


def _section_id(row_index: int, english_title: str) -> str:
    return f"{WORK_ID}-{row_index:03d}-{_slugify_ascii(english_title)}"


def _section_raw_capture_path(section_id: str) -> Path:
    return RAW_DIR / f"{WORK_ID}__{section_id}__chinesenotes-{UPSTREAM_COMMIT_SHORT}__raw.txt"


def _segment_record(
    *,
    section_id: str,
    source_id: str,
    block_index: int,
    text: str,
) -> dict[str, Any]:
    canonical_ref = f"{CANONICAL_TITLE_ZH} {section_id.split('-', 2)[1]}.{block_index}"
    return {
        "segment_id": f"{source_id}__seg-{block_index:03d}",
        "work_id": WORK_ID,
        "section_id": section_id,
        "source_id": source_id,
        "segment_type": "block",
        "segment_order": block_index,
        "canonical_ref": canonical_ref,
        "text_original": text,
        "text_normalized": text,
        "notes": "",
    }


def _metadata_only_reason(section_record: dict[str, Any]) -> str:
    if int(section_record["english_block_count"]) > 0:
        return (
            "Embedded ChineseNotes English was detected for this chapter, "
            "but it is not an exportable public-domain witness and no acceptable replacement witness was verified."
        )
    return (
        "No clean exportable public-domain English witness was verified for this chapter; "
        "ChineseNotes is Chinese-only here and no acceptable replacement witness was confirmed."
    )


def _build_manifest_section(
    *,
    section_id: str,
    label: str,
    canonical_ref: str,
    sort_key: str,
    reason: str,
    source_id: str,
) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "work_id": WORK_ID,
        "label": label,
        "canonical_ref": canonical_ref,
        "sort_key": sort_key,
        "notes": f"Metadata-only Mozi chapter. {reason}",
        "alignment_status": "not_exported",
        "tmx_status": "blocked",
        "expected_exact_alignment_count": 0,
        "source_ids": {
            "source_id": source_id,
        },
    }


def _update_chinesenotes_work_mapping(summary: dict[str, object], *, embedded_english_section_count: int) -> None:
    mapping = load_json_compatible_yaml(CHINESENOTES_WORK_MAPPING_PATH)
    entry = next(item for item in mapping["works"] if item["chintransmem_work_id"] == WORK_ID)
    entry["status"] = "staged"
    entry["english_coverage"] = "blocked"
    entry["chinese_coverage"] = "complete"
    entry["preferred_use"] = "metadata_only"
    entry["generated_summary"] = {
        "upstream_commit_sha": UPSTREAM_COMMIT_SHA,
        "total_section_count": summary["total_section_count"],
        "active_section_count": summary["active_section_count"],
        "exportable_section_count": summary["exportable_section_count"],
        "exact_alignment_count": summary["exact_alignment_count"],
        "alignment_granularity_counts": summary["alignment_granularity_counts"],
        "curated_override_section_count": summary["curated_override_section_count"],
        "fallback_section_count": summary["fallback_section_count"],
        "blocked_section_count": summary["blocked_section_count"],
        "remaining_drift_issue_count": summary["remaining_drift_issue_count"],
        "remaining_line_order_issue_count": summary.get("remaining_line_order_issue_count", 0),
        "embedded_chinesenotes_english_section_count": embedded_english_section_count,
        "english_witness": summary["english_witness"],
    }
    entry["notes"] = (
        f"Staged from ChineseNotes `{UPSTREAM_INDEX_PATH}` at upstream commit `{UPSTREAM_COMMIT_SHA}`: "
        f"{summary['total_section_count']} detected chapters, 0 active/exportable chapters, "
        f"{summary['blocked_section_count']} metadata-only blockers, "
        f"{embedded_english_section_count} chapters with embedded ChineseNotes English, "
        "and no clean public-domain English witness verified for export."
    )
    write_json(CHINESENOTES_WORK_MAPPING_PATH, mapping)


def bootstrap_corpus(*, skip_fetch: bool = False) -> dict[str, Any]:
    index_raw_path = RAW_DIR / f"{WORK_ID}__index__chinesenotes-{UPSTREAM_COMMIT_SHORT}__raw.csv"
    intro_raw_path = RAW_DIR / f"{WORK_ID}__intro__chinesenotes-{UPSTREAM_COMMIT_SHORT}__raw.txt"
    _ensure_text_capture(index_raw_path, UPSTREAM_RAW_BASE_URL + UPSTREAM_INDEX_PATH, skip_fetch=skip_fetch)
    _ensure_text_capture(intro_raw_path, UPSTREAM_RAW_BASE_URL + UPSTREAM_INTRO_PATH, skip_fetch=skip_fetch)

    intro_text = intro_raw_path.read_text(encoding="utf-8")
    inherited_translator_notes = _extract_notice_lines(intro_text, TRANSLATOR_ATTRIBUTION_RE)
    inherited_rights_notes = _extract_notice_lines(intro_text, PUBLIC_DOMAIN_RE)

    source_rows = _load_source_rows(index_raw_path)
    stage_sections: list[dict[str, Any]] = []
    stage_chinese_blocks: list[dict[str, Any]] = []
    stage_english_blocks: list[dict[str, Any]] = []
    inventory_units: list[dict[str, Any]] = []
    ledger_entries: list[dict[str, Any]] = []
    manifest_sections: list[dict[str, Any]] = []
    manifest_sources: list[dict[str, Any]] = []
    romanization_aliases: list[dict[str, Any]] = [
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "romanization_system": "pinyin",
            "alias": "Mozi",
        },
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "romanization_system": "historical",
            "alias": "Mo Tzu",
        },
        {
            "entity_type": "work",
            "entity_id": WORK_ID,
            "romanization_system": "english-title",
            "alias": CANONICAL_TITLE_EN,
        },
    ]
    blocked_sections: list[dict[str, str]] = []
    qc_sections: list[dict[str, Any]] = []
    embedded_english_section_count = 0

    for row in source_rows:
        volume_label, chinese_title, english_title = _parse_displayed_title(str(row["displayed_title"]))
        section_id = _section_id(int(row["row_index"]), english_title)
        raw_capture_path = _section_raw_capture_path(section_id)
        raw_url = UPSTREAM_RAW_BASE_URL + "corpus/" + str(row["source_relative_path"])
        blob_url = UPSTREAM_BLOB_BASE_URL + "corpus/" + str(row["source_relative_path"])
        _ensure_text_capture(raw_capture_path, raw_url, skip_fetch=skip_fetch)
        source_text = raw_capture_path.read_text(encoding="utf-8")
        source_sha256 = sha256_file(raw_capture_path)
        source_record = {
            **row,
            "local_checkout_root": str(REPO_ROOT),
            "local_raw_capture_path": repo_relative(raw_capture_path),
            "upstream_commit_sha": UPSTREAM_COMMIT_SHA,
            "sha256": source_sha256,
        }
        section_record, chinese_blocks, english_blocks, _ = _parse_section_body(
            work_id=WORK_ID,
            section_number=int(row["row_index"]),
            heading=str(row["displayed_title"]),
            body=source_text,
            inherited_translator_notes=inherited_translator_notes,
            inherited_rights_notes=inherited_rights_notes,
            source_record=source_record,
            section_id=section_id,
            section_unit="section",
            merge_wrapped_lines=True,
        )

        reason = _metadata_only_reason(section_record)
        if int(section_record["english_block_count"]) > 0:
            embedded_english_section_count += 1

        zh_source_suffix = f"chinesenotes-{WORK_ID}-zh-{UPSTREAM_COMMIT_SHORT}"
        zh_source_id = f"{section_id}__{zh_source_suffix}"
        chinese_segments_path = ZH_SEGMENTS_DIR / f"{WORK_ID}__{section_id}__{zh_source_suffix}__segments.jsonl"
        chinese_segments = [
            _segment_record(section_id=section_id, source_id=zh_source_id, block_index=index, text=str(block["text_original"]))
            for index, block in enumerate(chinese_blocks, start=1)
        ]
        write_jsonl(chinese_segments_path, chinese_segments)

        stage_sections.append(
            {
                "section_id": section_id,
                "displayed_title": row["displayed_title"],
                "source_relative_path": row["source_relative_path"],
                "raw_capture_path": repo_relative(raw_capture_path),
                "parser_status": section_record["status"],
                "chinese_block_count": section_record["chinese_block_count"],
                "english_block_count": section_record["english_block_count"],
                "commentary_present": section_record["commentary_present"],
                "english_headings": list(section_record["english_headings"]),
                "decision": "metadata_only",
                "blocking_reason": reason,
            }
        )
        stage_chinese_blocks.extend(chinese_blocks)
        stage_english_blocks.extend(english_blocks)

        canonical_ref = f"{CANONICAL_TITLE_ZH}·{volume_label} {chinese_title}".strip()
        sort_key = f"{int(row['row_index']):03d}"
        manifest_sections.append(
            _build_manifest_section(
                section_id=section_id,
                label=str(row["displayed_title"]),
                canonical_ref=canonical_ref,
                sort_key=sort_key,
                reason=reason,
                source_id=zh_source_id,
            )
        )
        manifest_sources.append(
            {
                "source_id": zh_source_id,
                "work_id": WORK_ID,
                "section_id": section_id,
                "language_code": "zh-Hant",
                "source_kind": "digital_transcription",
                "citation": f"{CANONICAL_TITLE_ZH} {row['displayed_title']}",
                "source_url": blob_url,
                "raw_path": repo_relative(raw_capture_path),
                "processed_path": repo_relative(chinese_segments_path),
                "rights_status": "public_domain",
                "author_or_translator_ids": ["mozi-transmitters"],
                "notes": (
                    "ChineseNotes Mozi chapter retained as a Chinese provenance scaffold only. "
                    f"Upstream repository: {UPSTREAM_REPOSITORY_URL} @ {UPSTREAM_COMMIT_SHA}. "
                    f"Upstream relative path: corpus/{row['source_relative_path']}. "
                    f"Source SHA256: {source_sha256}. Review date: {REVIEW_DATE}. "
                    "No clean public-domain English witness has been verified for export."
                ),
            }
        )
        inventory_units.append(
            {
                "section_id": section_id,
                "title": row["displayed_title"],
                "canonical_ref": canonical_ref,
                "sort_key": sort_key,
                "unit_type": "section",
                "text_status": "extant",
                "coverage_status": "metadata_only_blocked",
                "zh_page_url": blob_url,
                "english_witness_status": "unverified_or_missing",
                "verification_status": "metadata_only",
                "source_volume": volume_label,
                "translator": None,
                "decision": "metadata_only",
                "english_title": english_title,
                "reason": reason,
            }
        )
        ledger_entries.append(
            {
                "section_id": section_id,
                "title": row["displayed_title"],
                "canonical_ref": canonical_ref,
                "source_volume": volume_label,
                "source_page_or_anchor": blob_url,
                "translation_source_pages": [],
                "raw_source_path": repo_relative(raw_capture_path),
                "processed_source_path": repo_relative(chinese_segments_path),
                "processed_translation_path": None,
                "processed_alignment_path": None,
                "upstream_repository_url": UPSTREAM_REPOSITORY_URL,
                "upstream_commit_sha": UPSTREAM_COMMIT_SHA,
                "upstream_relative_path": f"corpus/{row['source_relative_path']}",
                "source_sha256": source_sha256,
                "repository_level_licence_basis": "Apache-2.0 for source code; CC BY-SA 3.0 assumed for text files per upstream license.txt",
                "translator_note": "; ".join(section_record["source_metadata"]["translator_notes"]),
                "rights_or_source_notes": list(section_record["source_metadata"]["rights_notes"]),
                "translator_or_source_notes": list(section_record["source_metadata"]["translator_notes"]),
                "local_staging_path": repo_relative(STAGING_DIR / "sections.jsonl"),
                "local_raw_capture_path": repo_relative(raw_capture_path),
                "translation_raw_capture_path": None,
                "verification_status": "metadata_only",
                "reviewer_note": WORK_LEVEL_BLOCKER_NOTE,
                "extraction_method": "chinesenotes_chinese_scaffold_only",
                "alignment_status": "not_exported",
                "alignment_granularity": None,
                "alignment_strategy": None,
                "alignment_anchor_map_used": False,
                "alignment_anchor_count": 0,
                "segment_granularity": None,
                "exact_alignment_count": 0,
                "commentary_present_and_excluded": bool(section_record["commentary_present"]),
                "english_heading_present_and_excluded": bool(section_record["english_headings"]),
                "excluded_english_headings": list(section_record["english_headings"]),
                "curated_override_used": False,
                "reason_automatic_alignment_failed": reason,
                "curator_note": None,
                "review_status": None,
                "alignment_quality_issues": [],
                "fallback_used": False,
                "coarse_alignment_reason": None,
                "decision": "metadata_only",
                "source_id": zh_source_id,
                "target_source_id": None,
            }
        )
        blocked_sections.append({"section_id": section_id, "reason": reason})
        qc_sections.append(
            {
                "section_id": section_id,
                "decision": "metadata_only",
                "reason": reason,
                "embedded_english_block_count": section_record["english_block_count"],
                "commentary_present": section_record["commentary_present"],
                "english_headings": list(section_record["english_headings"]),
            }
        )
        romanization_aliases.extend(
            [
                {
                    "entity_type": "section",
                    "entity_id": section_id,
                    "romanization_system": "source-label",
                    "alias": row["displayed_title"],
                },
                {
                    "entity_type": "section",
                    "entity_id": section_id,
                    "romanization_system": "english-title",
                    "alias": english_title,
                },
            ]
        )

    write_jsonl(STAGING_DIR / "sections.jsonl", stage_sections)
    write_jsonl(STAGING_DIR / "chinese_blocks.jsonl", stage_chinese_blocks)
    write_jsonl(STAGING_DIR / "english_blocks.jsonl", stage_english_blocks)

    alignment_qc_report = {
        "work_id": WORK_ID,
        "summary": {
            "total_section_count": len(manifest_sections),
            "active_section_count": 0,
            "exportable_section_count": 0,
            "exact_alignment_count": 0,
            "alignment_granularity_counts": {},
            "automatic_alignment_count": 0,
            "curated_override_section_count": 0,
            "fallback_section_count": 0,
            "blocked_section_count": len(blocked_sections),
            "english_witness": ENGLISH_WITNESS_SUMMARY,
            "work_state": "staged_metadata_only",
            "pre_repair_corruption_issue_count": 0,
            "corrected_corruption_issue_count": 0,
            "remaining_corruption_issue_count": 0,
            "drift_checks_run": 0,
            "drift_issue_count_before_repair": 0,
            "repaired_drift_issue_count": 0,
            "remaining_drift_issue_count": 0,
            "hard_failure_count": 0,
        },
        "curated_override_sections": [],
        "fallback_sections": [],
        "blocked_sections": blocked_sections,
        "sections": qc_sections,
    }

    manifest = {
        "work_id": WORK_ID,
        "title_zh": CANONICAL_TITLE_ZH,
        "title_en": CANONICAL_TITLE_EN,
        "status": "staged",
        "source_languages": ["zh-Hant"],
        "target_languages": ["en"],
        "summary": {
            "section_count": len(manifest_sections),
            "complete_sections": 0,
            "metadata_only_sections": len(manifest_sections),
            "sections_needing_alignment": 0,
            "sections_needing_qc": 0,
            "exact_alignment_count": 0,
        },
        "ingestion_policy": {
            "inventory_required": True,
            "inventory_path": repo_relative(INVENTORY_PATH),
            "inventory_unit_key": "units",
            "inventory_derivation": "generated_from_blocked_chinesenotes_mozi_bootstrap",
            "ingestion_plan_required": True,
            "ingestion_plan_path": "documentation/mozi_ingestion_plan.md",
            "source_audit_required": True,
            "source_audit_path": "documentation/mozi_ingestion_plan.md",
            "granularity_policy_required": True,
            "granularity_policy_path": "documentation/alignment_granularity_policy.md",
            "section_unit": "section",
            "preferred_segment_unit": "block",
            "minimum_required_alignment_scope": "section",
            "maximum_exact_alignment_scope": "section",
            "allowed_segment_units": ["block", "section"],
            "coarse_alignment_units": ["section"],
            "granularity_order": ["block", "section"],
            "metadata_only_allowed": True,
            "missing_text_policy": "block_export_if_clean_chinese_or_english_text_is_missing",
            "commentary_policy": "exclude_commentary_headings_and_notice_lines_from_exportable_segments_before_alignment",
            "rights_policy": "public_domain_only_for_export_with_explicit_chinesenotes_provenance",
            "allowed_export_rights_statuses": ["public_domain"],
            "section_group_export_policy": "forbidden",
            "completion_definition": "Mozi may be promoted only when every staged chapter has clean Chinese source text, a verified exportable public-domain English witness, explicit provenance, and QC-clean processed exports. Until then every chapter remains metadata-only with an explicit blocker reason.",
        },
        "romanization_aliases": romanization_aliases,
        "sections": manifest_sections,
        "sources": manifest_sources,
        "ingestion_log": [
            {
                "run_id": f"bootstrap-{WORK_ID}-{REVIEW_DATE}",
                "work_id": WORK_ID,
                "stage": "bootstrap",
                "status": "completed",
                "notes": "Staged Mozi as a metadata-only ChineseNotes scaffold because no clean exportable public-domain English witness was verified.",
            }
        ],
    }

    write_json(MANIFEST_PATH, manifest)
    write_json(INVENTORY_PATH, {"work_id": WORK_ID, "source": "ChineseNotes Mozi bootstrap", "units": inventory_units})
    write_json(LEDGER_PATH, {"entries": ledger_entries})
    write_json(ALIGNMENT_QC_PATH, alignment_qc_report)
    _update_chinesenotes_work_mapping(
        alignment_qc_report["summary"],
        embedded_english_section_count=embedded_english_section_count,
    )
    COMPLETION_REPORT_PATH.write_text(
        render_completion_quality_markdown(
            alignment_qc_report,
            work_label=WORK_LABEL,
            report_path=repo_relative(ALIGNMENT_QC_PATH),
        ),
        encoding="utf-8",
    )

    return {
        "work_id": WORK_ID,
        "section_count": len(manifest_sections),
        "active_sections": 0,
        "blocked_sections": len(blocked_sections),
        "embedded_english_sections": embedded_english_section_count,
        "english_witness": ENGLISH_WITNESS_SUMMARY,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage Mozi from ChineseNotes as a metadata-only work.")
    parser.add_argument("--skip-fetch", action="store_true", help="Require existing local raw captures.")
    args = parser.parse_args()
    print(bootstrap_corpus(skip_fetch=args.skip_fetch))


if __name__ == "__main__":
    main()
