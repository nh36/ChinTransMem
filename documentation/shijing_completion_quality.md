# Shijing completion quality audit

This report complements the structural preflight checks with verification-ledger enforcement for exportable *Shijing* poems.

## Summary

| Metric | Count |
| --- | ---: |
| section_count | 311 |
| extant_poem_count | 305 |
| exportable_extant_poems | 305 |
| non_exportable_extant_poems | 0 |
| title_only_lost_text_entries | 6 |
| remaining_likely_repairable_cases | 0 |
| remaining_needs_better_witness_cases | 0 |
| remaining_known_unrecoverable_cases | 0 |
| complete_sections | 305 |
| metadata_only_sections | 6 |
| non_exportable_extant_sections | 0 |
| exact_alignment_count | 757 |
| ocr_or_fulltext_derived_sections | 202 |
| sections_needing_human_text_review | 0 |
| sections_with_coarse_alignment | 90 |
| sections_with_single_poem_alignment | 97 |
| sections_with_extreme_length_ratio | 0 |
| sections_with_possible_commentary_leakage | 0 |
| sections_with_suspicious_ocr_artifacts | 0 |
| sections_with_hard_failures | 0 |
| hard_failure_count | 0 |
| warning_count | 35 |

## Progress

| Metric | Count |
| --- | ---: |
| total_extant_poems | 305 |
| verified_exportable_poems | 305 |
| non_exportable_extant_poems | 0 |
| title_only_lost_text_entries | 6 |
| all_human_verified_ocr_sections | 182 |
| non_exportable_repair_queue_remaining | 0 |
| current_repair_batch | 2026-05-31-11-shijing-chinesenotes-recovery |
| newly_repaired_in_current_batch | 16 |

## Current batch summary

| Metric | Count |
| --- | ---: |
| repair_batch | 2026-05-31-11-shijing-chinesenotes-recovery |
| latest_review_date | 2026-05-31 |
| newly_repaired_in_current_batch | 16 |
| human_verified_ocr_sections_in_current_batch | 0 |
| human_verified_fulltext_sections_in_current_batch | 16 |

## Newly repaired in current batch

| Section | Title | Canonical ref | Verification status |
| --- | --- | --- | --- |
| guofeng-zhaonan-006 | 行露 | 詩經·國風·召南·006 | human_verified_fulltext |
| guofeng-tangfeng-006 | 杕杜 | 詩經·國風·唐風·006 | human_verified_fulltext |
| guofeng-wangfeng-005 | 中谷有蓷 | 詩經·國風·王風·005 | human_verified_fulltext |
| guofeng-wangfeng-010 | 丘中有麻 | 詩經·國風·王風·010 | human_verified_fulltext |
| guofeng-weifeng-006 | 芄蘭 | 詩經·國風·衛風·006 | human_verified_fulltext |
| guofeng-binfeng-003 | 東山 | 詩經·國風·豳風·003 | human_verified_fulltext |
| guofeng-beifeng-001 | 柏舟 | 詩經·國風·邶風·001 | human_verified_fulltext |
| guofeng-beifeng-010 | 谷風 | 詩經·國風·邶風·010 | human_verified_fulltext |
| guofeng-beifeng-019 | 二子乘舟 | 詩經·國風·邶風·019 | human_verified_fulltext |
| guofeng-yongfeng-008 | 相鼠 | 詩經·國風·鄘風·008 | human_verified_fulltext |
| guofeng-zhengfeng-009 | 有女同車 | 詩經·國風·鄭風·009 | human_verified_fulltext |
| guofeng-chenfeng-009 | 株林 | 詩經·國風·陳風·009 | human_verified_fulltext |
| guofeng-weifeng-state-002 | 汾沮洳 | 詩經·國風·魏風·002 | human_verified_fulltext |
| guofeng-weifeng-state-003 | 園有桃 | 詩經·國風·魏風·003 | human_verified_fulltext |
| guofeng-weifeng-state-006 | 伐檀 | 詩經·國風·魏風·006 | human_verified_fulltext |
| guofeng-qifeng-003 | 著 | 詩經·國風·齊風·003 | human_verified_fulltext |

## Sections investigated but left non-exportable in this pass

| Section | Title | Canonical ref | Category | Source anchor | Note |
| --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — |

## Previous OCR repair batches

| Repair batch | Section count | human_verified_ocr | human_verified_fulltext |
| --- | ---: | ---: | ---: |
| 2026-05-30-01-zhaonan | 9 | 9 | 0 |
| 2026-05-30-02-beifeng | 13 | 13 | 0 |
| 2026-05-30-03-yongfeng | 6 | 6 | 0 |
| 2026-05-30-04-weifeng-wangfeng | 12 | 12 | 0 |
| 2026-05-30-05-zheng-qi-wei-tang | 34 | 34 | 0 |
| 2026-05-30-06-chen-qin-binfeng-cao-kuai-leftovers | 29 | 29 | 0 |
| 2026-05-30-07-guofeng-cleanup-xiaoya-start | 30 | 30 | 0 |
| 2026-05-31-08-xiaoya-completion-daya-song-start | 25 | 25 | 0 |
| 2026-05-31-09-shijing-finalization | 4 | 4 | 0 |
| 2026-05-31-10-shijing-last20-recovery-start | 4 | 0 | 4 |
| pre-batch verified | 20 | 20 | 0 |

## OCR sanity tests added

| Sample pattern | Detector |
| --- | --- |
| 0 Chung | zero_vocative_confusion |
| m}r | brace_artifact |
| \vill | backslash_artifact |
| Ts4ing | digit_letter_confusion |
| Cho'v | apostrophe_vw_artifact |
| Ho'v | apostrophe_vw_artifact |
| Wliere | tli_wli_artifact |
| tliey | tli_wli_artifact |
| coiifure | double_i_artifact |
| silk7 | digit_letter_confusion |
| Ae^-stone | caret_artifact |
| greatl)7 | paren_digit_intraword_artifact |
| greyj | trailing_j_artifact |
| I have here admirable guests, | terminal_truncation_punctuation |

## Current OCR sweep result

| Metric | Count |
| --- | ---: |
| checked_exportable_ocr_sections | 182 |
| flagged_sections | 0 |

| Section | Title | Canonical ref | Artifact markers | Matches |
| --- | --- | --- | --- | --- |
| — | — | — | — | — |

## Sections corrected in this pass

| Section | Title | Canonical ref | Source anchor | Note |
| --- | --- | --- | --- | --- |
| guofeng-tangfeng-004 | 椒聊 | 詩經·國風·唐風·004 | part-1 hOCR page 381; CTI AnoShih.html 1.10.117 | OCR sanity sweep corrected: rechecked part-1 hOCR p.381 against CTI AnoShih.html 1.10.117, restored the opening refrain line, and split the two verified stanzas for stanza-level export. |
| guofeng-qifeng-010 | 載驅 | 詩經·國風·齊風·010 | part-1 hOCR pages 362-363; CTI AnoShih.html 1.8.105 | OCR sanity sweep corrected: rechecked part-1 hOCR pp.362-363 against CTI AnoShih.html 1.8.105 and restored the stanza-4 closing full stop after preserving only the verse lines. |
| xiaoya-nanyoujiayu-006 | 蓼蕭 | 詩經·小雅·南有嘉魚之什·006 | part-2 hOCR pages 38-40; CTI AnoShih.html 2.2.173 | OCR sanity sweep corrected: rechecked part-2 hOCR pages 38-40 against CTI AnoShih.html 2.2.173, fixed the opening OCR slip, restored the missing stanza break, and split the four verified stanzas for export. |
| xiaoya-futian-006 | 鴛鴦 | 詩經·小雅·甫田之什·006 | part-2 hOCR pages 152-154; CTI AnoShih.html 2.7.216 | OCR sanity sweep corrected: rechecked part-2 hOCR pages 152-154 against CTI AnoShih.html 2.7.216, restored the missing opening stanza, removed the following KUI BIAN carry-over, and split the four verified stanzas for export. |
| xiaoya-hongyan-006 | 白駒 | 詩經·小雅·鴻鴈之什·006 | part-2 hOCR pages 63-65; CTI AnoShih.html 2.4.186 | OCR sanity sweep corrected: rechecked part-2 hOCR pages 63-65 against CTI AnoShih.html 2.4.186, removed the trailing DECADE OF K'E FOO heading, and split the four verified stanza blocks for export. |
| xiaoya-luming-001 | 鹿鳴 | 詩經·小雅·鹿鳴之什·001 | part-2 hOCR pages 9-11; CTI AnoShih 2.1.161 | OCR sanity sweep corrected: restored the truncated final stanza after checking part-2 hOCR pages 9-11 against the public-domain CTI transcription for AnoShih 2.1.161, while retaining stanza-level alignment. |
| xiaoya-luming-003 | 皇皇者華 | 詩經·小雅·鹿鳴之什·003 | part-2 hOCR pages 13-14; CTI AnoShih 2.1.163 | OCR sanity sweep corrected: replaced the lingering greyj OCR corruption after checking part-2 hOCR pages 13-14 against the public-domain CTI transcription for AnoShih 2.1.163, while retaining stanza-level alignment. |
| xiaoya-luming-004 | 常棣 | 詩經·小雅·鹿鳴之什·004 | part-2 hOCR pages 14-17; CTI AnoShih 2.1.164 | OCR sanity sweep corrected: fixed the greatl)7 OCR corruption and restored the missing closing line after checking part-2 hOCR pages 14-17 against the public-domain CTI transcription for AnoShih 2.1.164, while retaining stanza-level alignment. |

## Sections moved back to non-exportable in this pass

| Section | Title | Canonical ref | Source anchor | Note |
| --- | --- | --- | --- | --- |
| — | — | — | — | — |

## Ledger-backed OCR overrides

| Section | Title | Canonical ref | Source anchor | Override matches |
| --- | --- | --- | --- | --- |
| — | — | — | — | — |

## Remaining unresolved sections by category

| Metric | Count |
| --- | ---: |
| Known unrecoverable with current witness | 0 |
| Likely repairable now | 0 |
| Needs better witness | 0 |
| Not yet investigated in detail | 0 |

## Remaining repair queue by subdivision

| Metric | Count |
| --- | ---: |
| — | 0 |

## Remaining Guofeng items

| Metric | Count |
| --- | ---: |
| — | 0 |

### Likely repairable now

| Section | Title | Canonical ref | Reason |
| --- | --- | --- | --- |
| — | — | — | — |

### Not yet investigated in detail

| Section | Title | Canonical ref | Reason |
| --- | --- | --- | --- |
| — | — | — | — |

### Known unrecoverable with current witness

| Section | Title | Canonical ref | Reason |
| --- | --- | --- | --- |
| — | — | — | — |

### Needs better witness

| Section | Title | Canonical ref | Reason |
| --- | --- | --- | --- |
| — | — | — | — |

## Remaining Xiaoya items

| Metric | Count |
| --- | ---: |
| — | 0 |

| Section | Title | Canonical ref | Queue category | Reason |
| --- | --- | --- | --- | --- |
| — | — | — | — | — |

## Remaining Daya/Song items

| Metric | Count |
| --- | ---: |
| — | 0 |

| Section | Title | Canonical ref | Queue category | Reason |
| --- | --- | --- | --- | --- |
| — | — | — | — | — |

## Known unrecoverable cases

| Section | Title | Canonical ref | Reason |
| --- | --- | --- | --- |
| — | — | — | — |

## Cases needing a better witness

| Section | Title | Canonical ref | Queue category | Reason |
| --- | --- | --- | --- | --- |
| — | — | — | — | — |


## Witness mix

| Witness type | Complete sections |
| --- | ---: |
| OCR-derived witness | 182 |
| SBE transcluded page | 102 |
| full-text derived witness | 20 |
| standalone Wikisource | 1 |

## Verification status mix

| Status | Complete sections |
| --- | ---: |
| human_verified_fulltext | 20 |
| human_verified_ocr | 182 |
| verified_transcribed_text | 103 |

## Thresholds

| Heuristic | Value |
| --- | ---: |
| english_word_short_threshold | 44 |
| english_word_long_threshold | 327 |
| english_to_chinese_ratio_low_threshold | 1.678 |
| english_to_chinese_ratio_high_threshold | 8.000 |

## Non-exportable repair queue

| Section | Title | Verification status | Decision | Notes |
| --- | --- | --- | --- | --- |

## Most flagged sections

| Section | Title | Witness | Words | Ratio | Flags |
| --- | --- | --- | ---: | ---: | --- |
| xiaoya-jienanshan-003 | 十月之交 | SBE transcluded page | 327 | 4.336 | suspiciously long English text, poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-gufeng-003 | 大東 | SBE transcluded page | 367 | 5.502 | suspiciously long English text, poem-level alignment may hide recoverable stanza segmentation |
| daya-dang-002 | 抑 | SBE transcluded page | 471 | 3.688 | suspiciously long English text, poem-level alignment may hide recoverable stanza segmentation |
| song-lusong-004 | 閟宮 | SBE transcluded page | 863 | 6.466 | suspiciously long English text, poem-level alignment may hide recoverable stanza segmentation |
| guofeng-beifeng-010 | 谷風 | full-text derived witness | 322 | 4.069 | poem-level alignment may hide recoverable stanza segmentation |
| guofeng-zhengfeng-018 | 揚之水 | OCR-derived witness | 92 | 1.513 | poem-level alignment may hide recoverable stanza segmentation |
| guofeng-qifeng-007 | 甫田 | OCR-derived witness | 84 | 1.375 | poem-level alignment may hide recoverable stanza segmentation |
| guofeng-tangfeng-009 | 無衣 | OCR-derived witness | 78 | 3.099 | poem-level alignment may hide recoverable stanza segmentation |
| guofeng-qinfeng-008 | 無衣 | OCR-derived witness | 112 | 4.063 | poem-level alignment may hide recoverable stanza segmentation |
| guofeng-binfeng-003 | 東山 | full-text derived witness | 333 | 6.224 | suspiciously long English text |
| xiaoya-nanyoujiayu-011 | 采芑 | OCR-derived witness | 331 | 6.571 | suspiciously long English text |
| xiaoya-hongyan-009 | 斯干 | SBE transcluded page | 219 | 3.652 | poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-jienanshan-001 | 節南山 | SBE transcluded page | 452 | 6.378 | suspiciously long English text |
| xiaoya-jienanshan-006 | 小宛 | SBE transcluded page | 130 | 9.600 | poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-jienanshan-009 | 何人斯 | OCR-derived witness | 330 | 5.432 | suspiciously long English text |

## Extreme English/Chinese ratios

| Section | Title | Ratio | Witness | Notes |
| --- | --- | ---: | --- | --- |
| guofeng-beifeng-001 | 柏舟 | 11.250 | full-text derived witness | — |
| guofeng-zhaonan-014 | 騶虞 | 11.062 | OCR-derived witness | — |
| xiaoya-jienanshan-006 | 小宛 | 9.600 | SBE transcluded page | poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-luming-010 | 魚麗 | 8.580 | OCR-derived witness | — |
| daya-dang-007 | 韓奕 | 8.317 | SBE transcluded page | — |
| song-chengong-008 | 載見 | 8.208 | SBE transcluded page | — |
| song-minyuxiaozi-010 | 賚 | 8.161 | SBE transcluded page | — |
| song-shangsong-002 | 烈祖 | 8.089 | SBE transcluded page | — |
| daya-shengmin-009 | 民勞 | 8.080 | SBE transcluded page | — |
| guofeng-binfeng-004 | 破斧 | 8.078 | OCR-derived witness | — |

## Hard failures

- None.
