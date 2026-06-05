# Liji ingestion plan

## Scope

- Work: *Liji* / *Book of Rites* (`liji`)
- Upstream source: ChineseNotes bilingual chapter files pinned to a specific Git commit
- Section model: one section per chapter/pian
- Current witness policy: Chinese base text plus ChineseNotes-hosted Legge English mirror
- Rights policy: `rights_review_required` and `not_cleared` until independent release review is completed

## Alignment strategy

1. Strip deterministic non-translation residue from each bilingual chapter.
2. Attempt exact block or monotonic grouped alignment from the cleaned chapter text.
3. Retain reviewed chapter-level fallback only for structurally uneven chapters that still resist safe regrouping.
4. Promote only after candidate QC and alignment review pass.

## Current promotion shape

- Total chapters detected: 49
- Reviewed fallback chapters: 4
- Metadata-only blockers: 0
