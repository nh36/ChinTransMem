# Mengzi ingestion status

The repository now includes a **public-domain Mengzi corpus** aligned against James Legge's *The Chinese Classics*, Volume 2.

Current ingestion decisions:

1. Chinese base text comes from Chinese Wikisource `孟子/{section}` raw captures with access date `2026-05-30`.
2. English translation comes from English Wikisource's Legge Volume 2 chapter pages with section-scoped source IDs.
3. Canonical segmentation is top-level numbered `passage` alignment for all 14 traditional Mengzi sections.
4. Raw captures stay untouched under `corpus/raw/wikisource/`; cleaned texts, segments, and alignments live under `corpus/processed/`.
5. Alignment grouping uses Legge's embedded Chinese quotation blocks with comparison-only variant normalization; source text is not silently rewritten.
6. `make bootstrap-corpus`, `make corpus-work WORK=mengzi`, and `make regression` are the guardrails that keep Mengzi and Lunyu export/TMX behavior stable together.
