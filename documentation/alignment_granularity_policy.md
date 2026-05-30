# Alignment granularity policy

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

## Lunyu and Mengzi

Lunyu and Mengzi retain their current section-scoped exact-alignment behavior. The new alignment metadata is exported for those works too, but the coarse-alignment policy above is Shijing-specific.
