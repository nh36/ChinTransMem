# Copilot Instructions

## Current repository state

- The source of truth is `chinese_classics_translation_memory_readme.md`.
- The repository now includes a working **whole-Lunyu** public-domain corpus bootstrapped against James Legge's translation. Use the spec document for broader roadmap context, but prefer the implemented files under `corpus/`, `metadata/`, `db/`, `scripts/`, `web/api/`, and `tests/` when changing the current system.

## Build, test, and lint commands

- `make bootstrap-corpus` regenerates metadata and processed files for the committed Lunyu corpus from the section manifest and local raw captures.
- `make corpus` runs the end-to-end workflow: initialize the SQLite database, import the full corpus, export aligned passages, validate TMX, and write the QC report.
- `make init-db`, `make import-corpus`, `make export-corpus`, `make validate-tmx`, and `make qc-corpus` run the workflow stages individually.
- `make regression` is the commit-safe guardrail target; it reruns the full corpus workflow and the Python test suite, including TMX validation.
- `make install-hooks` configures `git core.hooksPath` to use `.githooks/pre-commit`, which runs `make regression` before each commit once the repository is under Git.
- `make serve-api` starts the read-only corpus API for the SQLite database.
- `make test` runs the Python `unittest` suite.
- `make single-test` runs one test method; override `TEST`, for example `make single-test TEST=tests.test_corpus_workflow.CorpusWorkflowTest.test_end_to_end`.
- Direct Python equivalents are `python3 scripts/bootstrap_lunyu_corpus.py --skip-fetch`, `python3 scripts/corpus_workflow.py`, `python3 scripts/init_db.py`, `python3 scripts/import_corpus.py`, `python3 scripts/export_corpus.py`, `python3 scripts/validate_tmx.py`, `python3 scripts/qc_corpus.py`, `python3 scripts/install_git_hooks.py`, `python3 web/api/corpus_api.py`, and `python3 -m unittest discover -s tests -p 'test_*.py'`.

## High-level architecture

- The project centers on an aligned-passage corpus: **Chinese source segment + one or more published translations + bibliographic citation + provenance metadata + rights status**.
- Text, translations, and alignments are separate data objects. Alignments are expected to be many-to-many rather than one-to-one.
- The implemented storage split is:
  - `corpus/raw/` for untouched source captures
  - `corpus/processed/` for cleaned base texts, translations, and alignments; normalized text currently lives in each segment's `text_normalized` field
  - `corpus/exports/` for query/export artifacts generated from SQLite, including per-section and combined JSONL, CSV, and TMX
  - `metadata/*.yml` for works, sections, persons, sources, rights, romanization aliases, ingestion logs, and the corpus manifest
  - `db/schema.sql` and `db/migrations/0001_initial_schema.sql` for the SQLite-first schema
  - `scripts/` for the no-dependency Python workflow and corpus bootstrap logic
  - `web/api/` for the read-only API layer over the corpus database
  - `.githooks/` and `.github/workflows/regression.yml` for local and CI regression enforcement
  - `logs/qc_reports/` for audit-style QC output
- `metadata/corpus_manifest.yml` is the section-level source of truth for whole-corpus status, URLs, expected alignment counts, and source IDs.
- The implemented processing pipeline is **capture raw Wikisource text -> create cleaned segment files and alignments per Lunyu book -> import into SQLite -> export per-section and combined aligned passages/TMX -> validate TMX -> generate corpus QC**.
- The core schema is `works`, `sections`, `persons`, `sources`, `segments`, `alignments`, and `agent_runs`.
- The current corpus imports all 20 Lunyu books, with one section-level grouped alignment per book and 241 saying-level exact alignments across the 11 books where the parsed Chinese and Legge segment counts match. The remaining 9 books are preserved with section-group coverage and explicit manifest metadata showing that exact alignment still needs follow-up.

## Key conventions

- **Provenance first.** Every segment should be traceable to a specific edition, page, URL, scan, file, or local object.
- **Keep raw data immutable.** Preserve raw captures untouched, and keep cleaned, normalized, segmented, and aligned stages as separate artifacts.
- **Do not silently normalize source text.** Do not silently convert traditional/simplified characters, variant characters, punctuation, or Wade-Giles/older romanization. Store normalized or alias forms separately.
- **Separate layers explicitly.** Chinese base text, translation, commentary, notes, and translator footnotes should be stored as distinct data, not flattened together.
- **Preserve canonical hierarchy.** Segment by canonical structures such as book/chapter, juan, poem/stanza/line, duke/year, or chapter/paragraph rather than arbitrary page or line wrapping.
- **Use stable IDs and filenames.** Follow the pattern `{work_id}__{section_id}__{source_id}__{stage}.{ext}` and keep persistent IDs for works, sections, sources, segments, and alignments.
- **Use JSON-compatible YAML metadata.** `metadata/*.yml` is currently written as JSON-compatible YAML so the bootstrap scripts can load it with the Python standard library instead of adding a YAML dependency.
- **The corpus manifest drives scale-up.** Add or change Lunyu books in `metadata/corpus_manifest.yml`, then regenerate derived metadata and processed files with `make bootstrap-corpus`.
- **Not every book is exact-aligned yet.** `alignment_status` and `tmx_status` in `metadata/corpus_manifest.yml` distinguish books with exact saying-level TMX coverage from books that currently have section-group coverage only.
- **Source IDs are section-scoped.** `sources.source_id` must be unique across the whole database, so each Lunyu book prefixes the shared source witness (`book-XX-...__zhwikisource-20260529`, `book-XX-...__legge-cc-v1-1893`).
- **Segment files are the import boundary.** The importer reads curated `segments.jsonl` and `alignments.jsonl` files, not the raw Wikisource captures directly.
- **Normalized text is explicit.** Keep source-faithful wording in `text_original`; put cleanup such as spacing or restored punctuation in `text_normalized`, and use notes when a normalization repairs a source formatting issue.
- **Every Lunyu book exports independently.** `scripts/export_corpus.py` writes JSONL, CSV, and TMX for each section as well as combined corpus exports.
- **TMX exports are first-class outputs.** `scripts/validate_tmx.py` must stay green against both per-section and combined SQLite-backed exports.
- **Regression runs must exercise the full corpus.** Local pre-commit checks and CI should run `make regression`, not just `make test`, so import, export, TMX validation, and QC all run on every change.
- **Treat rights status as a first-class field.** Keep public-domain, open, licensed-private, permission-pending, and metadata-only materials clearly separated from the start.
- **Do not treat LLM output as source text.** LLMs may assist with alignment, QC, and notes, but must not supply published-translation corpus content or fill missing source text.
- **Do not collapse recensions or editions.** Two texts with the same title may still be different witnesses/versions and must not share a source ID without verification.
- **Use romanization/search aliases for discovery.** Maintain Wade-Giles, older spellings, and local-library lookup variants as alias metadata instead of replacing canonical identifiers.
- **Batch outputs should stay audit-friendly.** QC and import runs should leave persistent artifacts such as export files, checksums, per-section counts, unmatched-segment checks, and manifest-backed completion status.
