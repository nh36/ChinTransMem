# Ingestion gauntlet

The ingestion gauntlet is the staging workflow for any new or repaired corpus work before it is allowed to overwrite active export artifacts.

## States

- `candidate_ingested`: candidate exports, TMX, snapshots, and state metadata have been staged under `corpus/candidates/{work}/`.
- `candidate_qc_failed`: deterministic QC or AI review found blocking issues.
- `candidate_repaired`: the work-specific repair/bootstrap logic was rerun and the candidate artifacts were regenerated.
- `candidate_ready_for_promotion`: deterministic QC, AI review, and promotion gates all pass.
- `active_proof_of_concept`: the promoted corpus is active, provenance is explicit, and proof-of-concept rights/release posture is acceptable.
- `active_release_ready`: the promoted corpus is active and cleared for release-ready use.
- `metadata_only_blocked`: the candidate cannot be promoted because the staged material is genuinely unusable or lacks the required witness coverage.

The current candidate state is written to `corpus/candidates/{work}/candidate_state.json`.

## Paths

- Candidate exports: `corpus/candidates/{work}/exports/`
- Candidate TMX validation snapshots: `corpus/candidates/{work}/reports/tmx_validation/`
- Candidate work snapshots: `corpus/candidates/{work}/metadata/`, `corpus/candidates/{work}/reports/`, `corpus/candidates/{work}/repair_logs/`
- Deterministic candidate QC report: `logs/qc_reports/{work}__candidate_qc.json`
- Alignment review output: `logs/ai_reviews/{work}__alignment_review.jsonl`
- Candidate report: `documentation/{work}_candidate_report.md`

## Make targets

- `make ingest-candidate WORK=...`
- `make qc-candidate WORK=...`
- `make ai-review-candidate WORK=...`
- `make refine-candidate WORK=...`
- `make promote-candidate WORK=...`
- `make ingestion-gauntlet WORK=...`

`make ingestion-gauntlet WORK=...` runs:

1. Bootstrap and import the work, then write candidate JSONL/CSV/TMX exports outside the active export tree.
2. Run deterministic QC over the candidate exports.
3. Run the alignment review pass over high-risk, fallback, repaired, first/last, and sampled alignments.
4. If blocking issues remain, rerun the work-specific repair/bootstrap logic and regenerate the candidate exports.
5. Re-run candidate QC and alignment review.
6. Promote only if the promotion gates pass.

## Promotion gates

Promotion fails if the candidate still shows any of the following:

- CJK in English translation text
- OCR corruption or known bad forms
- headings, source notices, page furniture, footnote leakage, or commentary leakage
- missing source witness metadata
- missing rights or release metadata
- unresolved line-order or drift issues
- unreviewed fallbacks
- manifest/export/QC count disagreement
- failed high-risk alignment reviews

Rights review status does not block proof-of-concept promotion when provenance and release posture are explicit.

## AI / semantic review

`scripts/ai_review_alignments.py` writes machine-readable JSONL review rows with one of:

- `pass`
- `fail`
- `needs_regrouping`
- `note_leakage`
- `ocr_issue`
- `wrong_section`
- `semantic_drift`
- `too_coarse_but_usable`
- `fallback_justified`

The review pass covers:

- all deterministic high-risk alignments
- all fallbacks
- suspicious length-ratio alignments
- alignments in sections that needed repairs
- the first and last alignment in every exported section
- a deterministic random sample of otherwise clean alignments

## Repair loop

The gauntlet is designed so work-specific bootstrap logic remains the repair engine. For candidate repair it can:

- apply deterministic OCR/token repair rules
- strip notes and footnotes from the exportable translation stream
- regenerate English segmentation
- rerun grouped monotonic alignment
- keep curated overrides when monotonic regrouping still fails
- leave only genuinely unusable sections as metadata-only

## Shiji policy

Shiji-scale ingestion should be staged and promoted in batches rather than as a monolith.

- Ingest by batch, for example `benji`, `biao`, `shu`, `shijia`, `liezhuan`, or smaller chapter groups.
- Run the gauntlet for each batch separately.
- Require alignment review for every high-risk row and sampled review for ordinary rows.
- Allow proof-of-concept promotion only for the batches that pass.
- Leave failed batches staged with blocker reports rather than forcing a whole-work promotion.
