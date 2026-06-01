# Mozi ingestion plan

## Scope

- Work ID: `mozi`
- Upstream ChineseNotes manifest: `data/corpus/mozi.csv`
- Upstream source directory: `corpus/mozi/`
- Section model: one section per ChineseNotes Mozi chapter file

## Source assessment

- ChineseNotes supplies 52 chapter files plus an introductory note file.
- The Chinese chapter files are structurally usable as a provenance scaffold and Chinese base-text witness.
- ChineseNotes English is not a viable export witness:
  - only `mozi001` and `mozi002` contain actual English translation text;
  - the rest of the chapter files are Chinese-only apart from occasional notice noise;
  - the mirrored text files remain tied to the upstream ChineseNotes text-file licence, so they do not satisfy this repository's public-domain-only export policy.

## English witness audit

The following replacement witnesses were checked and rejected for active export:

1. `https://en.wikisource.org/wiki/Translation:Mozi`
   - Source name: English Wikisource `Translation:Mozi`
   - Access date: `2026-06-01`
   - Attribution: Wikisource community translation
   - Rights/provenance: CC BY-SA / GFDL translation namespace, not a clean public-domain transcription
   - Result: rejected
2. `https://ctext.org/mozi/ens`
   - Source name: Chinese Text Project Mozi English view
   - Access date: `2026-06-01`
   - Attribution: mixed; CText notes Yi-Pao Mei's 1929 translation plus A. C. Graham's 1978 translation for the Canons and military chapters
   - Rights/provenance: mixed and not safe for the repository's public-domain-only export policy
   - Result: rejected
3. `https://archive.org/details/ethicalpolitical0000moti`
   - Source name: Internet Archive scan of Yi-Pao Mei, *The Ethical and Political Works of Motse*
   - Access date: `2026-06-01`
   - Attribution: Yi-Pao Mei (1893-1960), 1929
   - Rights/provenance: not yet worldwide public domain; also not a ready clean chapter-level transcription in this repository
   - Result: rejected

## Current decision

- Mozi is staged as a **metadata-only** work.
- All 52 chapters are retained in the manifest, inventory, ledger, and processed Chinese source scaffold.
- No English translation segments, no alignments, and no TM export rows are committed for Mozi in the current state.

## Promotion criteria

Promote Mozi only when:

1. a clean chapter-level public-domain English witness is captured with explicit provenance;
2. the witness covers the intended chapter set clearly enough to support useful TM alignment;
3. each promoted chapter has processed Chinese and English segments plus an explicit export decision;
4. QC reports zero hard failures for every active chapter.

## Next candidate

- `liji` remains the next likely ChineseNotes-derived ingestion candidate once the Mozi witness blocker is accepted or resolved.
