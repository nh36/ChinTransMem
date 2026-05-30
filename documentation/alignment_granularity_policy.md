# Alignment granularity policy

## Lunyu

- `section_unit`: `book`
- `preferred_segment_unit`: `saying`
- `allowed_segment_units`: `saying`
- `minimum_required_alignment_scope`: `saying`
- `maximum_exact_alignment_scope`: `saying`

Rules:

1. Every canonical Lunyu book must appear as its own section in the manifest and inventory.
2. No exact alignment may span more than one Lunyu book.
3. Exact exports must remain saying-level; broader book-level exact alignments are not allowed.
4. Commentary and translator notes are excluded from exact alignments and TMX.
5. Metadata-only Lunyu sections remain non-exportable.

## Mengzi

- `section_unit`: `section`
- `preferred_segment_unit`: `passage`
- `allowed_segment_units`: `passage`
- `minimum_required_alignment_scope`: `passage`
- `maximum_exact_alignment_scope`: `passage`

Rules:

1. Every canonical Mengzi section must appear as its own section in the manifest and inventory.
2. No exact alignment may span more than one Mengzi section.
3. Exact exports must remain passage-level; broader section-level exact alignments are not allowed.
4. Commentary and translator notes are excluded from exact alignments and TMX.
5. Metadata-only Mengzi sections remain non-exportable.

## Shijing

- `section_unit`: `poem`
- `preferred_segment_unit`: `stanza`
- `allowed_segment_units`: `stanza`, `poem`
- `minimum_required_alignment_scope`: `poem`
- `maximum_exact_alignment_scope`: `poem`

Rules:

1. Every canonical Shijing poem must appear as its own section in the manifest.
2. No exact alignment may span more than one Shijing poem.
3. Stanza-level exact alignment is preferred when the Chinese and English witnesses preserve matching stanza structure.
4. Poem-level exact alignment is allowed as the fallback when stanza structure cannot be aligned safely.
5. Poem-level exact alignment must be marked coarse unless the poem is structurally a single stanza in both source and target witnesses.
6. `section_group` alignments are descriptive only and must not be exported to TMX.
7. Metadata-only sections may appear in the manifest and API, but they must not be exported to TMX.
