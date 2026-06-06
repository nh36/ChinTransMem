from __future__ import annotations

import re
from typing import Any

ANCHOR_REQUIRED_KEYS = {
    "source": "source_required_terms",
    "target": "target_required_terms",
}
ANCHOR_SEQUENCE_KEYS = {
    "source": "source_entity_sequence",
    "target": "target_entity_sequence",
}


def _dedupe_consecutive(tokens: list[str]) -> list[str]:
    deduped: list[str] = []
    for token in tokens:
        if not token:
            continue
        if not deduped or deduped[-1] != token:
            deduped.append(token)
    return deduped


def _required_terms_present(text: str, terms: list[str], *, language: str) -> bool:
    if not terms:
        return False
    haystack = text if language == "zh" else text.casefold()
    for term in terms:
        needle = term if language == "zh" else term.casefold()
        if needle not in haystack:
            return False
    return True


def _matched_anchor_sequence(
    text: str,
    anchors: list[dict[str, Any]],
    *,
    language: str,
) -> tuple[list[str], list[str]]:
    sequence: list[str] = []
    matched_anchor_ids: list[str] = []
    ordered_anchors = sorted(anchors, key=lambda anchor: int(anchor["expected_order"]))
    for anchor in ordered_anchors:
        required_terms = list(anchor.get(ANCHOR_REQUIRED_KEYS[language]) or [])
        if not _required_terms_present(text, required_terms, language=language):
            continue
        matched_anchor_ids.append(str(anchor.get("source_anchor_id") or anchor.get("anchor_id") or anchor["expected_order"]))
        sequence.extend(str(token) for token in anchor.get(ANCHOR_SEQUENCE_KEYS[language]) or [])
    return _dedupe_consecutive(sequence), matched_anchor_ids


def compare_shiji_entity_sequences(
    chinese_text: str,
    translation_text: str,
    anchors: list[dict[str, Any]],
) -> dict[str, Any]:
    source_sequence, source_anchor_ids = _matched_anchor_sequence(chinese_text, anchors, language="source")
    target_sequence, target_anchor_ids = _matched_anchor_sequence(translation_text, anchors, language="target")
    if not source_sequence and not target_sequence:
        verdict = "not_applicable"
        drift_explanation = "No succession anchor sequence was detected in this alignment."
    elif source_sequence == target_sequence:
        verdict = "pass"
        drift_explanation = "Source and target succession sequences match."
    elif target_sequence and source_sequence[: len(target_sequence)] == target_sequence and len(target_sequence) < len(source_sequence):
        verdict = "target_lagging"
        drift_explanation = (
            "The English succession sequence lags behind the Chinese source sequence "
            f"(source={source_sequence}, target={target_sequence})."
        )
    elif source_sequence and target_sequence[: len(source_sequence)] == source_sequence and len(source_sequence) < len(target_sequence):
        verdict = "target_leading"
        drift_explanation = (
            "The English succession sequence leads the Chinese source sequence "
            f"(source={source_sequence}, target={target_sequence})."
        )
    else:
        verdict = "mismatch"
        drift_explanation = (
            "The Chinese and English succession sequences do not match "
            f"(source={source_sequence}, target={target_sequence})."
        )
    return {
        "entity_sequence_source": source_sequence,
        "entity_sequence_target": target_sequence,
        "entity_sequence_source_anchor_ids": source_anchor_ids,
        "entity_sequence_target_anchor_ids": target_anchor_ids,
        "entity_sequence_verdict": verdict,
        "drift_explanation": drift_explanation,
    }


def sequence_verdict_is_failure(verdict: str) -> bool:
    return verdict not in {"pass", "not_applicable"}
