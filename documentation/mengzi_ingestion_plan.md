# Mengzi ingestion plan

- **work_id:** `mengzi`
- **canonical title:** 孟子
- **English title:** The Works of Mencius
- **work type:** philosophical dialogue and prose treatise
- **canonical unit count:** 14 traditional sections
- **inventory basis:** derived from the committed Mengzi manifest; each traditional section is a section
- **Chinese witness plan:** Chinese Wikisource section pages under `孟子/*`
- **English witness plan:** James Legge, *The Chinese Classics*, Volume 2, English Wikisource transcription
- **source URL pattern:** `https://zh.wikisource.org/wiki/孟子/*`, `https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/*`
- **rights status:** public domain for all exportable witnesses
- **section unit:** section
- **segment unit:** passage
- **minimum TMX unit:** passage
- **fallback strategy:** if passage extraction becomes unreliable, keep the section metadata-only instead of exporting section-wide exact alignments
- **commentary/notes policy:** exclude commentary and notes from exact alignments and TMX
- **expected completion count:** 14 complete sections, 260 exact alignments
- **known gaps:** none in the current committed corpus
- **first pilot tranche:** 梁惠王上 and 梁惠王下

## Witness and rights notes

The current corpus uses public-domain Chinese Wikisource text and Legge's public-domain English witness only. Export is limited to witnesses whose `rights_status` remains `public_domain`.
