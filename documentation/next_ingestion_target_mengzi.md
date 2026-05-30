# Next ingestion target: Mengzi

The repository now carries a **metadata-only Mengzi pilot stub** for `book-01-lianghuiwang-shang` so the multi-work structure has a real second work before text ingestion begins.

Before ingesting public-domain Mengzi content, check:

1. Confirm the exact Chinese Wikisource base-text page and record the stable page URL plus access date in source metadata.
2. Confirm the public-domain English witness to use for the first proof of concept and record rights status before any text capture.
3. Decide the canonical section granularity for the pilot (`梁惠王上` as the first unit is the current placeholder).
4. Verify that raw captures, cleaned segments, and alignments can follow the existing `{work_id}__{section_id}__{source_id}__...` naming pattern without collisions.
5. Add explicit parser notes for any witness quirks instead of silently normalizing punctuation, numbering, or romanization.
6. Keep uncertain alignments flagged or metadata-only until the first section can export valid TMX under the same regression guardrails as Lunyu.
