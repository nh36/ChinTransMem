# Liji completion quality

Generated from `logs/qc_reports/liji__alignment_qc.json`.

## Summary

- Work state: proof_of_concept_active
- Total detected sections: 49
- Active sections: 49
- Exportable sections: 49
- English witness: ChineseNotes bilingual mirror of James Legge's Li Ki / Book of Rites translation
- Exact alignments: 1876
- Automatic fine-grained alignments: 1876
- Total processed alignment records: 1925
- Curated override sections: 0
- Remaining coarse fallbacks: 0
- Blocked sections: 0
- Hard failures: 0
- Corruption issues before repair: 0
- Corruption issues corrected: 0
- Automatic OCR/token repairs: 4
- Curated OCR/phrase repairs: 0
- Corruption issues remaining: 0
- Note/commentary leakage issues before repair: 4
- Note/commentary leakage issues repaired: 4
- Note/commentary leakage issues remaining: 0
- Drift issues remaining: 0

## Alignment granularity

- block: 1637
- grouped: 239

## Remaining fallbacks

- None.

## Curated override sections

- None.

## Anchor-mapped sections

- `liji-019-record-of-music`
- `liji-031-the-state-of-equilibrium-and-harmony`
- `liji-042-the-great-learning`

## Blocked sections

- None.

## Former fallback diagnostics

- `liji-015-record-of-small-matters-in-the-dress-of`: zh blocks 73, en blocks 73, zh segments 154, en segments 187; stable internal divisions: no; title/notices interfering: yes; merged English paragraphs: yes; Chinese segmentation too coarse: yes; scope: resolved. The Chinese and English chapter files share the same 73 paragraph blocks, but a few English paragraphs merge adjacent mourning-rule cases, so 4-target monotonic grouping was too tight. The mismatch is local rather than global. Raised the grouped-alignment window to permit slightly larger English clusters while keeping the original order.
- `liji-019-record-of-music`: zh blocks 67, en blocks 67, zh segments 456, en segments 562; stable internal divisions: yes; title/notices interfering: yes; merged English paragraphs: yes; Chinese segmentation too coarse: yes; scope: resolved. The later half of the English witness merges long conceptual runs around music, ritual, government, and the Marquis Wen / Wu dialogue, so direct sentence grouping drifted across topic boundaries. The mismatch is global across major topic shifts rather than a heading or note leak. Partitioned the joined chapter by deterministic anchor topics, then aligned the resulting macro-blocks safely.
- `liji-031-the-state-of-equilibrium-and-harmony`: zh blocks 39, en blocks 39, zh segments 348, en segments 415; stable internal divisions: yes; title/notices interfering: yes; merged English paragraphs: yes; Chinese segmentation too coarse: yes; scope: resolved. The Chinese and English files stay parallel in broad order, but Legge's prose runs more continuously across the sincerity, governance, and sagely-power expositions, so unguided grouping drifted late in the chapter. The mismatch is global across major conceptual units rather than local page furniture. Partitioned the chapter by doctrinal anchors for equilibrium/harmony, the superior man, spirits, governance, sincerity, and the closing sage material before alignment.
- `liji-042-the-great-learning`: zh blocks 16, en blocks 17, zh segments 168, en segments 168; stable internal divisions: yes; title/notices interfering: yes; merged English paragraphs: no; Chinese segmentation too coarse: no; scope: resolved. The English witness compresses several governance and wealth-policy passages into longer macro-paragraphs, and the raw chapter has 16 Chinese blocks against 17 English blocks. The mismatch is structural but still ordered, with stable internal divisions available. Partitioned the chapter by the classic Great Learning progression from illustrious virtue through family, state, and kingdom governance before alignment.
