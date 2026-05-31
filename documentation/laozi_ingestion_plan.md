# Laozi ingestion plan

This work promotes **Laozi / Daodejing** into the active ChinTransMem corpus from the ChineseNotes bilingual witness at upstream commit `1f6b1d3e7a40b6886a4b943c898125639e993544`.

## Source basis

- Upstream repository: `https://github.com/alexamies/chinesenotes.com`
- Reviewed files:
  - `corpus/daodejing/daodejing000.txt`
  - `corpus/daodejing/daodejing001.txt`
- Local preserved raw captures:
  - `corpus/raw/chinesenotes/laozi__daodejing__intro__chinesenotes-1f6b1d3__raw.txt`
  - `corpus/raw/chinesenotes/laozi__daodejing__main__chinesenotes-1f6b1d3__raw.txt`

## Rights and provenance policy

- Preserve the upstream repository URL, commit SHA, relative path, and raw-file SHA256 for every active chapter.
- Record the ChineseNotes repository-level text licence basis from `license.txt` alongside the file-level public-domain note and the James Legge 1891 attribution carried by the source.
- Export only the public-domain Laozi chapter text and the public-domain Legge translation text after commentary, headings, and notice lines have been excluded.

## Alignment policy

- Start from the parsed Chinese and English blocks produced from the raw ChineseNotes witness.
- Prefer deterministic refinement in this order:
  1. block-to-block when the parsed block counts match;
  2. split English by punctuation when that safely matches the Chinese blocks;
  3. split Chinese by strong punctuation when that safely matches the English blocks;
  4. split both sides by strong punctuation when both counts reconcile cleanly.
- Fall back to chapter-level alignment only when deterministic reconciliation still fails, and record a specific `coarse_alignment_reason`.

## Export and QC policy

- Every chapter must have both Chinese and English segment text before promotion.
- Commentary, English headings, and source/licence/translator notices must stay out of `translation_text`.
- Every active chapter must have a source/provenance record, an export decision, and either fine-grained exact alignments or a documented chapter-level fallback.
- Generated diagnostics live in `logs/qc_reports/laozi__alignment_qc.json` and `documentation/laozi_completion_quality.md`.
