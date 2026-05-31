# ChineseNotes integration plan

This plan treats **ChineseNotes** as an upstream source layer for ChinTransMem rather than as a replacement repository. ChinTransMem keeps its own manifest-driven corpus layout, reviewed provenance, alignment policy, and export pipeline; ChineseNotes supplies candidate witnesses, collection metadata, translator clues, and staged-ingestion evidence.

## Why ChineseNotes is useful

- It already organizes many classical works in a file-per-section corpus plus metadata tables under `data/corpus/`.
- It often records bilingual Chinese/English text, translator names, source hints, and public-domain notices inside the work files.
- It is especially useful as a witness-discovery layer for works where ChinTransMem needs a public-domain English translation or a clean Chinese section inventory.
- It gives us a structured cross-check against other sources such as Wikisource, CText, and Internet Archive scans.

## How it differs from ChinTransMem

| ChineseNotes | ChinTransMem |
| --- | --- |
| Mixed upstream website/source repository with code, dictionary data, corpus files, templates, and generated web assets | Translation-memory repository with curated metadata, reviewed witnesses, normalized exports, SQLite import, TMX/CSV/JSONL output, and QC gates |
| Organizes many texts for reading and lookup | Organizes approved source witnesses for stable segment alignment and export |
| File-level bilingual corpus with varying structure and coverage | Work manifests, reviewed sources, stable section IDs, exact/coarse alignment policy, and auditable exports |
| Repository-wide licensing includes code and text layers | Must record file-level provenance and licence status per ingested witness |

## What we will inspect first

1. `license.txt`, `README.md`, `data/authors.txt`, and any file-level notices.
2. `data/corpus/collections.csv` to understand upstream collections, titles, format hints, and category labels.
3. Work-specific metadata files such as `data/corpus/shijing.csv`, `data/corpus/lunyu.csv`, `data/corpus/mengzi.csv`, `data/corpus/zhuangzi.csv`, `data/corpus/xunzi.csv`, `data/corpus/hanfeizi.csv`, `data/corpus/zuozhuan.csv`, and `data/corpus/shiji.csv`.
4. Matching files under `corpus/` to confirm whether Chinese, English, translator attribution, and public-domain notices actually appear in the source text.

## What we will import first

1. **One work at a time in staging.** Run `scripts/ingest_chinesenotes_work.py` for a single mapped work and let that ingestion run generate the coverage audit.
2. **Staged outputs before active promotion.** Write parsed sections, Chinese blocks, English blocks, candidate alignments, a staging manifest, and a QC report under `corpus/staging/chinesenotes/{work_id}/` and `logs/qc_reports/`.
3. **Metadata before active corpus promotion.** Record upstream path, URL, inspected commit SHA, licence basis, and translator/source notes before any processed witness moves into active manifests or exports.
4. **Already-ingested works stay authoritative.** Use ChineseNotes first as a cross-check and source-witness layer for Shijing, Lunyu, and Mengzi rather than as replacement corpus content.

## What we will not import

- The entire upstream repository into active ChinTransMem corpus folders.
- Go application code, templates, generated HTML, indexes, Docker/container files, or web assets.
- Dictionary tables, grammar tutorials, modern news/article collections, or unrelated bilingual teaching materials unless a later task explicitly scopes them in.
- A separate forever-growing preliminary audit project divorced from ingestion. Coverage evidence should be emitted by each staged ingestion run.
- Any file whose provenance, licence, translator attribution, or text boundaries are unclear.

## Provenance and licence recording

For every ChineseNotes-derived witness we keep, record:

- upstream repository URL
- upstream relative path
- upstream commit SHA inspected
- source URL used for review
- access/review date
- repository-level licence basis from `license.txt`
- any file-level public-domain notice, translator attribution, or extra licence note
- local raw capture path under `corpus/raw/chinesenotes/`
- processed witness path under `corpus/processed/`

Repository-level licence is **not** enough by itself for export approval. File-level notices, translator attributions, and source-specific rights notes must still be captured in ChinTransMem metadata.

## Coverage handling

| Coverage shape | ChinTransMem handling |
| --- | --- |
| Chinese and English both present | Candidate bilingual witness; stage it, report block counts, and only promote exportable sections later |
| Chinese present, English absent | Classify as `chinese_only`; keep as a base-text or inventory aid, not a TM export |
| English present, Chinese absent | Classify as `english_only`; keep only if provenance is safe and pairing can later be established |
| Coverage uncertain | Let staged ingestion report `needs_boundary_review`, `needs_rights_or_translator_review`, or `parse_failed` rather than assuming completeness |

## Mapping ChineseNotes files into ChinTransMem work IDs

- ChinTransMem uses stable work IDs such as `shijing`, `lunyu`, `mengzi`, `zhuangzi`, and `shiji`.
- ChineseNotes filenames often map directly (`shijing.csv` -> `shijing`, `lunyu.csv` -> `lunyu`).
- Some require alias handling (`daodejing.csv` -> `laozi`, `sunzibingfa.csv` -> `sunzi`).
- The authoritative scaffold for this mapping lives in `metadata/chinesenotes_work_mapping.yml`.

## Current planning boundary

This workflow does **not** bulk-ingest the whole ChineseNotes repository and does **not** replace existing Lunyu, Mengzi, or Shijing data. The current pilot is `laozi`, staged from `data/corpus/daodejing.csv` into `corpus/staging/chinesenotes/laozi/`; it produced 81 chapters with both Chinese and English, 81 safe chapter-level candidate alignments, and no blocked sections, but it has not yet been promoted into the active corpus.
