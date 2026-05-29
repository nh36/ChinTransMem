# Classical Chinese Translation Memory Bank

Working README and agent instructions for a Sinology-based project to build a translation-memory corpus of major translations of Chinese classics.

**Status:** planning document, first pass  
**Prepared:** 2026-05-29  
**Primary goal:** create a structured, rights-aware, citation-rich bank of aligned Classical Chinese passages and published translations, suitable for research, dictionary support, and later web/database presentation.

---

## 1. Project summary

This project will assemble a reusable translation-memory bank for major Chinese classics. The core unit is an aligned passage:

> Chinese source segment + one or more published translations + bibliographic citation + source/provenance metadata + rights status.

The immediate priority is not a public website, but a well-structured corpus and metadata layer that can later support:

- side-by-side display of Chinese text and translations;
- lookup by Chinese word, phrase, sentence, chapter, or passage;
- dictionary-adjacent examples, possibly linked to a licensed dictionary such as Paul W. Kroll’s *A Student’s Dictionary of Classical and Medieval Chinese* / Brill’s Chinese-English Dictionary Online;
- research workflows for comparing translation choices across translators, periods, and genres;
- export to TMX, TSV/CSV, JSONL, SQLite/PostgreSQL, or web API formats.

The corpus should keep public-domain, open, licensed, and not-yet-cleared materials separate from the beginning. Modern translations can be fully included as the project will not go public until permission and licensing questions are settled.

---

## 2. Core principles

1. **Provenance first.** Every text segment must be traceable to a specific source page, edition, scan, file, or local object.
2. **No silent modernization.** Do not silently convert traditional to simplified characters, replace variant characters, modernize punctuation, or alter romanization. Store normalized forms in separate fields.
3. **Separate text, translation, and alignment.** The base Chinese text, translated text, and alignment relation are distinct data objects.
4. **Many-to-many alignment.** A Chinese segment may correspond to multiple translation segments; one translation sentence may span several Chinese segments.
5. **Keep bibliographic identities stable.** Use persistent IDs for works, translators, editions, sections, and segments.
6. **Prefer canonical hierarchies over arbitrary lines.** Segment by book/chapter/juan/year/poem/stanza/paragraph where possible, not by line wrapping in a web page or OCR output.
7. **LLM output is not a source text.** Agents may propose alignments, notes, and QC flags, but LLM-generated translations must never be mixed into the corpus as published translation memory.
8. **Reversible processing.** Raw input, cleaned text, segmented text, and aligned text should all be retained separately.
9. **Local and web sources must not be conflated.** A local PDF or scan should be cited independently from a Wikisource text, even if they represent the same edition.

---

## 3. Recommended Sinology directory layout

Use a single root directory on the Sinology NAS. The example below assumes:

```text
/volume1/ChineseClassicsTM/
```

Recommended layout:

```text
/volume1/ChineseClassicsTM/
├── README.md
├── corpus/
│   ├── raw/
│   │   ├── wikisource/
│   │   ├── internet_archive/
│   │   ├── hathitrust_or_google_books/
│   │   ├── local_scans/
│   │   ├── local_pdfs/
│   │   └── manual_transcriptions/
│   ├── processed/
│   │   ├── chinese_base_texts/
│   │   ├── translations/
│   │   ├── normalized/
│   │   └── alignments/
│   └── exports/
│       ├── jsonl/
│       ├── csv/
│       ├── tmx/
│       └── sqlite/
├── metadata/
│   ├── works.yml
│   ├── persons.yml
│   ├── sources.yml
│   ├── rights.yml
│   ├── romanization_aliases.yml
│   ├── local_library_lookup.yml
│   └── ingestion_log.yml
├── scripts/
│   ├── fetch/
│   ├── clean/
│   ├── segment/
│   ├── align/
│   ├── qc/
│   └── export/
├── db/
│   ├── schema.sql
│   └── migrations/
├── web/
│   ├── api/
│   └── frontend/
├── documentation/
│   ├── source_notes/
│   ├── rights_notes/
│   └── workflow_notes/
└── logs/
    ├── agent_runs/
    ├── errors/
    └── qc_reports/
```

---

## 4. File naming conventions

Use explicit work, section, source, and processing-stage IDs.

### 4.1 Pattern

```text
{work_id}__{section_id}__{source_id}__{stage}.{ext}
```

Examples:

```text
lunyu__book-01-xueer__legge-cc-v1-1893__raw.txt
lunyu__book-01-xueer__legge-cc-v1-1893__clean.txt
lunyu__book-01-xueer__zhwikisource-20260529__base.txt
shijing__guofeng-zhounan-001-guanju__legge-1871__translation.txt
shiji__juan-086__zhwikisource-20260529__base.txt
zuozhuan__xigong-year-01__durrant-li-schaberg-2016__metadata-only.yml
```

### 4.2 Work IDs

Suggested initial IDs:

| Work ID | Chinese | Pinyin | Common English titles |
|---|---:|---|---|
| `lunyu` | 論語 | Lunyu | Analects, Confucian Analects |
| `daxue` | 大學 | Daxue | Great Learning |
| `zhongyong` | 中庸 | Zhongyong | Doctrine of the Mean |
| `mengzi` | 孟子 | Mengzi | Mencius |
| `shijing` | 詩經 | Shijing | Classic of Poetry, Book of Songs, Book of Odes |
| `shujing` | 書經 / 尚書 | Shujing / Shangshu | Book of Documents, Shoo King |
| `zhouyi` | 周易 / 易經 | Zhouyi / Yijing | Book of Changes, I Ching |
| `liji` | 禮記 | Liji | Book of Rites, Li Ki |
| `chunqiu` | 春秋 | Chunqiu | Spring and Autumn Annals |
| `zuozhuan` | 左傳 / 春秋左氏傳 | Zuozhuan | Zuo Tradition, Tso Chuan, Tso Chuen |
| `shiji` | 史記 | Shiji | Records of the Grand Historian, Grand Scribe’s Records |
| `hanshu` | 漢書 | Hanshu | Book of Han |
| `guoyu` | 國語 | Guoyu | Discourses of the States |
| `zhanguoce` | 戰國策 | Zhanguoce | Strategies of the Warring States |
| `laozi` | 老子 / 道德經 | Laozi / Daodejing | Tao Te Ching, Tao Teh King |
| `zhuangzi` | 莊子 | Zhuangzi | Chuang Tzu, Chuang Tzŭ |
| `sunzi` | 孫子兵法 | Sunzi Bingfa | Art of War |
| `mozi` | 墨子 | Mozi | Mo Tzu |
| `xunzi` | 荀子 | Xunzi | Hsün Tzu |
| `hanfeizi` | 韓非子 | Han Feizi | Han Fei Tzu |
| `lushi_chunqiu` | 呂氏春秋 | Lüshi chunqiu | Master Lü’s Spring and Autumn Annals |
| `shanhaijing` | 山海經 | Shanhaijing | Classic of Mountains and Seas |
| `zizhi_tongjian` | 資治通鑑 | Zizhi tongjian | Comprehensive Mirror for Aid in Government |

---

## 5. Metadata model

A minimal source record should include:

```yaml
source_id: legge-cc-v1-1893
work_id: lunyu
source_type: translation
language: en
translator_or_editor:
  - James Legge
publication_year: 1893
original_publication_year: 1861
short_title: The Chinese Classics, Vol. I
full_citation: >
  Legge, James, trans. The Chinese Classics, Vol. I: Confucian Analects,
  The Great Learning, and The Doctrine of the Mean. 2nd ed. Oxford:
  Clarendon Press, 1893. First published 1861.
source_location:
  type: wikisource
  url: https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_1/Confucian_Analects
rights_status: public_domain
local_path_hint: corpus/raw/wikisource/lunyu/legge-cc-v1-1893/
romanization_system: Wade-Giles / Legge conventions
ocr_status: not_applicable_or_wikisource_text
proof_status: scan_backed_on_wikisource
agent_notes: >
  Preserve Legge's Chinese, romanization, notes, and translation as separate fields where possible.
```

A minimal alignment record should include:

```yaml
alignment_id: lunyu-01-001__zhws__legge-cc-v1-1893
work_id: lunyu
section_id: book-01-xueer
chinese_segment_id: lunyu-01-001-zhws
translation_segment_id: lunyu-01-001-legge
alignment_type: exact_or_near_exact
confidence: 0.95
created_by: agent_or_human_id
created_at: 2026-05-29T00:00:00Z
review_status: needs_human_spotcheck
source_citations:
  chinese: https://zh.wikisource.org/wiki/論語/學而第一
  translation: https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_1/Confucian_Analects/Book_I
notes: >
  Check whether Legge's numbering exactly corresponds to the Wikisource Chinese segmentation.
```

---

## 6. Proposed database schema

At the prototype stage, SQLite is sufficient. Later, move to PostgreSQL if the web system needs multiuser editing, full-text search, authentication, or larger-scale APIs.

### 6.1 Core tables

```sql
works(
  work_id TEXT PRIMARY KEY,
  title_zh TEXT,
  title_pinyin TEXT,
  title_wadegiles TEXT,
  title_english_primary TEXT,
  period TEXT,
  genre TEXT,
  notes TEXT
);

sections(
  section_id TEXT PRIMARY KEY,
  work_id TEXT REFERENCES works(work_id),
  parent_section_id TEXT,
  canonical_order INTEGER,
  title_zh TEXT,
  title_pinyin TEXT,
  title_english TEXT,
  hierarchy_level TEXT,
  notes TEXT
);

persons(
  person_id TEXT PRIMARY KEY,
  display_name TEXT,
  name_variants TEXT,
  role TEXT,
  dates TEXT,
  notes TEXT
);

sources(
  source_id TEXT PRIMARY KEY,
  work_id TEXT REFERENCES works(work_id),
  source_type TEXT,
  language TEXT,
  title TEXT,
  author_or_translator_ids TEXT,
  publication_year INTEGER,
  edition TEXT,
  publisher TEXT,
  url TEXT,
  local_path_hint TEXT,
  rights_status TEXT,
  citation_text TEXT,
  notes TEXT
);

segments(
  segment_id TEXT PRIMARY KEY,
  work_id TEXT REFERENCES works(work_id),
  section_id TEXT REFERENCES sections(section_id),
  source_id TEXT REFERENCES sources(source_id),
  language TEXT,
  segment_order INTEGER,
  segment_type TEXT,
  text_original TEXT,
  text_normalized TEXT,
  citation_locator TEXT,
  checksum TEXT,
  notes TEXT
);

alignments(
  alignment_id TEXT PRIMARY KEY,
  work_id TEXT REFERENCES works(work_id),
  chinese_segment_ids TEXT,
  translation_segment_ids TEXT,
  alignment_type TEXT,
  confidence REAL,
  review_status TEXT,
  created_by TEXT,
  created_at TEXT,
  notes TEXT
);

agent_runs(
  run_id TEXT PRIMARY KEY,
  agent_name TEXT,
  started_at TEXT,
  finished_at TEXT,
  task_description TEXT,
  input_paths TEXT,
  output_paths TEXT,
  errors TEXT,
  notes TEXT
);
```

### 6.2 Optional tables

```sql
terms(
  term_id TEXT PRIMARY KEY,
  graph TEXT,
  normalized_graph TEXT,
  pinyin TEXT,
  middle_chinese TEXT,
  old_chinese TEXT,
  dictionary_refs TEXT,
  notes TEXT
);

term_occurrences(
  occurrence_id TEXT PRIMARY KEY,
  term_id TEXT REFERENCES terms(term_id),
  segment_id TEXT REFERENCES segments(segment_id),
  start_offset INTEGER,
  end_offset INTEGER,
  notes TEXT
);

translation_choices(
  choice_id TEXT PRIMARY KEY,
  term_id TEXT REFERENCES terms(term_id),
  translation_segment_id TEXT REFERENCES segments(segment_id),
  translated_as TEXT,
  translator_id TEXT,
  notes TEXT
);
```

---

## 7. Agent workflow

### 7.1 Intake phase

For each proposed source, the agent must:

1. Identify the work, translator/editor, edition, publication date, and source location.
2. Create or update a `sources.yml` entry.
3. Assign a preliminary rights status.
4. Record all title and author variants useful for local-library searching.
5. Check whether the source is already present locally under likely author/editor names.
6. If online, save the URL and access date.
7. If Wikisource, record whether the text is scan-backed, proofread, downloadable, or merely a transcription page.

### 7.2 Fetch phase

For Wikisource or other public/open sources:

1. Fetch the raw page or export format.
2. Save unmodified raw text/HTML under `corpus/raw/`.
3. Save the access date, URL, and, if available, revision/permanent link.
4. Do not remove notes, headers, or page metadata in the raw file.

### 7.3 Cleaning phase

1. Strip navigation and boilerplate only in the cleaned version.
2. Preserve original punctuation, paragraphing, and variant characters in `text_original`.
3. Store normalized forms separately.
4. Mark all automated normalizations in the processing log.
5. Do not assume that two online texts with the same title represent the same recension.

### 7.4 Segmentation phase

Preferred segment levels by work:

| Work | Primary segmentation | Secondary segmentation |
|---|---|---|
| Lunyu | book/chapter | individual saying |
| Mengzi | book/part | numbered passage |
| Shijing | poem | stanza/line |
| Shujing | document/chapter | paragraph |
| Zhouyi/Yijing | hexagram | line statement, 彖, 象, 文言 |
| Liji | chapter | paragraph |
| Zuozhuan | Duke/year | 春秋 annal vs 左傳 narrative |
| Shiji | juan | biography/annal/table/treatise subsection |
| Hanshu | juan | annal/table/treatise/biography subsection |
| Laozi | chapter | sentence/line |
| Zhuangzi | chapter | paragraph |
| Sunzi | chapter | paragraph |
| Mozi | chapter | paragraph |
| Xunzi | chapter | paragraph |
| Han Feizi | chapter | paragraph |
| Lüshi chunqiu | 紀/覽/論 + chapter | paragraph |
| Zhanguoce | state/chapter | anecdote |

### 7.5 Alignment phase

1. Align at the smallest meaningful unit that remains stable across translations.
2. Allow many-to-many alignments.
3. Use conservative confidence scores.
4. Store uncertain alignments as `needs_human_review`.
5. Never pad an alignment by inventing missing translation text.
6. If a translation is abridged, mark the omitted Chinese segments explicitly.
7. If a translator rearranges material, preserve both source order and translation order.

### 7.6 Quality control phase

Each completed work or source batch requires:

- a count of sections expected vs sections ingested;
- a checksum for raw and cleaned files;
- random spot-checks against the source;
- a list of unmatched segments;
- a list of high-risk transformations, especially romanization conversion, OCR correction, and punctuation insertion;
- a rights-status check before any export beyond private research use.

---

## 8. Wikisource usability survey

Grades used below:

- **A:** usable immediately as a major source for base text and/or public-domain translation, subject to normal QC.
- **B:** useful, but needs manual verification of version, segmentation, completeness, or proofreading status.
- **C:** partial, uneven, or mainly useful as metadata/starting point.
- **D:** not useful for direct ingestion without substantial separate work.

### 8.1 High-priority works

| Work | Chinese Wikisource status | English Wikisource status | Grade | Project notes |
|---|---|---|---:|---|
| 論語 / Lunyu / Analects | Chinese Wikisource has a main page and chapter pages, including 學而第一. | English Wikisource has Legge’s *Chinese Classics*, Vol. I, with a scan-backed page for the *Confucian Analects*. | A | Best first pilot. Align Chinese chapter/saying structure with Legge. Add later modern translations as metadata/rights-cleared sources. |
| 大學 / Daxue / Great Learning | Chinese text appears within the Four Books / Liji tradition; verify the exact Wikisource base page before ingestion. | Included in Legge’s *Chinese Classics*, Vol. I. | A/B | Good small pilot after Lunyu; version control matters because it circulates both as a chapter of 禮記 and as a Four Books text. |
| 中庸 / Zhongyong / Doctrine of the Mean | Chinese Wikisource has a 禮記/中庸 page. | Included in Legge’s *Chinese Classics*, Vol. I. | A | Good companion to 大學. |
| 孟子 / Mengzi / Mencius | Chinese Wikisource has the work and category pages for the fourteen traditional sections. | English Wikisource has Legge’s *Works of Mencius* in *Chinese Classics*, Vol. II. | A | Strong second pilot after Lunyu. Segment by traditional book and part. |
| 詩經 / Shijing / Classic of Poetry | Chinese Wikisource has the work and a large category structure with poem-level pages. | English Wikisource has a *Classic of Poetry* portal listing Legge, Jennings, and other translations; some pages present original Chinese with translations. | A | Excellent for testing poem/stanza/line alignment. Karlgren should be treated as an important local/copyright-restricted source unless rights are cleared. |
| 書經 / 尚書 / Shujing / Book of Documents | Chinese Wikisource coverage should be verified by exact page/version before ingestion. | Legge’s *Shoo King* is included in *Chinese Classics*, Vol. III and in *Sacred Books of China*. | B | Important, but textual versioning and chapter identity require more care. |
| 春秋左氏傳 / Zuozhuan | Chinese Wikisource has a well-segmented page with Duke sections and a complete 全覽 page with export options. | Legge’s *Tso Chuen* is in *Chinese Classics*, Vol. V; the modern Durrant-Li-Schaberg translation is not a public-domain Wikisource source. | A/B | Use Chinese Wikisource for base text; Legge for public-domain translation; Durrant-Li-Schaberg as metadata/permission-pending. |
| 史記 / Shiji / Records of the Grand Historian | Chinese Wikisource has the full 130-juan structure and individual juan pages. | English Wikisource’s *Records of the Grand Historian* page is partial, listing only a few older translated excerpts. | A for Chinese; C for English | Use Chinese Wikisource as base. For English, Watson and Nienhauser are key modern sources but rights-restricted. |

### 8.2 Additional major works

| Work | Chinese Wikisource status | English Wikisource status | Grade | Project notes |
|---|---|---|---:|---|
| 周易 / 易經 / Yijing | Chinese Wikisource has 周易 pages, including hexagram pages. | English Wikisource has a *Book of Changes* translation page and Legge material in *Sacred Books of China*. | B | Versioning and commentary layers need explicit modeling: 經, 彖, 象, 文言, 繫辭, etc. |
| 禮記 / Liji / Book of Rites | Chinese Wikisource has 禮記. | English Wikisource has a *Book of Rites* translation page; Legge’s *Li Ki* is in *Sacred Books of China*. | B | Large but feasible; chapter hierarchy must be carefully preserved. |
| 老子 / 道德經 / Daodejing | Chinese Wikisource has multiple versions and commentarial traditions, including Wang Bi and excavated/manuscript-related versions. | English Wikisource has Legge’s *Tâo Teh King* and other older translations. | A/B | Choose base version explicitly. Do not mix Wang Bi, Mawangdui, Guodian, or other versions without version IDs. |
| 莊子 / Zhuangzi | Chinese Wikisource has the work divided into 內篇, 外篇, 雜篇. | English Wikisource has Zhuangzi/Chuang Tzŭ translation pages, including older public-domain translations. | A/B | Good for prose alignment; translation styles differ substantially. |
| 孫子兵法 / Sunzi Bingfa | Chinese Wikisource marks the text as proofread by a user and “quite reliable.” | English Wikisource has Lionel Giles’s *Art of War*. | A | Good small proof-of-concept for alignment and public-domain translation. |
| 墨子 / Mozi | Chinese Wikisource has 墨子 and 孫詒讓’s 墨子閒詁. | English Wikisource coverage is less central and should be checked source by source. | B/C | Important but complicated by lost chapters, commentary, and translation availability. |
| 荀子 / Xunzi | Chinese Wikisource has 荀子. | English public-domain Wikisource translation coverage is limited/needs checking. | B | Treat modern translations as rights-restricted unless cleared. |
| 韓非子 / Han Feizi | Chinese Wikisource marks the text as proofread against reliable references; talk page notes the base text and punctuation source. | English public-domain Wikisource coverage is limited/needs checking. | B | Chinese base looks promising; rights-cleared English translation may be the bottleneck. |
| 呂氏春秋 / Lüshi chunqiu | Chinese Wikisource has the work with traditional macrostructure. | English translation coverage is not a strong Wikisource target. | B | Good Chinese base, but English side likely requires modern/licensed sources. |
| 戰國策 / Zhanguoce | Chinese Wikisource has multiple textual versions and chapter pages. | English Wikisource coverage appears limited. | B | Version selection is the main issue. |
| 國語 / Guoyu | Chinese Wikisource has 國語. | English Wikisource coverage not yet established. | B | Good target after core corpus. |
| 漢書 / Hanshu | Chinese Wikisource has 漢書. | English translation coverage is not likely to be complete on Wikisource. | B/C | Useful as a base text; English translations are complex and scattered. |
| 山海經 / Shanhaijing | Chinese Wikisource has 山海經 with Guo Pu commentary tradition. | English Wikisource coverage not established here. | B | Model commentary separately from base text. |
| 資治通鑑 / Zizhi tongjian | Chinese Wikisource has the work. | English translation coverage not established here. | B/C | Very large; better for later phases. |

---

## 9. Initial source and bibliography list

### 9.1 Public-domain and Wikisource-friendly sources

#### James Legge, *The Chinese Classics*

Legge’s *Chinese Classics* is the main public-domain English backbone for early pilots. English Wikisource’s page lists the collection as follows: Vol. I contains the Confucian Analects, Great Learning, and Doctrine of the Mean; Vol. II contains Mencius; Vol. III contains the Shoo King; Vol. IV contains the She King; Vol. V contains the Ch’un Ts’ew and Tso Chuen.

Suggested citation:

> Legge, James, trans. *The Chinese Classics*. 5 vols. Hong Kong and London, 1861–1872; 2nd ed. Oxford: Clarendon Press, 1893–1895.

Local lookup keys:

```text
Legge
James Legge
Chinese Classics
Confucian Analects
Four Books
The Great Learning
Doctrine of the Mean
Mencius
Shoo King
Shu King
She King
Shih King
Ch'un Ts'ew
Tso Chuen
Tso Chuan
Li Chi
Li Ki
Sacred Books of China
Sacred Books of the East
```

Agent notes:

- Store Legge’s translation, Chinese text, romanization, notes, and commentary separately if they are mixed on the page.
- Do not normalize Legge’s Wade-Giles/older spellings in the source field; create separate searchable aliases.
- Use the scan-backed Wikisource pages when available.

#### James Legge, *The Sacred Books of China*

Legge’s *Sacred Books of China*, published in Max Müller’s *Sacred Books of the East*, is important for the Yijing, Liji, Daodejing, Zhuangzi, Xiaojing, and related materials.

Suggested citation:

> Legge, James, trans. *The Sacred Books of China*. In *The Sacred Books of the East*, ed. F. Max Müller. Oxford: Clarendon Press, 1879–1891.

Local lookup keys:

```text
Legge
Max Müller
Muller
Sacred Books of the East
Sacred Books of China
Texts of Confucianism
Texts of Taoism
Yi King
I Ching
Li Ki
Tao Teh King
Chuang Tzu
Chuang Tzŭ
```

#### Lionel Giles, *Sun Tzŭ on the Art of War*

Suggested citation:

> Sunzi. *Sun Tzŭ on the Art of War: The Oldest Military Treatise in the World*. Translated by Lionel Giles. London: Luzac & Co., 1910.

Local lookup keys:

```text
Giles
Lionel Giles
Sun Tzu
Sun Tzŭ
Sunzi
Art of War
Ping-fa
Bingfa
```

#### William Jennings, *The Shi King*

Suggested citation:

> Jennings, William, trans. *The Shi King: The Old “Poetry Classic” of the Chinese*. London: George Routledge and Sons, 1891.

Local lookup keys:

```text
Jennings
William Jennings
Shi King
Shih King
Book of Songs
Book of Odes
Classic of Poetry
```

#### H. A. Giles, selected translations and Zhuangzi materials

Suggested search target:

```text
Giles
Herbert A. Giles
Herbert Allen Giles
Chuang Tzu
Chuang Tzŭ
Zhuangzi
Gems of Chinese Literature
Records of the Grand Historian excerpts
Ssu-ma Ch'ien
Sima Qian
```

Agent notes:

- Treat H. A. Giles as a useful public-domain source for excerpts and early translations, but verify completeness and edition before using.
- English Wikisource’s *Records of the Grand Historian* page appears to list only a few Giles excerpts, not a complete Shiji translation.

### 9.2 Modern / rights-restricted priority sources

These should be represented first as metadata and local-library targets. Do not ingest full text into a public-facing corpus until rights are cleared.

#### Bernhard Karlgren, *The Book of Odes*

Suggested citation:

> Karlgren, Bernhard, trans. *The Book of Odes: Chinese Text, Transcription and Translation*. Stockholm: Museum of Far Eastern Antiquities, 1950.

Possible reprint citation:

> Karlgren, Bernhard, trans. *The Book of Odes: Chinese Text, Transcription and Translation*. Stockholm: Museum of Far Eastern Antiquities, 1974.

Local lookup keys:

```text
Karlgren
Bernhard Karlgren
Book of Odes
Shijing
Shih Ching
Shi King
Museum of Far Eastern Antiquities
MFEA
```

Agent notes:

- This is especially valuable because it includes Chinese text, transcription, and translation.
- Treat as permission-pending or private/local only unless the legal status is clarified.

#### Stephen Durrant, Wai-yee Li, and David Schaberg, *Zuo Tradition / Zuozhuan*

Suggested citation:

> Durrant, Stephen; Li, Wai-yee; and Schaberg, David, trans. *Zuo Tradition / Zuozhuan: Commentary on the “Spring and Autumn Annals”*. Seattle: University of Washington Press, 2016.

Local lookup keys:

```text
Durrant
Stephen Durrant
Li Wai-yee
Wai-yee Li
David Schaberg
Schaberg
Zuo Tradition
Zuozhuan
Zuo zhuan
Tso Chuan
Tso Chuen
Spring and Autumn Annals
```

Agent notes:

- This is likely the principal modern English translation to consult for Zuozhuan.
- The University of Washington Press page describes the book as a 2016, 2243-page translation with original text, introduction, and annotations.
- Mark as `permission_pending` or `licensed_private` unless and until permission is obtained.

#### William H. Nienhauser Jr. and collaborators, *The Grand Scribe’s Records*

Suggested citation family:

> Sima Qian. *The Grand Scribe’s Records*. Edited and translated by William H. Nienhauser Jr. and collaborators. Bloomington: Indiana University Press, multiple volumes.

Example volume citation:

> Sima Qian. *The Grand Scribe’s Records, Vol. I: The Basic Annals of Pre-Han China*. Edited by William H. Nienhauser Jr.; translated by William H. Nienhauser Jr. and collaborators. Bloomington: Indiana University Press, 2018.

Local lookup keys:

```text
Nienhauser
William H. Nienhauser
Grand Scribe's Records
Sima Qian
Ssu-ma Ch'ien
Shiji
Shih chi
Records of the Grand Historian
Basic Annals
Hereditary Houses
Memoirs
```

Agent notes:

- Search under Nienhauser, Sima Qian, Ssu-ma Ch’ien, Shiji, Shih chi, and Grand Scribe’s Records.
- Treat as rights-restricted unless permissions are secured.
- Very important for Shiji because English Wikisource coverage is only partial.

#### Burton Watson, *Records of the Grand Historian*

Suggested citations:

> Sima Qian. *Records of the Grand Historian: Qin Dynasty*. Translated by Burton Watson. New York: Columbia University Press, 1993; paperback 1996.

> Sima Qian. *Records of the Grand Historian: Han Dynasty*, Vols. 1–2. Translated by Burton Watson. Revised ed. New York: Columbia University Press, 1993; paperback 1996.

Local lookup keys:

```text
Watson
Burton Watson
Records of the Grand Historian
Sima Qian
Ssu-ma Ch'ien
Shiji
Shih chi
Qin Dynasty
Han Dynasty
Columbia University Press
```

Agent notes:

- Essential for the translated Shiji corpus, but not a complete translation of all 130 juan.
- Rights-restricted.

#### D. C. Lau, *The Analects*

Suggested citation:

> Confucius. *The Analects*. Translated by D. C. Lau. Harmondsworth: Penguin Books, 1979.

Local lookup keys:

```text
Lau
D. C. Lau
DC Lau
Analects
Confucius
Lunyu
Lun Yü
Penguin Classics
Chinese University Press
```

Agent notes:

- Useful modern comparison to Legge, but rights-restricted.

#### Edward Slingerland, *Confucius: Analects*

Suggested citation:

> Confucius. *Analects: With Selections from Traditional Commentaries*. Translated by Edward Slingerland. Indianapolis: Hackett Publishing, 2003.

Local lookup keys:

```text
Slingerland
Edward Slingerland
Analects
Traditional Commentaries
Hackett
Confucius
Lunyu
```

Agent notes:

- Especially useful because it includes selections from traditional commentaries.
- Rights-restricted.

#### Roger T. Ames and Henry Rosemont Jr., *The Analects of Confucius: A Philosophical Translation*

Suggested citation:

> Confucius. *The Analects of Confucius: A Philosophical Translation*. Translated by Roger T. Ames and Henry Rosemont Jr. New York: Ballantine Books, 1998/1999.

Local lookup keys:

```text
Ames
Roger Ames
Rosemont
Henry Rosemont
Analects of Confucius
Philosophical Translation
Ballantine
```

Agent notes:

- Useful as a philosophically inflected modern comparator.
- Rights-restricted.

#### Paul W. Kroll / Brill dictionary

Suggested citation:

> Kroll, Paul W. *A Student’s Dictionary of Classical and Medieval Chinese*. Leiden and Boston: Brill, 2015.

Also check revised/expanded Brill editions and the online Brill Chinese-English Dictionary Online.

Local lookup keys:

```text
Kroll
Paul W. Kroll
Student's Dictionary of Classical and Medieval Chinese
Classical and Medieval Chinese
Brill
Chinese-English Dictionary Online
```

Agent notes:

- Treat Brill dictionary integration as a licensed-linking problem, not as a scraping problem.
- Store dictionary references by headword, page, Brill ID, or locally assigned dictionary-entry ID if permitted.
- Do not copy dictionary entries into the open corpus without permission.

#### John Minford and Joseph S. M. Lau, *Classical Chinese Literature: An Anthology of Translations*

Suggested citation:

> Minford, John, and Joseph S. M. Lau, eds. *Classical Chinese Literature: An Anthology of Translations. Volume I: From Antiquity to the Tang Dynasty*. New York: Columbia University Press, 2002.

Local lookup keys:

```text
Minford
John Minford
Joseph S. M. Lau
Joseph Lau
Classical Chinese Literature
Anthology of Translations
Columbia University Press
```

Agent notes:

- Useful for identifying high-quality published translations and translators across genres.
- Rights-restricted as a source text.

---

## 10. Wade-Giles, older spellings, and local-library search aliases

The local library may file books under translators, editors, classical authors, or older romanizations. Use this table for search expansion.

| Pinyin / modern form | Older / Wade-Giles / variant search strings | Notes |
|---|---|---|
| Lunyu | Lun Yü, Lun-yü, Lun Yu, Analects, Confucian Analects | Search also under Confucius and Legge. |
| Mengzi | Mencius, Meng-tzu, Meng Tzu | Usually filed as Mencius or under Legge/Lau. |
| Shijing | Shih Ching, Shi King, She King, Book of Odes, Book of Songs, Classic of Poetry | Search under Karlgren, Legge, Jennings, Waley, Allen. |
| Shujing / Shangshu | Shu Ching, Shoo King, Book of Documents, Book of History | Legge uses Shoo King. |
| Chunqiu | Ch’un Ts’ew, Ch’un-ch’iu, Spring and Autumn Annals | Often paired with Zuozhuan/Tso Chuen. |
| Zuozhuan | Tso Chuan, Tso-chuan, Tso Chuen, Tso-chuen, Zuo Tradition | Modern UW title uses Zuo Tradition / Zuozhuan. |
| Shiji | Shih chi, Shi chi, Ssu-ma Ch’ien, Sima Qian, Records of the Grand Historian, Grand Scribe’s Records | Search under both Watson and Nienhauser. |
| Hanshu | Han Shu, Han-shu, Book of Han, Ban Gu, Pan Ku | Search under Ban Gu/Pan Ku. |
| Guoyu | Kuo-yü, Kuo yu, Discourses of the States | Often linked with Warring States prose. |
| Zhanguoce | Chan-kuo Ts’e, Chan-kuo Ts'e, Strategies of the Warring States | Multiple edition titles likely. |
| Yijing / Zhouyi | I Ching, Yi King, Book of Changes, Classic of Changes | Legge often uses Yi King. |
| Liji | Li Chi, Li Ki, Book of Rites, Record of Rites | Legge uses Li Ki. |
| Laozi / Daodejing | Lao Tzu, Lao-tzu, Tao Te Ching, Tao Teh King, Dao De Jing | English Wikisource includes Tâo Teh King. |
| Zhuangzi | Chuang Tzu, Chuang-tzu, Chuang Tzŭ | H. A. Giles and Legge spellings vary. |
| Sunzi | Sun Tzu, Sun-tzu, Sun Tzŭ, Art of War, Bingfa, Ping-fa | Lionel Giles 1910 is key. |
| Mozi | Mo Tzu, Mo-tzu, Mo Ti, Mo Di | Search also under Mei, Mei Ti in older catalogues if needed. |
| Xunzi | Hsün Tzu, Hsun Tzu, Hsün-tzu, Xun Kuang | Older systems vary. |
| Han Feizi | Han Fei Tzu, Han-fei-tzu, Han Fei | Search under Han Fei as author. |
| Lüshi chunqiu | Lü-shih ch’un-ch’iu, Lü-shih ch'un-ch'iu, Lu-shih ch'un-ch'iu, Master Lü’s Spring and Autumn Annals | Diacritics may be absent. |
| Shanhaijing | Shan Hai Ching, Shan-hai ching, Classic of Mountains and Seas | Search also under Guo Pu for commentary. |
| Zizhi tongjian | Tzu-chih t’ung-chien, Tzu-chih t'ung-chien, Comprehensive Mirror | Very large; likely filed under Sima Guang. |

---

## 11. Prioritized implementation plan

### Phase 0: project skeleton

1. Create the directory tree on Synology.
2. Create `works.yml`, `sources.yml`, `persons.yml`, `rights.yml`, and `romanization_aliases.yml`.
3. Add work records for Lunyu, Mengzi, Shijing, Zuozhuan, and Shiji.
4. Add source records for Legge, Chinese Wikisource, English Wikisource, Karlgren, Durrant-Li-Schaberg, Watson, and Nienhauser.
5. Define rights statuses before ingesting any modern translation.

### Phase 1: public-domain pilot corpus

Recommended pilot order:

1. **Lunyu + Legge**: easiest proof-of-concept.
2. **Mengzi + Legge**: tests larger prose segmentation.
3. **Shijing + Legge/Jennings + Chinese Wikisource**: tests poem/stanza/line alignment.
4. **Sunzi + Lionel Giles**: compact military/prose text, useful for QC.
5. **Zuozhuan + Chinese Wikisource + Legge**: tests large chronologically structured narrative.

Expected outputs:

- raw Wikisource HTML/text;
- cleaned source files;
- section table;
- segment table;
- alignment table;
- QC report.

### Phase 2: modern-source metadata layer

Add metadata-only records for:

- Karlgren’s *Book of Odes*;
- Durrant, Li, and Schaberg’s *Zuo Tradition / Zuozhuan*;
- Watson’s *Records of the Grand Historian* volumes;
- Nienhauser’s *Grand Scribe’s Records* volumes;
- D. C. Lau, Slingerland, Ames/Rosemont for Analects;
- Minford and Lau anthology;
- Kroll/Brill dictionary.

Do not ingest full modern translation text into an exportable or public corpus until rights are resolved.

### Phase 3: local-library reconciliation

1. Search `Library Authors Alphabetical` using translator/editor names first.
2. Search again by classical author and title variants.
3. Record local file paths and file types in `local_library_lookup.yml`.
4. For PDFs/scans, record OCR status and whether OCR is permitted/needed.
5. If a file is present under Wade-Giles title, add alias to `romanization_aliases.yml`.
6. If a file lacks bibliographic metadata, create a `needs_bibliography_check` flag.

### Phase 4: alignment expansion

1. Add modern translations where rights permit private research use.
2. Align against the existing Chinese segment IDs.
3. Keep public-domain exports separate from restricted/private alignments.
4. Add translator-comparison tools only after source identity and rights metadata are stable.

### Phase 5: database and web prototype

Minimum web features:

- search by Chinese graph, normalized graph, English word, title, translator, work, and section;
- show Chinese base text and selected translations side by side;
- filter by rights status, translator, date, and source type;
- expose persistent segment URLs;
- hide or suppress restricted text unless the user/session has rights;
- show bibliographic citation and source locator for every segment.

Possible API endpoints:

```text
GET /api/works
GET /api/works/{work_id}/sections
GET /api/sections/{section_id}/segments
GET /api/segments/{segment_id}
GET /api/search?q={query}
GET /api/terms/{graph}
GET /api/alignments/{segment_id}
```

---

## 12. Agent instructions: safe operating rules

These instructions should be copied into the system or project prompt for any agent working on the corpus.

### 12.1 Do

- Always create or update metadata before fetching or processing text.
- Always record source URL, access date, local path, and rights status.
- Always keep raw files untouched.
- Always distinguish Chinese base text, translation, commentary, notes, and translator footnotes.
- Always preserve section hierarchy.
- Always mark uncertainty.
- Always generate a QC report after batch processing.
- Always use the romanization alias table when searching local files.

### 12.2 Do not

- Do not ingest modern copyrighted translations into a public corpus without permission.
- Do not scrape licensed dictionaries or databases.
- Do not silently convert Wade-Giles to pinyin in source titles or citations.
- Do not silently simplify/traditionalize Chinese text.
- Do not merge different recensions of a text under one source ID.
- Do not replace missing text with an LLM-generated translation.
- Do not treat a Wikisource page as complete simply because the title exists.
- Do not delete uncertain alignments; flag them.

### 12.3 Required output from every agent batch

Each agent batch should produce:

```text
1. metadata changes made
2. raw files added
3. cleaned files added
4. sections created or modified
5. segments created or modified
6. alignments created or modified
7. unresolved bibliographic questions
8. unresolved rights questions
9. QC warnings
10. next recommended action
```

---

## 13. Work-specific notes

### 13.1 Lunyu / Analects

Recommended pilot source pair:

- Chinese: Chinese Wikisource 論語, chapter pages.
- English: Legge, *The Chinese Classics*, Vol. I, *Confucian Analects*.

Why first:

- compact;
- stable chapter structure;
- public-domain English translation available;
- useful for testing term-level lookup.

Modern comparison sources to add as metadata:

- D. C. Lau, Penguin;
- Edward Slingerland, Hackett;
- Ames and Rosemont;
- other local copies if present.

### 13.2 Shijing / Classic of Poetry

Recommended source layers:

1. Chinese Wikisource 詩經, poem-level pages.
2. Legge’s *She King* from *Chinese Classics*, Vol. IV.
3. Jennings’s *Shi King* if needed for a second public-domain translation.
4. Karlgren as a major modern scholarly translation/transcription source, pending rights.

Segmentation:

```text
collection → section → poem → stanza → line
```

Example:

```text
shijing__guofeng-zhounan-001-guanju__line-001
```

Special issues:

- poem titles may vary by romanization;
- stanza divisions can differ;
- translators may group lines differently;
- Karlgren’s transcription should be stored as a separate representation, not merely a note.

### 13.3 Zuozhuan / Zuo Tradition

Recommended source layers:

1. Chinese Wikisource 春秋左氏傳 with Duke/year structure.
2. Legge’s *Tso Chuen* in *Chinese Classics*, Vol. V.
3. Durrant, Li, and Schaberg’s 2016 *Zuo Tradition / Zuozhuan*, pending rights.

Segmentation:

```text
Duke → year → annal/narrative/speech → paragraph
```

Special issues:

- distinguish 春秋 annal text from 左傳 narrative/commentary;
- modern translation may use different paragraphing;
- names, titles, and states need authority control.

### 13.4 Shiji / Records of the Grand Historian

Recommended source layers:

1. Chinese Wikisource 史記, 130 juan.
2. English Wikisource: only selected older translated excerpts; useful but not sufficient.
3. Burton Watson translations, rights-restricted.
4. Nienhauser’s *Grand Scribe’s Records*, rights-restricted and more comprehensive.

Segmentation:

```text
juan → macro-category → named chapter/person/topic → paragraph/anecdote
```

Macro-categories:

```text
本紀 basic annals
表 tables
書 treatises
世家 hereditary houses
列傳 biographies/memoirs
```

Special issues:

- tables are structurally different from prose and may need a separate model;
- Watson and Nienhauser do not necessarily map one-to-one by visible paragraph;
- some chapters have partial translations in anthologies or older public-domain sources.

---

## 14. Source research notes and links

Access date for links below: 2026-05-29.

### 14.1 Wikisource and online source pages

- English Wikisource, *The Chinese Classics*: <https://en.wikisource.org/wiki/The_Chinese_Classics>
- English Wikisource, Legge, *Confucian Analects*: <https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_1/Confucian_Analects>
- Chinese Wikisource, 論語: <https://zh.wikisource.org/wiki/論語>
- Chinese Wikisource, 論語/學而第一: <https://zh.wikisource.org/wiki/論語/學而第一>
- English Wikisource, Legge, *Works of Mencius*: <https://en.wikisource.org/wiki/The_Chinese_Classics/Volume_2/The_Works_of_Mencius>
- Chinese Wikisource, 孟子: <https://zh.wikisource.org/wiki/孟子>
- Chinese Wikisource, Category:孟子: <https://zh.wikisource.org/wiki/Category:孟子>
- Chinese Wikisource, 禮記/中庸: <https://zh.wikisource.org/wiki/禮記/中庸>
- English Wikisource, Portal:Chinese Classics: <https://en.wikisource.org/wiki/Portal:Chinese_Classics>
- English Wikisource, Category:Works originally in Chinese: <https://en.wikisource.org/wiki/Category:Works_originally_in_Chinese>
- English Wikisource, *Classic of Poetry*: <https://en.wikisource.org/wiki/Classic_of_Poetry>
- Chinese Wikisource, 詩經: <https://zh.wikisource.org/wiki/詩經>
- Chinese Wikisource, Category:詩經: <https://zh.wikisource.org/wiki/Category:詩經>
- English Wikisource, *Guan ju*: <https://en.wikisource.org/wiki/Guan_ju>
- Chinese Wikisource, 春秋左氏傳: <https://zh.wikisource.org/wiki/春秋左氏傳>
- Chinese Wikisource, 春秋左氏傳/全覽: <https://zh.wikisource.org/wiki/春秋左氏傳/全覽>
- Chinese Wikisource, 史記: <https://zh.wikisource.org/wiki/史記>
- Chinese Wikisource, 史記/卷086: <https://zh.wikisource.org/wiki/史記/卷086>
- English Wikisource, *Records of the Grand Historian*: <https://en.wikisource.org/wiki/Records_of_the_Grand_Historian>
- Chinese Wikisource, 道德經: <https://zh.wikisource.org/wiki/道德經>
- Chinese Wikisource, 老子(匯校版): <https://zh.wikisource.org/wiki/老子_(匯校版)>
- Chinese Wikisource, 道德經 / 王弼本: <https://zh.wikisource.org/wiki/道德經>
- English Wikisource, *Tâo Teh King*: <https://en.wikisource.org/wiki/Tâo_Teh_King>
- English Wikisource, *Tao Te Ching*: <https://en.wikisource.org/wiki/Tao_Te_Ching>
- Chinese Wikisource, 莊子: <https://zh.wikisource.org/wiki/莊子>
- English Wikisource, *Zhuangzi*: <https://en.wikisource.org/wiki/Zhuangzi>
- Chinese Wikisource, 周易: <https://zh.wikisource.org/wiki/周易>
- English Wikisource, *Book of Changes*: <https://en.wikisource.org/wiki/Book_of_Changes>
- Chinese Wikisource, 禮記: <https://zh.wikisource.org/wiki/禮記>
- English Wikisource, *Book of Rites*: <https://en.wikisource.org/wiki/Book_of_Rites>
- Chinese Wikisource, 孫子兵法: <https://zh.wikisource.org/wiki/孫子兵法>
- English Wikisource, Lionel Giles, *The Art of War*: <https://en.wikisource.org/wiki/The_Art_of_War_(Giles)>
- Chinese Wikisource, 墨子: <https://zh.wikisource.org/wiki/墨子>
- Chinese Wikisource, 墨子閒詁: <https://zh.wikisource.org/wiki/墨子閒詁>
- Chinese Wikisource, 荀子: <https://zh.wikisource.org/wiki/荀子>
- Chinese Wikisource, 韓非子: <https://zh.wikisource.org/wiki/韓非子>
- Chinese Wikisource, Talk:韓非子: <https://zh.wikisource.org/wiki/Talk:韓非子>
- Chinese Wikisource, 呂氏春秋: <https://zh.wikisource.org/wiki/呂氏春秋>
- Chinese Wikisource, 戰國策: <https://zh.wikisource.org/wiki/戰國策>
- Chinese Wikisource, 國語: <https://zh.wikisource.org/wiki/國語>
- Chinese Wikisource, 漢書: <https://zh.wikisource.org/wiki/漢書>
- Chinese Wikisource, 山海經: <https://zh.wikisource.org/wiki/山海經>
- Chinese Wikisource, 資治通鑑: <https://zh.wikisource.org/wiki/資治通鑑>

### 14.2 Publisher/catalogue pages for modern or bibliographic sources

- University of Washington Press, *Zuo Tradition / Zuozhuan*: <https://uwapress.uw.edu/book/9780295999159/zuo-tradition-zuozhuan/>
- Indiana University Press, *The Grand Scribe’s Records*, Vol. I: <https://iupress.org/9780253038555/the-grand-scribes-records-vol-i/>
- Indiana University Press, *The Grand Scribe’s Records*, Vol. VII: <https://iupress.org/9780253033420/the-grand-scribes-records-vol-vii/>
- Columbia University Press, Watson, *Records of the Grand Historian: Qin Dynasty*: <https://cup.columbia.edu/book/records-of-the-grand-historian/9780231081696>
- Columbia University Press, Watson, *Records of the Grand Historian: Han Dynasty*, Vol. 1: <https://cup.columbia.edu/book/records-of-the-grand-historian/9780231081658>
- Columbia University Press, Watson, *Records of the Grand Historian: Han Dynasty*, Vol. 2: <https://cup.columbia.edu/book/records-of-the-grand-historian/9780231081672>
- National Library of Australia catalogue, Karlgren, *The Book of Odes*: <https://catalogue.nla.gov.au/catalog/1034840>
- Brill, *Chinese-English Dictionary Online*: <https://brill.com/display/db/cedo>
- Brill, Kroll, *A Student’s Dictionary of Classical and Medieval Chinese*: <https://brill.com/display/title/24911>
- Columbia University Press, Minford and Lau anthology: <https://cup.columbia.edu/book/classical-chinese-literature/9780231096775>
- Penguin Random House, D. C. Lau, *The Analects*: <https://www.penguinrandomhouse.com/books/291979/the-analects-by-confucius-translated-with-an-introduction-by-d-c-lau/>
- Hackett, Slingerland, *Confucius: Analects*: <https://hackettpublishing.com/confucius-analects>

---

## 15. Immediate next actions

1. Create the Synology root folder and metadata skeleton.
2. Begin with `lunyu` using Chinese Wikisource and Legge.
3. Write a small script to fetch and clean Wikisource pages while preserving raw files.
4. Create a stable section ID scheme for Lunyu.
5. Export the first aligned pilot as JSONL and SQLite.
6. Run a human spot-check on one complete Lunyu book.
7. Repeat the same pipeline for Mengzi and Sunzi before attempting Shijing, Zuozhuan, or Shiji.
8. In parallel, search the local `Library Authors Alphabetical` folder with the alias table above and populate `local_library_lookup.yml`.
9. Create metadata-only records for Karlgren, Durrant-Li-Schaberg, Watson, Nienhauser, Kroll, Lau, Slingerland, Ames/Rosemont, and Minford/Lau.
10. Decide the first rights-cleared or private-only workflow for modern translations.

---

## 16. Minimal project prompt for an agent

Use the following compact version when assigning a specific ingestion task to an agent:

```text
You are working on the Classical Chinese Translation Memory Bank.

Task: ingest or prepare source material for {WORK_ID}.

Rules:
1. Create/update metadata before processing text.
2. Preserve raw files unchanged.
3. Separate Chinese base text, translation, commentary, notes, and alignment.
4. Record source URL/local path, access date, citation, and rights status.
5. Do not ingest modern copyrighted text into a public corpus unless rights are cleared.
6. Do not silently normalize Chinese characters, punctuation, romanization, or section titles.
7. Segment according to the canonical hierarchy for the work.
8. Use stable IDs for work, section, source, segment, and alignment.
9. Flag uncertain segmentation or alignment for human review.
10. Produce a QC report listing files created, metadata changed, unresolved issues, and next actions.

Output required:
- updated metadata YAML;
- raw source files;
- cleaned source files;
- segment table;
- alignment table if applicable;
- QC report.
```

---

## 17. Open questions

1. Which Chinese base text should be canonical for each work: Wikisource, a specific punctuated edition, ctext, a received-text edition, or multiple parallel versions?
2. Should the public website display only public-domain/open translations, while keeping modern translations private or metadata-only?
3. What is the exact intended relationship to Brill/Kroll: licensed lookup, citation-only reference, local cross-reference, or public integration?
4. How granular should alignment be for each genre: phrase, sentence, paragraph, poem line, annal entry, or juan?
5. How should commentaries be modeled: separate source texts, annotations on base text, or linked witnesses?
6. Should romanization conversion be handled as metadata aliases only, or should searchable normalized forms be generated for all sources?
7. What review standard is required before a work is considered “usable” for scholarly citation?
8. Which modern translations are priority targets for rights clearance?

