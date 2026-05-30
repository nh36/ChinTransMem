# Work manifest architecture

The repository now treats **Lunyu as the default work** inside a broader multi-work pipeline instead of assuming that the whole corpus is a single work forever.

## Layout

- `metadata/manifests/{work_id}.yml` is the per-work manifest layer.
- `metadata/manifests/lunyu.yml` is the canonical Lunyu manifest.
- `metadata/corpus_manifest.yml` remains as a **Lunyu compatibility mirror** so the current Lunyu paths and downstream assumptions stay stable.
- `metadata/works.yml`, `metadata/sections.yml`, `metadata/sources.yml`, `metadata/romanization_aliases.yml`, and `metadata/ingestion_log.yml` remain the aggregate metadata files imported into SQLite.

## Bootstrap model

- `scripts/bootstrap_lunyu_corpus.py`, `scripts/bootstrap_mengzi_corpus.py`, and `scripts/bootstrap_shijing_corpus.py` own the implemented work-specific parsing and alignment logic.
- `scripts/bootstrap_work_corpus.py` is the manifest-aware coordinator. It loads all work manifests, runs concrete work bootstraps such as Lunyu, Mengzi, and Shijing, preserves any metadata-only manifests that may be added later, and rewrites the aggregate metadata files.
- `make bootstrap-corpus` now runs the manifest-aware bootstrap while preserving the existing Lunyu output paths.

## Shared workflow expectations

- `scripts/import_corpus.py` imports aggregate metadata for all configured works.
- `scripts/export_corpus.py`, `scripts/validate_tmx.py`, `scripts/qc_corpus.py`, and `scripts/corpus_workflow.py` are **work-scoped** by `work_id`, defaulting to `lunyu`.
- `make corpus`, `make regression`, and the legacy Lunyu export paths still target Lunyu by default.
- Optional future-facing entry points now exist through `make bootstrap-work WORK=...` and `make corpus-work WORK=...`.

## API direction

- `GET /works` lists imported works.
- `GET /works/{work_id}/sections` lists manifest-backed sections for one work.
- `GET /works/{work_id}/sections/{section_id}/passages` returns exported exact-alignment rows for one section.
- Legacy Lunyu compatibility routes remain at `GET /sections` and `GET /sections/{section_id}/passages`.

## Current constraint

The generic layer is intentionally conservative: it supports multiple work manifests now, with complete raw-to-alignment bootstraps for Lunyu and Mengzi plus a controlled Shijing pilot (`關雎`) aligned at stanza level. New works should still enter as metadata-first manifests until their public-domain witnesses and segmentation rules are ready.
