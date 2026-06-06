# shiji benji candidate report

- Work id: shiji
- Batch id: benji
- Current state: candidate_qc_failed
- Candidate export root: `corpus/candidates/shiji/benji`
- Monolithic promotion occurred: False
- Deterministic QC status: fail
- Deterministic QC hard failures: 1
- Deterministic QC issue count: 1
- Alignment review method: heuristic high-risk review (entity sequence, succession formula, witness quality, and anchor order; no remote LLM reviewer used)
- Alignment review count: 46
- Alignment review failed high-risk alignments: 15
- Reviewed fallback alignments: 0
- Named-entity drift reviews run: 46
- Named-entity drift issues detected: 1
- Named-entity drift issues repaired: 1
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
- Promotion ready: False
- Promotion target state: candidate_qc_failed
- Active corpus QC status: pass
- Candidate/active export agreement: False

## Section status

- active `shiji-001-annals-annals-of-the-five-emperors`
- metadata-only `shiji-002-annals-of-xia`: ChineseNotes Shiji pilot witness remains too structurally uneven for safe export in this tranche: Alignment QC failed for shiji-002-annals-of-xia: group 36: target segment length/structure imbalance suggests missing grouping; group 41: target segment length/structure imbalance suggests missing grouping; group 57: target segment length/structure imbalance suggests missing grouping
- active `shiji-003-annals-of-yin`

## Alignment review classifications

- `pass`: 31
- `semantic_drift`: 15

## Promotion blockers

- deterministic candidate QC has 1 hard failures
- alignment review found 15 failed high-risk alignments

## Candidate vs active agreement

- candidate and active corpus QC hard_failure_count differ
- candidate and active exact alignment count differ (46 != 29)
- candidate and active exact alignment counts differ
- candidate and active promoted section count differ (2 != 1)
- candidate and active promoted section ids differ
