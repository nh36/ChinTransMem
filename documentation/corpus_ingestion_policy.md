# Corpus ingestion policy

Every new work must clear a documented preflight before any scraper, parser, bootstrap, TMX export, or API exposure is treated as valid.

A syntactically valid TMX file is **not** sufficient. Exported units must correspond to meaningful textual units permitted by the work's declared granularity policy.

## Phase 0: Work proposal

Record the proposal in `documentation/{work_id}_ingestion_plan.md` with:

- `work_id`
- canonical title
- English title
- work type
- expected canonical structure
- expected public-domain translation witnesses

## Phase 1: Canonical inventory

Create `metadata/{work_id}_inventory.yml` before serious ingestion.

The inventory must enumerate every canonical unit in order and distinguish:

- extant text
- title-only or lost-text units
- doubtful units
- appendices
- commentary or paratext

## Phase 2: Source reconnaissance

Document the witness plan before extraction work begins.

For each required Chinese and English witness, record:

- source URL
- whether the text is clean transcription, Wikisource transclusion, scan/OCR, or unavailable
- rights status
- whether human verification is still needed

Do not proceed merely because a witness seems likely to exist.

## Phase 3: Granularity policy

Declare the work's alignment policy in the manifest `ingestion_policy` block and document it in `documentation/alignment_granularity_policy.md`.

Required decisions:

- `section_unit`
- `preferred_segment_unit`
- `minimum_required_alignment_scope`
- `maximum_exact_alignment_scope`
- allowed fallback units
- what counts as coarse alignment
- whether commentary and notes are excluded or stored separately

## Phase 4: Pilot ingestion

Ingest a small representative subset first.

The pilot must prove:

- source fetching
- parser stability
- segmentation strategy
- exact alignment strategy
- TMX/JSONL/CSV exportability
- coverage and granularity validation

## Phase 5: Full ingestion

Only after the pilot is stable may the work expand to full coverage.

Rules:

1. Ingest every sourceable canonical unit.
2. Keep metadata-only units explicit.
3. Every complete unit must meet the work's minimum exact-alignment requirement.
4. Add finer alignment only where it is structurally safe.

## Phase 6: Regression and audit

Before a work is considered mergeable, it must pass:

- ingestion-policy validation
- coverage audit
- granularity validation
- TMX validation
- regression tests

## Enforced repository rules

The repository validators fail when a work lacks:

- a manifest `ingestion_policy` block
- a required inventory file
- an ingestion plan with witness and rights coverage
- a granularity policy
- source records with `rights_status` and `source_url`
- compliant exact-alignment exports

No new work may be ingested until those prerequisites exist and `make preflight-work WORK={work_id}` passes.
