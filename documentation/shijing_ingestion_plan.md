# Shijing ingestion plan

- **work_id:** `shijing`
- **canonical title:** 詩經
- **English title:** The Book of Poetry / She King
- **work type:** poetry anthology
- **canonical unit count:** 311 canonical index entries
- **extant text count:** 305 poems
- **title-only lost-text count:** 6 entries marked 有其義而亡其辭
- **inventory basis:** ordered Chinese Wikisource 詩經 index captured in `metadata/shijing_poem_inventory.yml`
- **Chinese witness plan:** Chinese Wikisource poem pages anchored from the canonical index
- **English witness plan:** James Legge's public-domain Shijing witnesses, preferring transcribed English Wikisource text and falling back to recorded public-domain Internet Archive OCR/hOCR witnesses when extraction is reliable
- **source URL pattern:** `https://zh.wikisource.org/wiki/詩經*`, `https://en.wikisource.org/wiki/Sacred_Books_of_the_East/Volume_3/The_Shih*`, `https://archive.org/details/chineseclassics41legg`, `https://archive.org/details/chineseclassics42legg`
- **rights status:** public domain for all exportable witnesses
- **section unit:** poem
- **segment unit:** stanza preferred, poem allowed as fallback
- **minimum TMX unit:** poem
- **fallback strategy:** if stanza structure is uncertain, export a single poem-level exact alignment marked coarse; if the witness is too uncertain, keep the poem metadata-only
- **commentary/notes policy:** exclude commentary and notes from exact alignments and TMX
- **expected completion count:** 305 complete extant poems, 6 metadata-only lost-text entries, 452 exact alignments in the current committed corpus
- **known gaps:** the six title-only lost-text entries remain explicit non-exportable metadata sections
- **first pilot tranche:** 周南 beginning with 關雎

## Witness and rights notes

The corpus exports only public-domain witnesses. OCR and hOCR captures are acceptable only when the extracted poem text is reliable enough to support bounded poem-level or stanza-level exact alignment.
