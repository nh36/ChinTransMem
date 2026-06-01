# Shangshu ingestion plan

## Scope

- Work ID: `shangshu`
- Upstream ChineseNotes manifest: `data/corpus/shangshu.csv`
- Upstream repository: `https://github.com/alexamies/chinesenotes.com`
- Upstream commit used for promotion: `1f6b1d3e7a40b6886a4b943c898125639e993544`

## Canonical inventory and witness model

- ChineseNotes lists one source file per Shangshu section.
- The active ChinTransMem model keeps every listed Shangshu section in the inventory.
- Exportable sections require clean Chinese and English text after commentary, headings, page notices, and rights/source notices are removed.
- Non-exportable sections remain metadata-only with an explicit blocker reason rather than being dropped from the inventory.

## Alignment policy

- Parse each ChineseNotes file into logical Chinese and English blocks rather than trusting physical line wrapping.
- Prefer exact block alignment when source and target block boundaries already correspond.
- Otherwise use monotonic grouped alignment that allows one-to-many and many-to-one groupings.
- Curated overrides are supported through `metadata/shangshu_alignment_overrides.yml`.
- Section-level coarse fallback is allowed only as a last resort and must carry an explicit reason.

## Completion definition

Shangshu is complete only when every listed section has a provenance record and an explicit export decision, exportable sections produce clean Chinese and English processed segments plus SQLite/CSV/JSONL/TMX exports, and alignment QC reports zero hard failures.
