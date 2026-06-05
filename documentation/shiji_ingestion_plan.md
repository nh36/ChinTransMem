# Shiji ingestion plan

- **work_id:** `shiji`
- **title:** *Shiji* / *Records of the Grand Historian* (`史記`)
- **primary discovery source:** `data/corpus/shiji.csv` with chapter files under `corpus/shiji/`
- **batch policy:** Shiji is batch-only from the start. It will **not** be promoted as one monolithic work.

## Batch model

Shiji batches follow the traditional division model where the ChineseNotes file numbering supports it:

1. `benji` 本紀 (`shiji001`-`shiji012`)
2. `biao` 表 (`shiji013`-`shiji022`)
3. `shu` 書 (`shiji023`-`shiji030`)
4. `shijia` 世家 (`shiji031`-`shiji060`)
5. `liezhuan` 列傳 (`shiji061`-`shiji130`)

Clean passing batches may be promoted as proof-of-concept. Failed batches remain in candidate storage with blocker reports. Rights review does not block proof-of-concept promotion, but every source must record provenance, `rights_status`, and `release_status`.

## First batch choice

The first batch id remains `benji`, but the initial pilot tranche is limited to **shiji001-shiji003**:

1. `shiji001` 五帝本紀
2. `shiji002` 夏本紀
3. `shiji003` 殷本紀

This smaller tranche was chosen automatically because:

- the first three annals show clearly bilingual ChineseNotes chapter files;
- `shiji002` and `shiji003` support clean block-level alignment immediately;
- `shiji001` is still attributable and structurally local enough to keep in the candidate batch, even if it needs to remain metadata-only or blocked for the first pass;
- later annals in `shiji004`-`shiji012` collapse the English witness into summary-level prose or near-empty parallel structure, making a full `benji` monolith unsafe for the first gauntlet pass.

## Witness policy

- **Chinese base text:** ChineseNotes chapter file pinned to a specific upstream commit.
- **English witness:** ChineseNotes-hosted bilingual English text from the same chapter file.
- **Translator/editor attribution:** provisional and chapter-specific. The current pilot records the witness as a ChineseNotes bilingual English witness with explicit raw-path provenance. Where no clearer translator attribution is visible in the source file, the translator remains unresolved and `release_status` stays `not_cleared`.
- **Rights posture:** proof-of-concept only unless independently cleared.

## Promotion rules

1. Candidate outputs stay under `corpus/candidates/shiji/<batch>/`.
2. Deterministic QC must pass with zero hard failures for promoted rows.
3. High-risk alignment review must pass for the batch.
4. Any remaining fallback must have an explicit reviewed reason.
5. Active exports are written only after the batch promotion gates pass.
