# Mozi ingestion plan

## Scope

- Work ID: `mozi`
- Upstream ChineseNotes manifest: `data/corpus/mozi.csv`
- Upstream source directory: `corpus/mozi/`
- Section model: one section per ChineseNotes Mozi chapter file

## Source assessment

- ChineseNotes supplies 52 chapter files plus an introductory note file.
- The Chinese chapter files are structurally usable as a provenance scaffold and Chinese base-text witness.
- ChineseNotes English is not a viable main export witness:
  - only `mozi001` and `mozi002` contain actual English translation text;
  - the remaining chapter files are Chinese-only apart from notice noise and page furniture;
  - the project now treats rights/release review separately from proof-of-concept ingestion, so ChineseNotes English was rejected for coverage/quality rather than as the sole blocker.

## English witness audit

The following replacement witnesses were checked:

1. `https://en.wikisource.org/wiki/Translation:Mozi`
   - Source name: English Wikisource `Translation:Mozi`
   - Access date: `2026-06-01`
   - Attribution: Wikisource community translation
   - Rights/provenance: translation-namespace community text; not a stable attributable witness for this bootstrap
   - Result: not used
2. `https://ctext.org/mozi/ens`
   - Source name: Chinese Text Project Mozi English view
   - Access date: `2026-06-01`
   - Attribution: mixed; CText notes Yi-Pao Mei's 1929 translation plus A. C. Graham's 1978 translation for the Canons and military chapters
   - Rights/provenance: mixed-source witness and operationally unreliable from this environment because of anti-automation gating
   - Result: not used
3. `https://archive.org/details/in.ernet.dli.2015.283868`
   - Source name: Archive.org OCR capture of Yi-Pao Mei, *The Works of Motse from the Chinese*
   - Access date: `2026-06-01`
   - Attribution: Yi-Pao Mei (1929)
   - Rights/provenance: usable with explicit attribution and `rights_review_required`, but not yet cleared for release or redistribution
   - Local raw capture: `corpus/raw/archiveorg/mozi__mei-1929__archiveorg-in-ernet-dli-2015-283868__raw.txt`
   - Result: adopted for the clean attributable proof-of-concept subset

## Current decision

- Mozi is now an **active proof-of-concept partial corpus**.
- All 52 chapters remain in the manifest, inventory, and verification ledger.
- Current committed state:
  1. 30 proof-of-concept exportable chapters
  2. 22 metadata-only chapters with explicit blocker reasons
  3. 684 export rows
  4. 676 grouped alignments and 8 chapter-level fallbacks
  5. 30 chapters marked `rights_review_required`
  6. 0 release-ready chapters
- Exportable chapters use explicit provenance plus `release_status: not_cleared`; this supports TM research without claiming the English witness is cleared for public release.

## Known blocker classes

- Chapters outside Mei coverage remain metadata-only until another attributable English witness is captured.
- Mei chapter numbers 46-50 are currently left metadata-only because the OCR extraction resolves to unrelated dialogue or glossary material rather than the matching Mozi chapter.
- Metadata-only blockers reflect real text/witness problems, not merely unverified public-domain status.

## Release-ready criteria

Promote a proof-of-concept chapter to release-ready only when:

1. the English witness is still clean and attributable;
2. rights/release review is complete and recorded explicitly;
3. the chapter keeps useful alignment with provenance, rights status, and release status intact;
4. QC continues to report zero hard failures.

## Next candidate

- `liji` remains the next likely ChineseNotes-derived ingestion candidate once Mozi is stable under the full guardrail run.
