# shiji benji candidate report

- Work id: shiji
- Batch id: benji
- Current state: active_proof_of_concept
- Candidate export root: `corpus/candidates/shiji/benji`
- Monolithic promotion occurred: False
- Deterministic QC status: pass
- Deterministic QC hard failures: 0
- Deterministic QC issue count: 2
- Alignment review method: heuristic high-risk review (entity sequence, succession formula, witness quality, and anchor order; no remote LLM reviewer used)
- Alignment review count: 46
- Alignment review failed high-risk alignments: 1
- Reviewed fallback alignments: 0
- Named-entity drift reviews run: 46
- Named-entity drift issues detected: 10
- Named-entity drift issues repaired: 0
- Named-entity drift issues remaining: 0
- Shiji 003 succession sequence passed entity-order validation: True
- Shiji witness-quality issues detected: 88
- Shiji witness-quality issues repaired: 88
- Shiji witness-quality issues remaining: 0
- Name-gloss handling: stripped_from_translation_text_raw_preserved
- Automatic repairs applied: 89
- Curated repairs applied: 0
- Remaining OCR issues: 0
- Remaining leakage issues: 0
- Remaining drift issues: 0
- Promotion ready: True
- Promotion target state: candidate_qc_failed
- Active corpus QC status: pass
- Candidate/active export agreement: True

## Section status

- active `shiji-001-annals-annals-of-the-five-emperors`
- metadata-only `shiji-002-annals-of-xia`: ChineseNotes Shiji pilot witness remains too structurally uneven for safe export in this tranche: Alignment QC failed for shiji-002-annals-of-xia: group 36: target segment length/structure imbalance suggests missing grouping; group 41: target segment length/structure imbalance suggests missing grouping; group 57: target segment length/structure imbalance suggests missing grouping
- active `shiji-003-annals-of-yin`

## Alignment review classifications

- `pass`: 45
- `semantic_drift`: 1

## Promotion blockers

- deterministic candidate QC has 2 hard failures
- alignment review found 1 failed high-risk alignments

## Candidate vs active agreement

- candidate and active corpus QC hard_failure_count differ
- candidate and active exact alignment counts differ
- candidate and active promoted section count differ (2 != 1)
- candidate and active promoted section ids differ
- candidate and active section export differ for shiji-003-annals-of-yin (csv)
- candidate and active section export differ for shiji-003-annals-of-yin (jsonl)
- candidate and active section export differ for shiji-003-annals-of-yin (tmx)
