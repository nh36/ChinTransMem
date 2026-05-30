# Lunyu ingestion plan

- **work_id:** `lunyu`
- **canonical title:** 論語
- **English title:** The Analects
- **work type:** sayings anthology
- **canonical unit count:** 20 books
- **inventory basis:** derived from the committed Lunyu manifest; each canonical book is a section
- **Chinese witness plan:** Chinese Wikisource book pages under `論語/*`
- **English witness plan:** James Legge, *The Chinese Classics*, Volume 1, English Wikisource transcription
- **source URL pattern:** `https://zh.wikisource.org/wiki/論語/*`, `https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_1/*`
- **rights status:** public domain for all exportable witnesses
- **section unit:** book
- **segment unit:** saying
- **minimum TMX unit:** saying
- **fallback strategy:** if a book cannot be segmented safely to saying level, keep it metadata-only instead of exporting broader exact alignments
- **commentary/notes policy:** exclude commentary and notes from exact alignments and TMX
- **expected completion count:** 20 complete books, 501 exact alignments
- **known gaps:** none in the current committed corpus
- **first pilot tranche:** books 1-2

## Witness and rights notes

The current corpus uses public-domain Chinese Wikisource text and Legge's public-domain English witness only. Export is limited to witnesses whose `rights_status` remains `public_domain`.
