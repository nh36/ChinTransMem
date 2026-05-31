# Shijing completion quality audit

This report complements the structural preflight checks with verification-ledger enforcement for exportable *Shijing* poems.

## Summary

| Metric | Count |
| --- | ---: |
| section_count | 311 |
| extant_poem_count | 305 |
| exportable_extant_poems | 285 |
| non_exportable_extant_poems | 20 |
| title_only_lost_text_entries | 6 |
| remaining_likely_repairable_cases | 0 |
| remaining_needs_better_witness_cases | 18 |
| remaining_known_unrecoverable_cases | 2 |
| complete_sections | 285 |
| metadata_only_sections | 26 |
| non_exportable_extant_sections | 20 |
| exact_alignment_count | 708 |
| ocr_or_fulltext_derived_sections | 182 |
| sections_needing_human_text_review | 0 |
| sections_with_coarse_alignment | 88 |
| sections_with_single_poem_alignment | 95 |
| sections_with_extreme_length_ratio | 0 |
| sections_with_possible_commentary_leakage | 0 |
| sections_with_suspicious_ocr_artifacts | 0 |
| sections_with_hard_failures | 0 |
| hard_failure_count | 0 |
| warning_count | 33 |

## Progress

| Metric | Count |
| --- | ---: |
| total_extant_poems | 305 |
| verified_exportable_poems | 285 |
| non_exportable_extant_poems | 20 |
| title_only_lost_text_entries | 6 |
| all_human_verified_ocr_sections | 182 |
| non_exportable_repair_queue_remaining | 20 |
| current_repair_batch | 2026-05-31-09-shijing-finalization |
| newly_repaired_in_current_batch | 4 |

## Current batch summary

| Metric | Count |
| --- | ---: |
| repair_batch | 2026-05-31-09-shijing-finalization |
| latest_review_date | 2026-05-31 |
| newly_repaired_in_current_batch | 4 |
| human_verified_ocr_sections_in_current_batch | 4 |
| human_verified_fulltext_sections_in_current_batch | 0 |

## Newly repaired in current batch

| Section | Title | Canonical ref | Verification status |
| --- | --- | --- | --- |
| guofeng-tangfeng-002 | 山有樞 | 詩經·國風·唐風·002 | human_verified_ocr |
| guofeng-weifeng-010 | 木瓜 | 詩經·國風·衛風·010 | human_verified_ocr |
| guofeng-beifeng-017 | 靜女 | 詩經·國風·邶風·017 | human_verified_ocr |
| guofeng-qifeng-002 | 還 | 詩經·國風·齊風·002 | human_verified_ocr |

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
| Needs better witness | 18 |
| Known unrecoverable with current witness | 2 |
| Likely repairable now | 0 |
| Not yet investigated in detail | 0 |

## Remaining repair queue by subdivision

| Metric | Count |
| --- | ---: |
| 國風 / 鄭風 | 5 |
| 國風 / 邶風 | 3 |
| 國風 / 魏風 | 3 |
| 國風 / 王風 | 2 |
| 國風 / 召南 | 1 |
| 國風 / 唐風 | 1 |
| 國風 / 衛風 | 1 |
| 國風 / 豳風 | 1 |
| 國風 / 鄘風 | 1 |
| 國風 / 陳風 | 1 |
| 國風 / 齊風 | 1 |

## Remaining Guofeng items

| Metric | Count |
| --- | ---: |
| 國風 / 鄭風 | 5 |
| 國風 / 邶風 | 3 |
| 國風 / 魏風 | 3 |
| 國風 / 王風 | 2 |
| 國風 / 召南 | 1 |
| 國風 / 唐風 | 1 |
| 國風 / 衛風 | 1 |
| 國風 / 豳風 | 1 |
| 國風 / 鄘風 | 1 |
| 國風 / 陳風 | 1 |
| 國風 / 齊風 | 1 |

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
| guofeng-beifeng-019 | 二子乘舟 | 詩經·國風·邶風·019 | Checked part-1 hOCR pp.273-274. The poem body is almost entirely unrecoverable in the current hOCR witness, so no verified English text can be exported yet. |
| guofeng-chenfeng-009 | 株林 | 詩經·國風·陳風·009 | Checked part-1 hOCR page 415. The translation column collapses into glyph debris immediately after the title, so no recoverable verse lines survive in the current witness. |

### Needs better witness

| Section | Title | Canonical ref | Reason |
| --- | --- | --- | --- |
| guofeng-zhaonan-006 | 行露 | 詩經·國風·召南·006 | Checked part-1 hOCR pp.229-230. Only the closing stanza survives legibly; the opening stanzas dissolve into mixed Chinese/OCR noise, so this witness cannot yet support a clean export. |
| guofeng-tangfeng-006 | 杕杜 | 詩經·國風·唐風·006 | Checked part-1 hOCR pp.383-384. The verse is interrupted by Mencius commentary fragments and a repeated closing block, so the poem boundary is not yet safe. |
| guofeng-wangfeng-005 | 中谷有蓷 | 詩經·國風·王風·005 | Checked part-1 hOCR pp.318-319. One stanza falls back across the preceding 揚之水 range and the remaining lines do not yield a complete clean witness, so this poem stays non-exportable. |
| guofeng-wangfeng-010 | 丘中有麻 | 詩經·國風·王風·010 | Checked part-1 hOCR pp.324-325. The final stanza ends in OCR/Chinese contamination ("They will give me 是細 -stones for my girdie"), so the witness is not yet clean enough for export. |
| guofeng-weifeng-006 | 芄蘭 | 詩經·國風·衛風·006 | Checked part-1 hOCR pp.305-306. The surviving lines on p.305 are mostly gibberish, and the recovered verse on p.306 resolves into the following 河廣 witness, so the poem boundary is not yet safe. |
| guofeng-binfeng-003 | 東山 | 詩經·國風·豳風·003 | Checked part-1 hOCR pages 437-440. The witness merges stanza 1 with commentary debris, drops the return line in stanza 3, and truncates stanza 4 after its opening couplet, so the full poem is not recoverable cleanly. |
| guofeng-beifeng-001 | 柏舟 | 詩經·國風·邶風·001 | Checked part-1 hOCR pp.240-242. Stanzas 1, 2, 4, and 5 are partly recoverable, but stanza 3 breaks into gibberish and the paired Chinese page also contains the separate 鄘·柏舟 entry, so the source pairing is not yet safe. |
| guofeng-beifeng-010 | 谷風 | 詩經·國風·邶風·010 | Checked part-1 hOCR pp.257-260. The first six stanzas are partly recoverable, but the remaining stanzas are not cleanly separable from commentary and page-break noise, so export would still be incomplete. |
| guofeng-yongfeng-008 | 相鼠 | 詩經·國風·鄘風·008 | Checked part-1 hOCR pp.286-287. Only stanza 1 is legible in the current witness; stanzas 2 and 3 drop out before the next book heading, so the poem remains incomplete and non-exportable. |
| guofeng-zhengfeng-001 | 緇衣 | 詩經·國風·鄭風·001 | Checked part-1 hOCR pp.326-327. Only two partial stanzas survive before the witness breaks off, so the poem remains incomplete in the current source. |
| guofeng-zhengfeng-008 | 女曰鷄鳴 | 詩經·國風·鄭風·008 | Checked part-1 hOCR pp.336-338. The opening stanza survives only as two dialogue lines before the rest of the poem continues, so the current witness does not preserve a clean full-poem boundary. |
| guofeng-zhengfeng-009 | 有女同車 | 詩經·國風·鄭風·009 | Checked part-1 hOCR pp.338-339. Only the opening stanza survives before the ODES OF CH'ING running heading, so the poem is incomplete in the current witness. |
| guofeng-zhengfeng-010 | 山有扶蘇 | 詩經·國風·鄭風·010 | Checked part-1 hOCR pp.339-340. The middle of the witness collapses into unreadable OCR gibberish between the opening and closing lines, so the poem cannot yet be verified cleanly. |
| guofeng-zhengfeng-021 | 溱洧 | 詩經·國風·鄭風·021 | Checked part-1 hOCR pp.345-347. The dialogue stanzas are misordered and partially repeated across the page break, so the full poem sequence is not yet recoverable from this witness. |
| guofeng-weifeng-state-002 | 汾沮洳 | 詩經·國風·魏風·002 | Checked part-1 hOCR pp.366-367. The first stanza runs straight into the following 園有桃 witness and the poem boundary is not recoverable cleanly. |
| guofeng-weifeng-state-003 | 園有桃 | 詩經·國風·魏風·003 | Checked part-1 hOCR pp.367-369. The stanza order is mixed and the opening lines are partly lost to OCR debris, so the poem cannot yet be verified cleanly. |
| guofeng-weifeng-state-006 | 伐檀 | 詩經·國風·魏風·006 | Checked part-1 hOCR pp.371-373. The second stanza breaks off at the page edge and the remaining witness does not preserve a clean continuation, so the poem stays non-exportable. |
| guofeng-qifeng-003 | 著 | 詩經·國風·齊風·003 | Checked part-1 hOCR pp.354-355. The key gem-name lines are OCR-corrupt in every stanza, so the translation cannot be normalized confidently from this witness alone. |

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
| guofeng-beifeng-019 | 二子乘舟 | 詩經·國風·邶風·019 | Checked part-1 hOCR pp.273-274. The poem body is almost entirely unrecoverable in the current hOCR witness, so no verified English text can be exported yet. |
| guofeng-chenfeng-009 | 株林 | 詩經·國風·陳風·009 | Checked part-1 hOCR page 415. The translation column collapses into glyph debris immediately after the title, so no recoverable verse lines survive in the current witness. |

## Cases needing a better witness

| Section | Title | Canonical ref | Queue category | Reason |
| --- | --- | --- | --- | --- |
| guofeng-zhaonan-006 | 行露 | 詩經·國風·召南·006 | Needs better witness | Checked part-1 hOCR pp.229-230. Only the closing stanza survives legibly; the opening stanzas dissolve into mixed Chinese/OCR noise, so this witness cannot yet support a clean export. |
| guofeng-tangfeng-006 | 杕杜 | 詩經·國風·唐風·006 | Needs better witness | Checked part-1 hOCR pp.383-384. The verse is interrupted by Mencius commentary fragments and a repeated closing block, so the poem boundary is not yet safe. |
| guofeng-wangfeng-005 | 中谷有蓷 | 詩經·國風·王風·005 | Needs better witness | Checked part-1 hOCR pp.318-319. One stanza falls back across the preceding 揚之水 range and the remaining lines do not yield a complete clean witness, so this poem stays non-exportable. |
| guofeng-wangfeng-010 | 丘中有麻 | 詩經·國風·王風·010 | Needs better witness | Checked part-1 hOCR pp.324-325. The final stanza ends in OCR/Chinese contamination ("They will give me 是細 -stones for my girdie"), so the witness is not yet clean enough for export. |
| guofeng-weifeng-006 | 芄蘭 | 詩經·國風·衛風·006 | Needs better witness | Checked part-1 hOCR pp.305-306. The surviving lines on p.305 are mostly gibberish, and the recovered verse on p.306 resolves into the following 河廣 witness, so the poem boundary is not yet safe. |
| guofeng-binfeng-003 | 東山 | 詩經·國風·豳風·003 | Needs better witness | Checked part-1 hOCR pages 437-440. The witness merges stanza 1 with commentary debris, drops the return line in stanza 3, and truncates stanza 4 after its opening couplet, so the full poem is not recoverable cleanly. |
| guofeng-beifeng-001 | 柏舟 | 詩經·國風·邶風·001 | Needs better witness | Checked part-1 hOCR pp.240-242. Stanzas 1, 2, 4, and 5 are partly recoverable, but stanza 3 breaks into gibberish and the paired Chinese page also contains the separate 鄘·柏舟 entry, so the source pairing is not yet safe. |
| guofeng-beifeng-010 | 谷風 | 詩經·國風·邶風·010 | Needs better witness | Checked part-1 hOCR pp.257-260. The first six stanzas are partly recoverable, but the remaining stanzas are not cleanly separable from commentary and page-break noise, so export would still be incomplete. |
| guofeng-yongfeng-008 | 相鼠 | 詩經·國風·鄘風·008 | Needs better witness | Checked part-1 hOCR pp.286-287. Only stanza 1 is legible in the current witness; stanzas 2 and 3 drop out before the next book heading, so the poem remains incomplete and non-exportable. |
| guofeng-zhengfeng-001 | 緇衣 | 詩經·國風·鄭風·001 | Needs better witness | Checked part-1 hOCR pp.326-327. Only two partial stanzas survive before the witness breaks off, so the poem remains incomplete in the current source. |
| guofeng-zhengfeng-008 | 女曰鷄鳴 | 詩經·國風·鄭風·008 | Needs better witness | Checked part-1 hOCR pp.336-338. The opening stanza survives only as two dialogue lines before the rest of the poem continues, so the current witness does not preserve a clean full-poem boundary. |
| guofeng-zhengfeng-009 | 有女同車 | 詩經·國風·鄭風·009 | Needs better witness | Checked part-1 hOCR pp.338-339. Only the opening stanza survives before the ODES OF CH'ING running heading, so the poem is incomplete in the current witness. |
| guofeng-zhengfeng-010 | 山有扶蘇 | 詩經·國風·鄭風·010 | Needs better witness | Checked part-1 hOCR pp.339-340. The middle of the witness collapses into unreadable OCR gibberish between the opening and closing lines, so the poem cannot yet be verified cleanly. |
| guofeng-zhengfeng-021 | 溱洧 | 詩經·國風·鄭風·021 | Needs better witness | Checked part-1 hOCR pp.345-347. The dialogue stanzas are misordered and partially repeated across the page break, so the full poem sequence is not yet recoverable from this witness. |
| guofeng-weifeng-state-002 | 汾沮洳 | 詩經·國風·魏風·002 | Needs better witness | Checked part-1 hOCR pp.366-367. The first stanza runs straight into the following 園有桃 witness and the poem boundary is not recoverable cleanly. |
| guofeng-weifeng-state-003 | 園有桃 | 詩經·國風·魏風·003 | Needs better witness | Checked part-1 hOCR pp.367-369. The stanza order is mixed and the opening lines are partly lost to OCR debris, so the poem cannot yet be verified cleanly. |
| guofeng-weifeng-state-006 | 伐檀 | 詩經·國風·魏風·006 | Needs better witness | Checked part-1 hOCR pp.371-373. The second stanza breaks off at the page edge and the remaining witness does not preserve a clean continuation, so the poem stays non-exportable. |
| guofeng-qifeng-003 | 著 | 詩經·國風·齊風·003 | Needs better witness | Checked part-1 hOCR pp.354-355. The key gem-name lines are OCR-corrupt in every stanza, so the translation cannot be normalized confidently from this witness alone. |


## Witness mix

| Witness type | Complete sections |
| --- | ---: |
| OCR-derived witness | 182 |
| SBE transcluded page | 102 |
| standalone Wikisource | 1 |

## Verification status mix

| Status | Complete sections |
| --- | ---: |
| human_verified_ocr | 182 |
| verified_transcribed_text | 103 |

## Thresholds

| Heuristic | Value |
| --- | ---: |
| english_word_short_threshold | 44 |
| english_word_long_threshold | 327 |
| english_to_chinese_ratio_low_threshold | 1.600 |
| english_to_chinese_ratio_high_threshold | 8.000 |

## Non-exportable repair queue

| Section | Title | Verification status | Decision | Notes |
| --- | --- | --- | --- | --- |
| guofeng-zhaonan-006 | 行露 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.229-230. Only the closing stanza survives legibly; the opening stanzas dissolve into mixed Chinese/OCR noise, so this witness cannot yet support a clean export. |
| guofeng-beifeng-001 | 柏舟 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.240-242. Stanzas 1, 2, 4, and 5 are partly recoverable, but stanza 3 breaks into gibberish and the paired Chinese page also contains the separate 鄘·柏舟 entry, so the source pairing is not yet safe. |
| guofeng-beifeng-010 | 谷風 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.257-260. The first six stanzas are partly recoverable, but the remaining stanzas are not cleanly separable from commentary and page-break noise, so export would still be incomplete. |
| guofeng-beifeng-019 | 二子乘舟 | extraction_failed_non_exportable | do_not_export_until_repaired | Checked part-1 hOCR pp.273-274. The poem body is almost entirely unrecoverable in the current hOCR witness, so no verified English text can be exported yet. |
| guofeng-yongfeng-008 | 相鼠 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.286-287. Only stanza 1 is legible in the current witness; stanzas 2 and 3 drop out before the next book heading, so the poem remains incomplete and non-exportable. |
| guofeng-weifeng-006 | 芄蘭 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.305-306. The surviving lines on p.305 are mostly gibberish, and the recovered verse on p.306 resolves into the following 河廣 witness, so the poem boundary is not yet safe. |
| guofeng-wangfeng-005 | 中谷有蓷 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.318-319. One stanza falls back across the preceding 揚之水 range and the remaining lines do not yield a complete clean witness, so this poem stays non-exportable. |
| guofeng-wangfeng-010 | 丘中有麻 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.324-325. The final stanza ends in OCR/Chinese contamination ("They will give me 是細 -stones for my girdie"), so the witness is not yet clean enough for export. |
| guofeng-zhengfeng-001 | 緇衣 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.326-327. Only two partial stanzas survive before the witness breaks off, so the poem remains incomplete in the current source. |
| guofeng-zhengfeng-008 | 女曰鷄鳴 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.336-338. The opening stanza survives only as two dialogue lines before the rest of the poem continues, so the current witness does not preserve a clean full-poem boundary. |
| guofeng-zhengfeng-009 | 有女同車 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.338-339. Only the opening stanza survives before the ODES OF CH'ING running heading, so the poem is incomplete in the current witness. |
| guofeng-zhengfeng-010 | 山有扶蘇 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.339-340. The middle of the witness collapses into unreadable OCR gibberish between the opening and closing lines, so the poem cannot yet be verified cleanly. |
| guofeng-zhengfeng-021 | 溱洧 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.345-347. The dialogue stanzas are misordered and partially repeated across the page break, so the full poem sequence is not yet recoverable from this witness. |
| guofeng-qifeng-003 | 著 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.354-355. The key gem-name lines are OCR-corrupt in every stanza, so the translation cannot be normalized confidently from this witness alone. |
| guofeng-weifeng-state-002 | 汾沮洳 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.366-367. The first stanza runs straight into the following 園有桃 witness and the poem boundary is not recoverable cleanly. |
| guofeng-weifeng-state-003 | 園有桃 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.367-369. The stanza order is mixed and the opening lines are partly lost to OCR debris, so the poem cannot yet be verified cleanly. |
| guofeng-weifeng-state-006 | 伐檀 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.371-373. The second stanza breaks off at the page edge and the remaining witness does not preserve a clean continuation, so the poem stays non-exportable. |
| guofeng-tangfeng-006 | 杕杜 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.383-384. The verse is interrupted by Mencius commentary fragments and a repeated closing block, so the poem boundary is not yet safe. |
| guofeng-chenfeng-009 | 株林 | extraction_failed_non_exportable | do_not_export_until_repaired | Checked part-1 hOCR page 415. The translation column collapses into glyph debris immediately after the title, so no recoverable verse lines survive in the current witness. |
| guofeng-binfeng-003 | 東山 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pages 437-440. The witness merges stanza 1 with commentary debris, drops the return line in stanza 3, and truncates stanza 4 after its opening couplet, so the full poem is not recoverable cleanly. |

## Most flagged sections

| Section | Title | Witness | Words | Ratio | Flags |
| --- | --- | --- | ---: | ---: | --- |
| xiaoya-jienanshan-003 | 十月之交 | SBE transcluded page | 327 | 4.336 | suspiciously long English text, poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-gufeng-003 | 大東 | SBE transcluded page | 367 | 5.502 | suspiciously long English text, poem-level alignment may hide recoverable stanza segmentation |
| daya-dang-002 | 抑 | SBE transcluded page | 471 | 3.688 | suspiciously long English text, poem-level alignment may hide recoverable stanza segmentation |
| song-lusong-004 | 閟宮 | SBE transcluded page | 863 | 6.466 | suspiciously long English text, poem-level alignment may hide recoverable stanza segmentation |
| guofeng-zhengfeng-018 | 揚之水 | OCR-derived witness | 92 | 1.513 | poem-level alignment may hide recoverable stanza segmentation |
| guofeng-qifeng-007 | 甫田 | OCR-derived witness | 84 | 1.375 | poem-level alignment may hide recoverable stanza segmentation |
| guofeng-tangfeng-009 | 無衣 | OCR-derived witness | 78 | 3.099 | poem-level alignment may hide recoverable stanza segmentation |
| guofeng-qinfeng-008 | 無衣 | OCR-derived witness | 112 | 4.063 | poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-nanyoujiayu-011 | 采芑 | OCR-derived witness | 331 | 6.571 | suspiciously long English text |
| xiaoya-hongyan-009 | 斯干 | SBE transcluded page | 219 | 3.652 | poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-jienanshan-001 | 節南山 | SBE transcluded page | 452 | 6.378 | suspiciously long English text |
| xiaoya-jienanshan-006 | 小宛 | SBE transcluded page | 130 | 9.600 | poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-jienanshan-009 | 何人斯 | OCR-derived witness | 330 | 5.432 | suspiciously long English text |
| xiaoya-gufeng-002 | 蓼莪 | OCR-derived witness | 214 | 5.091 | poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-futian-002 | 大田 | SBE transcluded page | 140 | 3.477 | poem-level alignment may hide recoverable stanza segmentation |

## Extreme English/Chinese ratios

| Section | Title | Ratio | Witness | Notes |
| --- | --- | ---: | --- | --- |
| guofeng-zhaonan-014 | 騶虞 | 11.062 | OCR-derived witness | — |
| xiaoya-jienanshan-006 | 小宛 | 9.600 | SBE transcluded page | poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-luming-010 | 魚麗 | 8.580 | OCR-derived witness | — |
| daya-dang-007 | 韓奕 | 8.317 | SBE transcluded page | — |
| song-chengong-008 | 載見 | 8.208 | SBE transcluded page | — |
| song-minyuxiaozi-010 | 賚 | 8.161 | SBE transcluded page | — |
| song-shangsong-002 | 烈祖 | 8.089 | SBE transcluded page | — |
| daya-shengmin-009 | 民勞 | 8.080 | SBE transcluded page | — |
| guofeng-binfeng-004 | 破斧 | 8.078 | OCR-derived witness | — |
| guofeng-binfeng-001 | 七月 | 7.710 | SBE transcluded page | — |

## Hard failures

- None.
