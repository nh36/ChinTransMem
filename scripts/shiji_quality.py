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
SHIJI_NAME_GLOSS_RE = re.compile(
    r"\b([A-Za-z][A-Za-z'’.-]*(?:\s+[A-Za-z][A-Za-z'’.-]*){0,2})\s+\(([^()]{1,40})\)",
    re.IGNORECASE,
)
SHIJI_WITNESS_FIXES: list[dict[str, Any]] = [
    {
        "pattern": re.compile(r"\bsucceseful\b", re.IGNORECASE),
        "replacement": "successful",
        "issue_type": "known_bad_form",
        "reason": "Known Shiji witness misspelling.",
        "confidence": 0.99,
    },
    {
        # Match the specific raw romanization error (case-sensitive) so corrected forms aren't re-flagged
        "pattern": re.compile(r"\bZao\s+Yu\b"),
        "replacement": "Cao Yu",
        "issue_type": "romanization_inconsistency",
        "reason": "Witness spelling disagrees with the surrounding Cao Yu succession anchor.",
        "confidence": 0.97,
    },
    {
        # Match the lowercase 'gui' error specifically (case-sensitive)
        "pattern": re.compile(r"\bZhu\s+gui\b"),
        "replacement": "Zhu Gui",
        "issue_type": "capitalization_drift",
        "reason": "Witness capitalization is inconsistent within the same succession chain.",
        "confidence": 0.96,
    },
]
SHIJI_KNOWN_BAD_FORM_RE = re.compile(r"\bsucceseful\b", re.IGNORECASE)
# Case-sensitive detection for the two romanization/capitalization issues so normalized forms are not matched
SHIJI_ZAO_YU_RE = re.compile(r"\bZao\s+Yu\b")
SHIJI_ZHU_GUI_RE = re.compile(r"\bZhu\s+gui\b")


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


def normalize_shiji_witness_text(text: str) -> tuple[str, list[dict[str, Any]]]:
    normalized = text
    repairs: list[dict[str, Any]] = []
    for entry in SHIJI_WITNESS_FIXES:
        pattern = entry["pattern"]
        replacement = str(entry["replacement"])

        def _replace(match: re.Match[str]) -> str:
            repairs.append(
                {
                    "raw_form": match.group(0),
                    "corrected_form": replacement,
                    "issue_type": str(entry["issue_type"]),
                    "reason": str(entry["reason"]),
                    "confidence": float(entry["confidence"]),
                    "automatic_or_curated": "automatic",
                }
            )
            return replacement

        normalized = pattern.sub(_replace, normalized)

    def _strip_name_gloss(match: re.Match[str]) -> str:
        raw_form = match.group(0)
        corrected_form = match.group(1).strip()
        # Normalize capitalization for name-like forms when stripping glosses
        corrected_form = corrected_form.title()
        repairs.append(
            {
                "raw_form": raw_form,
                "corrected_form": corrected_form,
                "issue_type": "name_gloss_intrusion",
                "reason": "Strip parenthetical glosses attached to name-like English witness forms.",
                "confidence": 0.92,
                "automatic_or_curated": "automatic",
            }
        )
        return corrected_form

    while True:
        updated = SHIJI_NAME_GLOSS_RE.sub(_strip_name_gloss, normalized)
        if updated == normalized:
            break
        normalized = updated
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = re.sub(r"\s+([,.;:!?])", r"\1", normalized)
    return normalized.strip(), repairs


def detect_shiji_witness_quality_issues(text: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    for match in SHIJI_KNOWN_BAD_FORM_RE.finditer(text):
        issues.append({"token": match.group(0), "issue_type": "known_bad_form"})
    for match in SHIJI_ZAO_YU_RE.finditer(text):
        issues.append({"token": match.group(0), "issue_type": "romanization_inconsistency"})
    for match in SHIJI_ZHU_GUI_RE.finditer(text):
        issues.append({"token": match.group(0), "issue_type": "capitalization_drift"})
    for match in SHIJI_NAME_GLOSS_RE.finditer(text):
        issues.append({"token": match.group(0), "issue_type": "name_gloss_intrusion"})
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        token = str(issue.get("token", ""))
        issue_type = str(issue.get("issue_type", ""))
        key = (token, issue_type)
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"token": token, "issue_type": issue_type})
    return deduped


def _matched_anchor_sequence(
    text: str,
    anchors: list[dict[str, Any]],
    *,
    language: str,
) -> tuple[list[str], list[str]]:
    sequence: list[str] = []
    matched_anchor_ids: list[str] = []
    ordered_anchors = sorted(anchors, key=lambda anchor: int(anchor["expected_order"]))
    # For target-language matching, normalize the witness text once (strip name glosses, fix known bad forms)
    match_text = text
    if language == "target":
        match_text, _ = normalize_shiji_witness_text(text)
    for anchor in ordered_anchors:
        if language == "target":
            # Prefer pre-normalized target terms, but normalize legacy committed terms at runtime
            required_terms = list(anchor.get("normalized_target_required_terms") or anchor.get(ANCHOR_REQUIRED_KEYS[language]) or [])
            if required_terms and not anchor.get("normalized_target_required_terms"):
                # Normalize legacy target terms using the Shiji witness normalizer to strip name-gloss parentheticals
                normalized_required: list[str] = []
                for term in required_terms:
                    cleaned, _ = normalize_shiji_witness_text(str(term))
                    normalized_required.append(cleaned)
                required_terms = normalized_required
        else:
            required_terms = list(anchor.get(ANCHOR_REQUIRED_KEYS[language]) or [])
        if not _required_terms_present(match_text, required_terms, language=language):
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
