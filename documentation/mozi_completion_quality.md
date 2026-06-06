# Mozi completion quality

Generated from `logs/qc_reports/mozi__alignment_qc.json`.

## Summary

- Work state: proof_of_concept_partial_active
- Total detected sections: 52
- Active sections: 30
- Exportable sections: 30
- English witness: Archive.org DjVu OCR capture of Yi-Pao Mei, The Works of Motse from the Chinese (1929) for the translated chapter subset
- Exact alignments: 654
- Automatic fine-grained alignments: 654
- Total processed alignment records: 684
- Curated override sections: 1
- Remaining coarse fallbacks: 9
- Blocked sections: 22
- Hard failures: 0
- Corruption issues before repair: 532
- Corruption issues corrected: 482
- Automatic OCR/token repairs: 471
- Curated OCR/phrase repairs: 11
- Corruption issues remaining: 0
- Note/commentary leakage issues before repair: 0
- Note/commentary leakage issues repaired: 0
- Note/commentary leakage issues remaining: 0
- Alignment drift checks run: 30
- Drift issues before repair: 3
- Drift issues repaired: 0
- Drift issues remaining: 4

## Alignment granularity

- chapter: 9
- grouped: 645

## Remaining fallbacks

- `mozi-001-make-close-the-scholars`: ChineseNotes source segmentation remains too coarse for grouped alignment at this chapter scale; retained chapter-level fallback after OCR repair.
- `mozi-002-self-cultivation`: ChineseNotes source segmentation remains too coarse for grouped alignment at this chapter scale; retained chapter-level fallback after OCR repair.
- `mozi-003-that-which-is-affectable`: English OCR segmentation still requires chapter-level coarse alignment after repair because grouped alignment remained unreliable (Anchor drift remains after repair: four-good-kings (resolved_ambiguous_anchor); four-bad-kings (resolved_ambiguous_anchor); six-bad-princes (resolved_ambiguous_anchor); good-friends (resolved_ambiguous_anchor)).
- `mozi-018-condemnation-of-offensive-war-ii`: English OCR segmentation still requires chapter-level coarse alignment after repair because grouped alignment remained unreliable (Alignment QC failed for mozi-018-condemnation-of-offensive-war-ii: group 18: target segment length/structure imbalance suggests missing grouping; group 31: target segment length/structure imbalance suggests missing grouping; group 38: target segment length/structure imbalance suggests missing grouping; group 39: target segment length/structure imbalance suggests missing grouping; group 40: target segment length/structure imbalance suggests missing grouping).
- `mozi-025-on-ghosts-iii`: English OCR segmentation still requires chapter-level coarse alignment after repair because grouped alignment remained unreliable (Alignment QC failed for mozi-025-on-ghosts-iii: group 25: source/target question punctuation mismatch ('非惟若書之說為然也，昔者宋文君鮑之時，有臣曰礻後觀辜固嘗從事於厲，祩子杖揖出與言曰：「觀辜！是何珪璧之不滿度量？酒醴粢盛之不淨潔也？犧牲之不全肥？春秋冬夏選失時？' vs 'While the ministers and secretaries should spare no pains at work, they may not make the standard at will There are the high duke and feudal lords to give them the standard.')).
- `mozi-027-anti-fatalism-i`: English OCR segmentation still requires chapter-level coarse alignment after repair because grouped alignment remained unreliable (Alignment QC failed for mozi-027-anti-fatalism-i: group 30: target segment length/structure imbalance suggests missing grouping).
- `mozi-031-canon-i`: English OCR segmentation still requires chapter-level coarse alignment after repair because grouped alignment remained unreliable (Alignment QC failed for mozi-031-canon-i: group 1: target segment length/structure imbalance suggests missing grouping; group 7: target segment length/structure imbalance suggests missing grouping; group 13: target segment length/structure imbalance suggests missing grouping; group 14: target segment length/structure imbalance suggests missing grouping).
- `mozi-035-major-illustrations`: English OCR segmentation still requires chapter-level coarse alignment after repair because grouped alignment remained unreliable (Alignment QC failed for mozi-035-major-illustrations: group 25: source/target question punctuation mismatch ('小圜之圜，與大圜之圜同。不至尺之不至也，與不至千里之不至不異，其不至同者，遠近之謂也。是璜也，是玉也。意楹，非意木也，意是楹之木也。意指之人也，非意人也。意獲也，乃意禽也。' vs 'Why do you, sir, now oppose it? " (In answer,) Motse asked: Was it from the sages and good men of the Three Dynasties or from the wicked and the vicious of the Three Dynasties that the fatalistic doctrine came?')).
- `mozi-036-minor-illustrations`: English OCR segmentation still requires chapter-level coarse alignment after repair because grouped alignment remained unreliable (Alignment QC failed for mozi-036-minor-illustrations: group 3: target segment length/structure imbalance suggests missing grouping).

## Curated override sections

- `mozi-003-that-which-is-affectable`

## Anchor-mapped sections

- `mozi-003-that-which-is-affectable`

## Blocked sections

- `mozi-021-simplicity-in-funerals-iii`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-022-will-of-heaven-i`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-023-will-of-heaven-ii`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-028-anti-fatalism-ii`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-029-anti-fatalism-iii`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-032-canon-ii`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-033-exposition-of-canon-i`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-037-geng-zhu`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-039-gong-meng`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-040-lu-s-question`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-041-gong-shu`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-042-fortification-of-the-city-gate`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-043-defense-against-attack-from-an-elevation`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-044-defense-against-attack-with-ladders`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-045-preparation-against-inundation`: The committed Mei 1929 OCR witness contains this chapter number, but the extracted English resolves to unrelated dialogue or glossary material instead of the matching Mozi chapter. Leave this chapter metadata-only until a clean attributable English witness is captured.
- `mozi-046-preparation-against-a-sally`: The committed Mei 1929 OCR witness contains this chapter number, but the extracted English resolves to unrelated dialogue or glossary material instead of the matching Mozi chapter. Leave this chapter metadata-only until a clean attributable English witness is captured.
- `mozi-047-preparation-against-tunnelling`: The committed Mei 1929 OCR witness contains this chapter number, but the extracted English resolves to unrelated dialogue or glossary material instead of the matching Mozi chapter. Leave this chapter metadata-only until a clean attributable English witness is captured.
- `mozi-048-defence-against-ant-rush`: The committed Mei 1929 OCR witness contains this chapter number, but the extracted English resolves to unrelated dialogue or glossary material instead of the matching Mozi chapter. Leave this chapter metadata-only until a clean attributable English witness is captured.
- `mozi-049-the-sacrifice-against-the-coming-of-the-enemy`: The committed Mei 1929 OCR witness contains this chapter number, but the extracted English resolves to unrelated dialogue or glossary material instead of the matching Mozi chapter. Leave this chapter metadata-only until a clean attributable English witness is captured.
- `mozi-050-flags-and-pennants`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-051-commands-and-orders`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.
- `mozi-052-miscellaneous-measures-in-defense`: No clean attributed English witness has been captured for this chapter. The committed Mei 1929 OCR witness does not cover this chapter and no secondary witness has been staged.

## Proof-of-concept rights posture
- Active Mozi exports: 30
- Rights review required: 30
- Release-ready chapters: 0
- Metadata-only genuine blockers: 22
