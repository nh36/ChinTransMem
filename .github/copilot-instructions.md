# Copilot Instructions

## Current repository state

- The source of truth is `chinese_classics_translation_memory_readme.md`.
- The repository now includes a working public-domain pilot for **Lunyu / 學而第一 + James Legge Book I**. Use the spec document for broader roadmap context, but prefer the implemented files under `corpus/`, `metadata/`, `db/`, `scripts/`, and `tests/` when changing the current system.

## Build, test, and lint commands

- `make pilot` runs the end-to-end workflow: initialize the SQLite database, import the Lunyu/Legge pilot, export aligned passages, and write a QC report.
- `make init-db`, `make import-pilot`, `make export-pilot`, `make validate-tmx`, and `make qc-pilot` run the workflow stages individually.
- `make regression` is the commit-safe guardrail target; it reruns the full workflow and the Python test suite, including TMX validation.
- `make install-hooks` configures `git core.hooksPath` to use `.githooks/pre-commit`, which runs `make regression` before each commit once the repository is under Git.
- `make serve-api` starts the thin read-only API for the pilot database.
- `make test` runs the Python `unittest` suite.
- `make single-test` runs one test method; override `TEST`, for example `make single-test TEST=tests.test_pilot_workflow.PilotWorkflowTest.test_end_to_end`.
- Direct Python equivalents are `python3 scripts/pilot_workflow.py`, `python3 scripts/init_db.py`, `python3 scripts/import_lunyu_legge_pilot.py`, `python3 scripts/export_pilot.py`, `python3 scripts/validate_tmx.py`, `python3 scripts/qc_pilot.py`, `python3 scripts/install_git_hooks.py`, `python3 web/api/pilot_api.py`, and `python3 -m unittest discover -s tests -p 'test_*.py'`.

## High-level architecture

- The project centers on an aligned-passage corpus: **Chinese source segment + one or more published translations + bibliographic citation + provenance metadata + rights status**.
- Text, translations, and alignments are separate data objects. Alignments are expected to be many-to-many rather than one-to-one.
- The implemented storage split is:
  - `corpus/raw/` for untouched source captures
  - `corpus/processed/` for cleaned base texts, translations, and alignments; normalized text currently lives in each segment's `text_normalized` field
  - `corpus/exports/` for query/export artifacts generated from SQLite, including JSONL, CSV, and TMX
  - `metadata/*.yml` for works, sections, persons, sources, rights, romanization aliases, and ingestion logs
  - `db/schema.sql` and `db/migrations/0001_initial_schema.sql` for the SQLite-first schema
  - `scripts/` for the no-dependency Python workflow
  - `web/api/` for the thin read-only API layer over the pilot database
  - `.githooks/` and `.github/workflows/regression.yml` for local and CI regression enforcement
  - `logs/qc_reports/` for audit-style QC output
- The implemented processing pipeline is **capture raw Wikisource text -> create cleaned segment files -> import into SQLite -> export aligned passages and TMX -> validate TMX -> generate QC report**.
- The core schema is `works`, `sections`, `persons`, `sources`, `segments`, `alignments`, and `agent_runs`.
- The current pilot imports one section with 32 segments total, 16 saying-level exact alignments, and one section-level many-to-many alignment record proving grouped-alignment support.

## Key conventions

- **Provenance first.** Every segment should be traceable to a specific edition, page, URL, scan, file, or local object.
- **Keep raw data immutable.** Preserve raw captures untouched, and keep cleaned, normalized, segmented, and aligned stages as separate artifacts.
- **Do not silently normalize source text.** Do not silently convert traditional/simplified characters, variant characters, punctuation, or Wade-Giles/older romanization. Store normalized or alias forms separately.
- **Separate layers explicitly.** Chinese base text, translation, commentary, notes, and translator footnotes should be stored as distinct data, not flattened together.
- **Preserve canonical hierarchy.** Segment by canonical structures such as book/chapter, juan, poem/stanza/line, duke/year, or chapter/paragraph rather than arbitrary page or line wrapping.
- **Use stable IDs and filenames.** Follow the pattern `{work_id}__{section_id}__{source_id}__{stage}.{ext}` and keep persistent IDs for works, sections, sources, segments, and alignments.
- **Use JSON-compatible YAML metadata.** `metadata/*.yml` is currently written as JSON-compatible YAML so the bootstrap scripts can load it with the Python standard library instead of adding a YAML dependency.
- **Segment files are the import boundary.** The importer reads curated `segments.jsonl` and `alignments.jsonl` files, not the raw Wikisource captures directly.
- **Normalized text is explicit.** Keep source-faithful wording in `text_original`; put cleanup such as spacing or restored punctuation in `text_normalized`, and use notes when a normalization repairs a source formatting issue.
- **TMX exports are first-class outputs.** `scripts/export_pilot.py` writes TMX alongside JSONL and CSV, and `scripts/validate_tmx.py` must stay green against the SQLite export rows.
- **Regression runs must exercise TMX.** Local pre-commit checks and CI should run `make regression`, not just `make test`, so TMX generation and validation are covered on every change.
- **Treat rights status as a first-class field.** Keep public-domain, open, licensed-private, permission-pending, and metadata-only materials clearly separated from the start.
- **Do not treat LLM output as source text.** LLMs may assist with alignment, QC, and notes, but must not supply published-translation corpus content or fill missing source text.
- **Do not collapse recensions or editions.** Two texts with the same title may still be different witnesses/versions and must not share a source ID without verification.
- **Use romanization/search aliases for discovery.** Maintain Wade-Giles, older spellings, and local-library lookup variants as alias metadata instead of replacing canonical identifiers.
- **Batch outputs should stay audit-friendly.** QC and import runs should leave persistent artifacts such as export files, checksums, counts, unmatched-segment checks, and the many-to-many alignment IDs that were exercised.
