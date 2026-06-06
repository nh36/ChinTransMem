from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any, Callable

from common import load_json_compatible_yaml

ENGLISH_UNIT_BOUNDARY_RE = re.compile(r"(?<=[.!?;:])\s+")
CHINESE_UNIT_BOUNDARY_RE = re.compile(r"(?<=[。！？；：])")
ENGLISH_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
CHINESE_CHAR_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
PAGE_PREFIX_RE = re.compile(r"^\[p\.\s*\d+\]\s*")
ENGLISH_TERMINAL_RE = re.compile(r"[.!?;:]$|[\"')\]]$")
CHINESE_TERMINAL_RE = re.compile(r"[。！？；：]$|[」』）】]$")
ENGLISH_CONTINUATION_START_RE = re.compile(
    r"^(?:and|or|but|nor|for|yet|so|as|because|with|when|while|who|which|that|"
    r"whose|whom|where|whereas|therefore|thereupon|thus|then|if|though|although|"
    r"before|after|from|to|of|in|on|at|by|into|upon|under|over|among|through|"
    r"against|without|within|is|are|was|were|be|been|being|he|she|they|it|his|her|"
    r"their|him|them|its)\b",
    re.IGNORECASE,
)


def strip_page_prefix(text: str) -> str:
    return PAGE_PREFIX_RE.sub("", text).strip()


def split_english_units(text: str) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    parts = [part.strip(" ;") for part in ENGLISH_UNIT_BOUNDARY_RE.split(normalized) if part.strip(" ;")]
    if len(parts) <= 1:
        return parts
    merged: list[str] = []
    for part in parts:
        if merged and part and part[0].islower() and len(ENGLISH_WORD_RE.findall(part)) <= 4:
            merged[-1] = f"{merged[-1]} {part}"
            continue
        merged.append(part)
    return merged


def split_chinese_units(text: str) -> list[str]:
    normalized = "".join(text.split())
    if not normalized:
        return []
    return [part.strip() for part in CHINESE_UNIT_BOUNDARY_RE.split(normalized) if part.strip()]


def english_word_count(text: str) -> int:
    return len(ENGLISH_WORD_RE.findall(text))


def chinese_char_count(text: str) -> int:
    return len(CHINESE_CHAR_RE.findall(text))


def major_clause_count(text: str, language: str) -> int:
    if language == "en":
        return max(1, len(re.findall(r"[,:;]", text)) + len(re.findall(r"\b(?:and|or|but|who|which|that)\b", text, re.IGNORECASE)))
    return max(1, len(re.findall(r"[，、；：]", text)))


def ends_with_question(text: str) -> bool:
    stripped = text.strip()
    return stripped.endswith("?") or stripped.endswith("？")


def merge_logical_lines(lines: list[str], language: str) -> list[str]:
    merged: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if not merged:
            merged.append(line)
            continue
        previous = merged[-1]
        if language == "zh":
            if not CHINESE_TERMINAL_RE.search(previous):
                merged[-1] = f"{previous}{line}"
                continue
        else:
            if not ENGLISH_TERMINAL_RE.search(previous) and ENGLISH_CONTINUATION_START_RE.match(line):
                merged[-1] = f"{previous} {line}"
                continue
        merged.append(line)
    return merged


def build_unit_records(
    blocks: list[str],
    language: str,
    splitter: Callable[[str], list[str]] | None,
) -> list[dict[str, Any]]:
    if not splitter:
        return [{"unit_index": index, "text": block.strip()} for index, block in enumerate(blocks) if block.strip()]
    units: list[dict[str, Any]] = []
    for block_index, block in enumerate(blocks):
        for unit_index, unit_text in enumerate(splitter(block)):
            stripped = unit_text.strip()
            if stripped:
                units.append(
                    {
                        "block_index": block_index,
                        "unit_index": len(units),
                        "unit_offset": unit_index,
                        "language": language,
                        "text": stripped,
                    }
                )
    return units


def join_unit_texts(units: list[dict[str, Any]], indices: list[int], language: str) -> str:
    pieces = [str(units[index]["text"]).strip() for index in indices]
    if language == "zh":
        return "".join(pieces)
    return " ".join(piece for piece in pieces if piece)


def _group_cost(
    source_units: list[dict[str, Any]],
    target_units: list[dict[str, Any]],
    source_indices: list[int],
    target_indices: list[int],
) -> float:
    source_text = join_unit_texts(source_units, source_indices, "zh")
    target_text = join_unit_texts(target_units, target_indices, "en")
    source_length = max(1, chinese_char_count(source_text))
    target_length = max(1, english_word_count(target_text))
    length_ratio_cost = abs(math.log((target_length * 1.8) / source_length))
    source_clause_count = major_clause_count(source_text, "zh")
    target_clause_count = major_clause_count(target_text, "en")
    clause_cost = abs(source_clause_count - target_clause_count) * 0.25
    grouping_penalty = ((len(source_indices) - 1) + (len(target_indices) - 1)) * 0.22
    question_penalty = 1.0 if ends_with_question(source_text) != ends_with_question(target_text) else 0.0
    return length_ratio_cost + clause_cost + grouping_penalty + question_penalty


def group_monotonic_units(
    source_units: list[dict[str, Any]],
    target_units: list[dict[str, Any]],
    *,
    max_source_group_size: int = 4,
    max_target_group_size: int = 4,
) -> list[dict[str, list[int]]]:
    source_count = len(source_units)
    target_count = len(target_units)
    if source_count == 0 or target_count == 0:
        raise ValueError("Cannot align empty unit lists.")

    best: dict[tuple[int, int], tuple[float, list[dict[str, list[int]]]]] = {(0, 0): (0.0, [])}
    for source_index in range(source_count + 1):
        for target_index in range(target_count + 1):
            state = best.get((source_index, target_index))
            if state is None:
                continue
            score, groups = state
            if source_index == source_count and target_index == target_count:
                continue
            for source_group_size in range(1, max_source_group_size + 1):
                next_source = source_index + source_group_size
                if next_source > source_count:
                    break
                for target_group_size in range(1, max_target_group_size + 1):
                    next_target = target_index + target_group_size
                    if next_target > target_count:
                        break
                    source_indices = list(range(source_index, next_source))
                    target_indices = list(range(target_index, next_target))
                    candidate_cost = score + _group_cost(source_units, target_units, source_indices, target_indices)
                    candidate = {"source_unit_indices": source_indices, "target_unit_indices": target_indices}
                    current = best.get((next_source, next_target))
                    if current is None or candidate_cost < current[0]:
                        best[(next_source, next_target)] = (candidate_cost, [*groups, candidate])

    final_state = best.get((source_count, target_count))
    if final_state is None:
        raise ValueError(
            f"Unable to find a monotonic grouped alignment for {source_count} source units and {target_count} target units."
        )
    return final_state[1]


def alignment_quality_issues(
    alignment: dict[str, Any],
    *,
    false_precision_segment_granularities: set[str] | frozenset[str] = frozenset({"sentence", "line"}),
) -> list[str]:
    issues: list[str] = []
    source_units = alignment["source_units"]
    target_units = alignment["target_units"]
    segment_granularity = str(alignment.get("segment_granularity") or "")
    for group_index, group in enumerate(alignment["groups"], start=1):
        source_indices = group["source_unit_indices"]
        target_indices = group["target_unit_indices"]
        source_text = join_unit_texts(source_units, source_indices, "zh")
        target_text = join_unit_texts(target_units, target_indices, "en")
        source_length = max(1, chinese_char_count(source_text))
        target_length = max(1, english_word_count(target_text))
        source_clause_count = major_clause_count(source_text, "zh")
        target_clause_count = major_clause_count(target_text, "en")
        if ends_with_question(source_text) != ends_with_question(target_text):
            issues.append(
                f"group {group_index}: source/target question punctuation mismatch ({source_text!r} vs {target_text!r})"
            )
        if (
            segment_granularity in false_precision_segment_granularities
            and len(source_indices) == 1
            and len(target_indices) == 1
            and source_length <= 12
            and target_length >= 18
            and target_clause_count > source_clause_count
        ):
            issues.append(
                f"group {group_index}: suspicious false precision; short source clause aligned to a long target segment"
            )
        if target_length / source_length > 4.5 and target_clause_count > source_clause_count + 2:
            issues.append(f"group {group_index}: target segment length/structure imbalance suggests missing grouping")
        if source_length / target_length > 5.0 and source_clause_count > target_clause_count + 2:
            issues.append(f"group {group_index}: source segment length/structure imbalance suggests missing grouping")
    return issues


def load_alignment_overrides(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = load_json_compatible_yaml(path)
    sections = data.get("sections", [])
    overrides: dict[str, dict[str, Any]] = {}
    for entry in sections:
        overrides[str(entry["section_id"])] = entry
    return overrides


def load_alignment_anchor_maps(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    data = load_json_compatible_yaml(path)
    sections = data.get("sections", [])
    return {str(entry["section_id"]): entry for entry in sections}


def _text_contains_required_terms(text: str, terms: list[str], *, language: str) -> bool:
    haystack = text if language == "zh" else text.lower()
    for term in terms:
        needle = term if language == "zh" else term.lower()
        if needle not in haystack:
            return False
    return True


def _find_anchor_boundary(text: str, terms: list[str], *, language: str, search_start: int) -> int:
    if not terms:
        raise ValueError("Anchor boundary terms are required for non-initial anchor partitioning.")
    candidates: list[int] = []
    for term in terms:
        if language == "zh":
            index = text.find(term, search_start)
            if index >= 0:
                candidates.append(index)
            continue
        match = re.search(re.escape(term), text[search_start:], re.IGNORECASE)
        if match is not None:
            candidates.append(search_start + match.start())
    if not candidates:
        raise ValueError(f"Unable to locate anchor boundary terms {terms!r} after offset {search_start}.")
    return min(candidates)


def _partition_joined_text_by_anchors(
    text: str,
    anchors: list[dict[str, Any]],
    *,
    language: str,
) -> list[str]:
    ordered_anchors = sorted(anchors, key=lambda anchor: int(anchor["expected_order"]))
    if not ordered_anchors:
        return [text.strip()] if text.strip() else []
    starts: list[int] = [0]
    search_start = 0
    boundary_key = "source_boundary_terms" if language == "zh" else "target_boundary_terms"
    required_key = "source_required_terms" if language == "zh" else "target_required_terms"
    for anchor in ordered_anchors[1:]:
        boundary_terms = list(anchor.get(boundary_key) or anchor.get(required_key) or [])
        anchor_start = _find_anchor_boundary(text, boundary_terms, language=language, search_start=search_start)
        starts.append(anchor_start)
        search_start = anchor_start + 1
    starts.append(len(text))
    segments = [text[starts[index] : starts[index + 1]].strip() for index in range(len(ordered_anchors))]
    for anchor, segment in zip(ordered_anchors, segments, strict=True):
        required_terms = list(anchor.get(required_key) or [])
        if required_terms and not _text_contains_required_terms(segment, required_terms, language=language):
            anchor_id = str(anchor.get("source_anchor_id") or anchor.get("anchor_id") or anchor["expected_order"])
            raise ValueError(
                f"Anchor partition for {anchor_id} did not retain the required {language} terms {required_terms!r}."
            )
    return segments


def partition_block_texts_by_anchors(
    chinese_blocks: list[str],
    english_blocks: list[str],
    anchor_map: dict[str, Any],
) -> tuple[list[str], list[str]]:
    anchors = list(anchor_map.get("anchors", []))
    if not anchors:
        return chinese_blocks, english_blocks
    chinese_text = "".join(block.strip() for block in chinese_blocks if block.strip())
    english_text = " ".join(block.strip() for block in english_blocks if block.strip())
    return (
        _partition_joined_text_by_anchors(chinese_text, anchors, language="zh"),
        _partition_joined_text_by_anchors(english_text, anchors, language="en"),
    )


def find_anchor_drift_issues(
    rows: list[dict[str, Any]],
    anchors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ordered_anchors = sorted(anchors, key=lambda anchor: int(anchor["expected_order"]))
    issues: list[dict[str, Any]] = []
    for anchor in ordered_anchors:
        anchor_id = str(anchor.get("source_anchor_id") or anchor.get("anchor_id") or anchor["expected_order"])
        source_matches = [
            row
            for row in rows
            if _text_contains_required_terms(
                str(row.get("chinese_text", "")),
                list(anchor.get("source_required_terms") or []),
                language="zh",
            )
        ]
        target_matches = [
            row
            for row in rows
            if _text_contains_required_terms(
                str(row.get("translation_text", "")),
                list(anchor.get("target_required_terms") or []),
                language="en",
            )
        ]
        if len(source_matches) != 1:
            issues.append(
                {
                    "anchor_id": anchor_id,
                    "issue": "missing_or_ambiguous_source_anchor",
                    "matching_alignment_ids": [str(row.get("alignment_id")) for row in source_matches],
                    "note": anchor.get("note"),
                }
            )
            continue
        if len(target_matches) != 1:
            issues.append(
                {
                    "anchor_id": anchor_id,
                    "issue": "missing_or_ambiguous_target_anchor",
                    "matching_alignment_ids": [str(row.get("alignment_id")) for row in target_matches],
                    "note": anchor.get("note"),
                }
            )
            continue
        source_alignment_id = str(source_matches[0].get("alignment_id"))
        target_alignment_id = str(target_matches[0].get("alignment_id"))
        if source_alignment_id != target_alignment_id:
            issues.append(
                {
                    "anchor_id": anchor_id,
                    "issue": "crossed_anchor_alignment",
                    "source_alignment_id": source_alignment_id,
                    "target_alignment_id": target_alignment_id,
                    "note": anchor.get("note"),
                }
            )
    return issues


def build_override_alignment(
    section_id: str,
    chinese_blocks: list[str],
    english_blocks: list[str],
    override: dict[str, Any],
    *,
    source_splitter: Callable[[str], list[str]] | None,
    target_splitter: Callable[[str], list[str]] | None,
    default_segment_granularity: str,
) -> dict[str, Any]:
    source_units = build_unit_records(chinese_blocks, "zh", source_splitter)
    target_units = build_unit_records(english_blocks, "en", target_splitter)
    groups: list[dict[str, Any]] = []
    per_group_granularities: set[str] = set()
    for entry in override.get("alignments", []):
        source_indices = [int(index) for index in entry["source_unit_indices"]]
        target_indices = [int(index) for index in entry["target_unit_indices"]]
        if not source_indices or not target_indices:
            raise ValueError(f"Override for {section_id} contains an empty unit list.")
        if max(source_indices) >= len(source_units) or max(target_indices) >= len(target_units):
            raise ValueError(f"Override for {section_id} references out-of-range unit indices.")
        granularity = str(entry.get("alignment_granularity") or default_segment_granularity)
        per_group_granularities.add(granularity)
        groups.append(
            {
                "source_unit_indices": source_indices,
                "target_unit_indices": target_indices,
                "alignment_granularity": granularity,
                "curator_note": entry.get("curator_note"),
                "reason_automatic_alignment_failed": entry.get("reason_automatic_alignment_failed"),
                "review_status": entry.get("review_status"),
            }
        )
    if not groups:
        raise ValueError(f"Override for {section_id} does not define any alignments.")
    segment_granularity = default_segment_granularity
    alignment_granularity = "grouped" if any(
        len(group["source_unit_indices"]) != 1 or len(group["target_unit_indices"]) != 1 for group in groups
    ) else (next(iter(per_group_granularities)) if len(per_group_granularities) == 1 else default_segment_granularity)
    return {
        "source_units": source_units,
        "target_units": target_units,
        "groups": groups,
        "alignment_granularity": alignment_granularity,
        "segment_granularity": segment_granularity,
        "strategy": "curated_override",
        "curated_override_used": True,
        "reason_automatic_alignment_failed": override.get("reason_automatic_alignment_failed"),
        "curator_note": override.get("curator_note"),
        "review_status": override.get("review_status"),
    }


def refine_alignment(
    section_id: str,
    chinese_blocks: list[str],
    english_blocks: list[str],
    *,
    source_splitter: Callable[[str], list[str]] | None = None,
    target_splitter: Callable[[str], list[str]] | None = None,
    default_segment_granularity: str = "sentence",
    block_alignment_granularity: str = "block",
    max_source_group_size: int = 4,
    max_target_group_size: int = 4,
    override: dict[str, Any] | None = None,
    false_precision_segment_granularities: set[str] | frozenset[str] = frozenset({"sentence", "line"}),
) -> dict[str, Any]:
    if override:
        alignment = build_override_alignment(
            section_id,
            chinese_blocks,
            english_blocks,
            override,
            source_splitter=source_splitter,
            target_splitter=target_splitter,
            default_segment_granularity=default_segment_granularity,
        )
        issues = alignment_quality_issues(
            alignment,
            false_precision_segment_granularities=false_precision_segment_granularities,
        )
        if issues:
            raise ValueError(f"Curated override for {section_id} still fails alignment QC: {'; '.join(issues)}")
        alignment["quality_issues"] = []
        return alignment

    if len(chinese_blocks) == len(english_blocks) and chinese_blocks and english_blocks:
        groups = [
            {"source_unit_indices": [index], "target_unit_indices": [index]}
            for index in range(len(chinese_blocks))
        ]
        alignment = {
            "source_units": build_unit_records(chinese_blocks, "zh", None),
            "target_units": build_unit_records(english_blocks, "en", None),
            "groups": groups,
            "alignment_granularity": block_alignment_granularity,
            "segment_granularity": block_alignment_granularity,
            "strategy": "exact_block_alignment",
            "curated_override_used": False,
            "reason_automatic_alignment_failed": None,
            "curator_note": None,
            "review_status": None,
        }
        issues = alignment_quality_issues(
            alignment,
            false_precision_segment_granularities=false_precision_segment_granularities,
        )
        if not issues:
            alignment["quality_issues"] = []
            return alignment

    source_units = build_unit_records(chinese_blocks, "zh", source_splitter)
    target_units = build_unit_records(english_blocks, "en", target_splitter)
    groups = group_monotonic_units(
        source_units,
        target_units,
        max_source_group_size=max_source_group_size,
        max_target_group_size=max_target_group_size,
    )
    alignment_granularity = "grouped"
    if all(len(group["source_unit_indices"]) == 1 and len(group["target_unit_indices"]) == 1 for group in groups):
        alignment_granularity = default_segment_granularity
    alignment = {
        "source_units": source_units,
        "target_units": target_units,
        "groups": groups,
        "alignment_granularity": alignment_granularity,
        "segment_granularity": default_segment_granularity,
        "strategy": "monotonic_grouped_auto_alignment",
        "curated_override_used": False,
        "reason_automatic_alignment_failed": None,
        "curator_note": None,
        "review_status": None,
    }
    issues = alignment_quality_issues(
        alignment,
        false_precision_segment_granularities=false_precision_segment_granularities,
    )
    if issues:
        raise ValueError(f"Alignment QC failed for {section_id}: {'; '.join(issues)}")
    alignment["quality_issues"] = []
    return alignment


def render_completion_quality_markdown(
    report: dict[str, Any],
    *,
    work_label: str,
    report_path: str,
) -> str:
    summary = report["summary"]
    lines = [
        f"# {work_label} completion quality",
        "",
        f"Generated from `{report_path}`.",
        "",
        "## Summary",
        "",
    ]
    if "work_state" in summary:
        lines.append(f"- Work state: {summary['work_state']}")
    if "total_section_count" in summary:
        lines.append(f"- Total detected sections: {summary['total_section_count']}")
    lines.extend(
        [
            f"- Active sections: {summary['active_section_count']}",
            f"- Exportable sections: {summary['exportable_section_count']}",
        ]
    )
    if "english_witness" in summary:
        lines.append(f"- English witness: {summary['english_witness']}")
    lines.extend(
        [
        f"- Exact alignments: {summary['exact_alignment_count']}",
        f"- Automatic fine-grained alignments: {summary['automatic_alignment_count']}",
        f"- Total processed alignment records: {summary.get('alignment_record_count', summary['exact_alignment_count'])}",
        f"- Curated override sections: {summary['curated_override_section_count']}",
        f"- Remaining coarse fallbacks: {summary['fallback_section_count']}",
        f"- Blocked sections: {summary['blocked_section_count']}",
        f"- Hard failures: {summary['hard_failure_count']}",
        ]
    )
    if "pre_repair_corruption_issue_count" in summary:
        lines.append(f"- Corruption issues before repair: {summary['pre_repair_corruption_issue_count']}")
    if "corrected_corruption_issue_count" in summary:
        lines.append(f"- Corruption issues corrected: {summary['corrected_corruption_issue_count']}")
    if "automatic_correction_count" in summary:
        lines.append(f"- Automatic OCR/token repairs: {summary['automatic_correction_count']}")
    if "curated_correction_count" in summary:
        lines.append(f"- Curated OCR/phrase repairs: {summary['curated_correction_count']}")
    if "remaining_corruption_issue_count" in summary:
        lines.append(f"- Corruption issues remaining: {summary['remaining_corruption_issue_count']}")
    if "pre_repair_leakage_issue_count" in summary:
        lines.append(f"- Note/commentary leakage issues before repair: {summary['pre_repair_leakage_issue_count']}")
    if "repaired_leakage_issue_count" in summary:
        lines.append(f"- Note/commentary leakage issues repaired: {summary['repaired_leakage_issue_count']}")
    if "remaining_leakage_issue_count" in summary:
        lines.append(f"- Note/commentary leakage issues remaining: {summary['remaining_leakage_issue_count']}")
    if "drift_checks_run" in summary:
        lines.append(f"- Alignment drift checks run: {summary['drift_checks_run']}")
    if "drift_issue_count_before_repair" in summary:
        lines.append(f"- Drift issues before repair: {summary['drift_issue_count_before_repair']}")
    if "repaired_drift_issue_count" in summary:
        lines.append(f"- Drift issues repaired: {summary['repaired_drift_issue_count']}")
    if "remaining_drift_issue_count" in summary:
        lines.append(f"- Drift issues remaining: {summary['remaining_drift_issue_count']}")
    if "entity_sequence_validation_passed" in summary:
        lines.append(f"- Named-entity succession validation passed: {summary['entity_sequence_validation_passed']}")
    if "line_order_checks_run" in summary:
        lines.append(f"- Canonical line-order checks run: {summary['line_order_checks_run']}")
    if "line_order_issue_count_before_repair" in summary:
        lines.append(f"- Line-order issues before repair: {summary['line_order_issue_count_before_repair']}")
    if "repaired_line_order_issue_count" in summary:
        lines.append(f"- Line-order issues repaired: {summary['repaired_line_order_issue_count']}")
    if "remaining_line_order_issue_count" in summary:
        lines.append(f"- Line-order issues remaining: {summary['remaining_line_order_issue_count']}")
    lines.extend(["", "## Alignment granularity", ""])
    for granularity, count in sorted(summary["alignment_granularity_counts"].items()):
        lines.append(f"- {granularity}: {count}")
    fallback_sections = report.get("fallback_sections", [])
    lines.extend(["", "## Remaining fallbacks", ""])
    if fallback_sections:
        for section in fallback_sections:
            lines.append(f"- `{section['section_id']}`: {section['coarse_alignment_reason']}")
    else:
        lines.append("- None.")
    curated_sections = report.get("curated_override_sections", [])
    lines.extend(["", "## Curated override sections", ""])
    if curated_sections:
        for section_id in curated_sections:
            lines.append(f"- `{section_id}`")
    else:
        lines.append("- None.")
    anchor_sections = report.get("anchor_mapped_sections", [])
    lines.extend(["", "## Anchor-mapped sections", ""])
    if anchor_sections:
        for section_id in anchor_sections:
            lines.append(f"- `{section_id}`")
    else:
        lines.append("- None.")
    blocked_sections = report.get("blocked_sections", [])
    lines.extend(["", "## Blocked sections", ""])
    if blocked_sections:
        for section in blocked_sections:
            lines.append(f"- `{section['section_id']}`: {section['reason']}")
    else:
        lines.append("- None.")
    return "\n".join(lines) + "\n"
