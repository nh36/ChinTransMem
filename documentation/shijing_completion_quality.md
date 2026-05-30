# Shijing completion quality audit

This report complements the structural preflight checks with verification-ledger enforcement for exportable *Shijing* poems.

## Summary

| Metric | Count |
| --- | ---: |
| complete_sections | 163 |
| metadata_only_sections | 148 |
| non_exportable_extant_sections | 142 |
| exact_alignment_count | 392 |
| ocr_or_fulltext_derived_sections | 60 |
| sections_needing_human_text_review | 0 |
| sections_with_coarse_alignment | 50 |
| sections_with_single_poem_alignment | 50 |
| sections_with_extreme_length_ratio | 0 |
| sections_with_possible_commentary_leakage | 0 |
| sections_with_hard_failures | 0 |
| hard_failure_count | 0 |
| warning_count | 23 |

## Progress

| Metric | Count |
| --- | ---: |
| total_extant_poems | 305 |
| verified_exportable_poems | 163 |
| all_human_verified_ocr_sections | 60 |
| non_exportable_repair_queue_remaining | 142 |
| current_repair_batch | 2026-05-30-04-weifeng-wangfeng |
| newly_repaired_in_current_batch | 12 |

## Latest repaired tranche

Latest repair batch: 2026-05-30-04-weifeng-wangfeng

Latest review date: 2026-05-30

| Section | Title | Canonical ref | Verification status |
| --- | --- | --- | --- |
| guofeng-wangfeng-002 | 君子于役 | 詩經·國風·王風·002 | human_verified_ocr |
| guofeng-wangfeng-003 | 君子陽陽 | 詩經·國風·王風·003 | human_verified_ocr |
| guofeng-wangfeng-004 | 揚之水 | 詩經·國風·王風·004 | human_verified_ocr |
| guofeng-wangfeng-006 | 兔爰 | 詩經·國風·王風·006 | human_verified_ocr |
| guofeng-wangfeng-007 | 葛藟 | 詩經·國風·王風·007 | human_verified_ocr |
| guofeng-wangfeng-008 | 采葛 | 詩經·國風·王風·008 | human_verified_ocr |
| guofeng-weifeng-001 | 淇奧 | 詩經·國風·衛風·001 | human_verified_ocr |
| guofeng-weifeng-002 | 考槃 | 詩經·國風·衛風·002 | human_verified_ocr |
| guofeng-weifeng-003 | 碩人 | 詩經·國風·衛風·003 | human_verified_ocr |
| guofeng-weifeng-005 | 竹竿 | 詩經·國風·衛風·005 | human_verified_ocr |
| guofeng-weifeng-008 | 伯兮 | 詩經·國風·衛風·008 | human_verified_ocr |
| guofeng-weifeng-009 | 有狐 | 詩經·國風·衛風·009 | human_verified_ocr |

## Human-verified OCR by batch

| Repair batch | Section count | human_verified_ocr | human_verified_fulltext |
| --- | ---: | ---: | ---: |
| 2026-05-30-01-zhaonan | 9 | 9 | 0 |
| 2026-05-30-02-beifeng | 13 | 13 | 0 |
| 2026-05-30-03-yongfeng | 6 | 6 | 0 |
| 2026-05-30-04-weifeng-wangfeng | 12 | 12 | 0 |
| pre-batch verified | 20 | 20 | 0 |

## Remaining repair queue by subdivision

| Subdivision | Remaining poems |
| --- | ---: |
| 國風 / 鄭風 | 19 |
| 小雅 / 魚藻之什 | 13 |
| 國風 / 齊風 | 11 |
| 國風 / 陳風 | 10 |
| 國風 / 唐風 | 9 |
| 國風 / 秦風 | 9 |
| 小雅 / 南有嘉魚之什 | 9 |
| 小雅 / 鴻鴈之什 | 8 |
| 國風 / 魏風 | 7 |
| 小雅 / 甫田之什 | 6 |
| 小雅 / 谷風之什 | 6 |
| 小雅 / 鹿鳴之什 | 6 |
| 國風 / 豳風 | 5 |
| 國風 / 曹風 | 4 |
| 國風 / 邶風 | 4 |
| 國風 / 檜風 | 3 |
| 國風 / 王風 | 2 |
| 國風 / 衛風 | 2 |
| 大雅 / 生民之什 | 2 |
| 頌 / 魯頌 | 2 |
| 國風 / 召南 | 1 |
| 國風 / 鄘風 | 1 |
| 大雅 / 文王之什 | 1 |
| 大雅 / 蕩之什 | 1 |
| 小雅 / 節南山之什 | 1 |

## Detailed remaining queue in current subdivisions

### 國風 / 召南

| Section | Title | Canonical ref | Reason |
| --- | --- | --- | --- |
| guofeng-zhaonan-006 | 行露 | 詩經·國風·召南·006 | Checked part-1 hOCR pp.229-230. Only the closing stanza survives legibly; the opening stanzas dissolve into mixed Chinese/OCR noise, so this witness cannot yet support a clean export. |

### 國風 / 邶風

| Section | Title | Canonical ref | Reason |
| --- | --- | --- | --- |
| guofeng-beifeng-001 | 柏舟 | 詩經·國風·邶風·001 | Checked part-1 hOCR pp.240-242. Stanzas 1, 2, 4, and 5 are partly recoverable, but stanza 3 breaks into gibberish and the paired Chinese page also contains the separate 鄘·柏舟 entry, so the source pairing is not yet safe. |
| guofeng-beifeng-010 | 谷風 | 詩經·國風·邶風·010 | Checked part-1 hOCR pp.257-260. The first six stanzas are partly recoverable, but the remaining stanzas are not cleanly separable from commentary and page-break noise, so export would still be incomplete. |
| guofeng-beifeng-017 | 靜女 | 詩經·國風·邶風·017 | Checked part-1 hOCR pp.270-271. Only the opening stanza is legible; the rest of the poem collapses into low-font OCR debris and cannot yet be verified. |
| guofeng-beifeng-019 | 二子乘舟 | 詩經·國風·邶風·019 | Checked part-1 hOCR pp.273-274. The poem body is almost entirely unrecoverable in the current hOCR witness, so no verified English text can be exported yet. |

### 國風 / 鄘風

| Section | Title | Canonical ref | Reason |
| --- | --- | --- | --- |
| guofeng-yongfeng-008 | 相鼠 | 詩經·國風·鄘風·008 | Checked part-1 hOCR pp.286-287. Only stanza 1 is legible in the current witness; stanzas 2 and 3 drop out before the next book heading, so the poem remains incomplete and non-exportable. |

### 國風 / 衛風

| Section | Title | Canonical ref | Reason |
| --- | --- | --- | --- |
| guofeng-weifeng-006 | 芄蘭 | 詩經·國風·衛風·006 | Checked part-1 hOCR pp.305-306. The surviving lines on p.305 are mostly gibberish, and the recovered verse on p.306 resolves into the following 河廣 witness, so the poem boundary is not yet safe. |
| guofeng-weifeng-010 | 木瓜 | 詩經·國風·衛風·010 | Checked part-1 hOCR pp.309-310. The poem is mostly legible, but stanza 3's gift-word line survives as zero-confidence OCR mixed with stray characters ("beautiful Ae^-stone"), so the witness cannot yet be verified cleanly. |

### 國風 / 王風

| Section | Title | Canonical ref | Reason |
| --- | --- | --- | --- |
| guofeng-wangfeng-005 | 中谷有蓷 | 詩經·國風·王風·005 | Checked part-1 hOCR pp.318-319. One stanza falls back across the preceding 揚之水 range and the remaining lines do not yield a complete clean witness, so this poem stays non-exportable. |
| guofeng-wangfeng-010 | 丘中有麻 | 詩經·國風·王風·010 | Checked part-1 hOCR pp.324-325. The final stanza ends in OCR/Chinese contamination ("They will give me 是細 -stones for my girdie"), so the witness is not yet clean enough for export. |

## Skipped or unrecoverable in current witness

| Section | Title | Subdivision | Canonical ref | Reason |
| --- | --- | --- | --- | --- |
| guofeng-zhaonan-006 | 行露 | 國風 / 召南 | 詩經·國風·召南·006 | Checked part-1 hOCR pp.229-230. Only the closing stanza survives legibly; the opening stanzas dissolve into mixed Chinese/OCR noise, so this witness cannot yet support a clean export. |
| guofeng-wangfeng-005 | 中谷有蓷 | 國風 / 王風 | 詩經·國風·王風·005 | Checked part-1 hOCR pp.318-319. One stanza falls back across the preceding 揚之水 range and the remaining lines do not yield a complete clean witness, so this poem stays non-exportable. |
| guofeng-wangfeng-010 | 丘中有麻 | 國風 / 王風 | 詩經·國風·王風·010 | Checked part-1 hOCR pp.324-325. The final stanza ends in OCR/Chinese contamination ("They will give me 是細 -stones for my girdie"), so the witness is not yet clean enough for export. |
| guofeng-weifeng-006 | 芄蘭 | 國風 / 衛風 | 詩經·國風·衛風·006 | Checked part-1 hOCR pp.305-306. The surviving lines on p.305 are mostly gibberish, and the recovered verse on p.306 resolves into the following 河廣 witness, so the poem boundary is not yet safe. |
| guofeng-weifeng-010 | 木瓜 | 國風 / 衛風 | 詩經·國風·衛風·010 | Checked part-1 hOCR pp.309-310. The poem is mostly legible, but stanza 3's gift-word line survives as zero-confidence OCR mixed with stray characters ("beautiful Ae^-stone"), so the witness cannot yet be verified cleanly. |
| guofeng-beifeng-001 | 柏舟 | 國風 / 邶風 | 詩經·國風·邶風·001 | Checked part-1 hOCR pp.240-242. Stanzas 1, 2, 4, and 5 are partly recoverable, but stanza 3 breaks into gibberish and the paired Chinese page also contains the separate 鄘·柏舟 entry, so the source pairing is not yet safe. |
| guofeng-beifeng-010 | 谷風 | 國風 / 邶風 | 詩經·國風·邶風·010 | Checked part-1 hOCR pp.257-260. The first six stanzas are partly recoverable, but the remaining stanzas are not cleanly separable from commentary and page-break noise, so export would still be incomplete. |
| guofeng-beifeng-017 | 靜女 | 國風 / 邶風 | 詩經·國風·邶風·017 | Checked part-1 hOCR pp.270-271. Only the opening stanza is legible; the rest of the poem collapses into low-font OCR debris and cannot yet be verified. |
| guofeng-beifeng-019 | 二子乘舟 | 國風 / 邶風 | 詩經·國風·邶風·019 | Checked part-1 hOCR pp.273-274. The poem body is almost entirely unrecoverable in the current hOCR witness, so no verified English text can be exported yet. |
| guofeng-yongfeng-008 | 相鼠 | 國風 / 鄘風 | 詩經·國風·鄘風·008 | Checked part-1 hOCR pp.286-287. Only stanza 1 is legible in the current witness; stanzas 2 and 3 drop out before the next book heading, so the poem remains incomplete and non-exportable. |


## Witness mix

| Witness type | Complete sections |
| --- | ---: |
| OCR-derived witness | 60 |
| SBE transcluded page | 102 |
| standalone Wikisource | 1 |

## Verification status mix

| Status | Complete sections |
| --- | ---: |
| human_verified_ocr | 60 |
| verified_transcribed_text | 103 |

## Thresholds

| Heuristic | Value |
| --- | ---: |
| english_word_short_threshold | 42 |
| english_word_long_threshold | 378 |
| english_to_chinese_ratio_low_threshold | 1.413 |
| english_to_chinese_ratio_high_threshold | 8.000 |

## Non-exportable repair queue

| Section | Title | Verification status | Decision | Notes |
| --- | --- | --- | --- | --- |
| guofeng-zhaonan-006 | 行露 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.229-230. Only the closing stanza survives legibly; the opening stanzas dissolve into mixed Chinese/OCR noise, so this witness cannot yet support a clean export. |
| guofeng-beifeng-001 | 柏舟 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.240-242. Stanzas 1, 2, 4, and 5 are partly recoverable, but stanza 3 breaks into gibberish and the paired Chinese page also contains the separate 鄘·柏舟 entry, so the source pairing is not yet safe. |
| guofeng-beifeng-010 | 谷風 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.257-260. The first six stanzas are partly recoverable, but the remaining stanzas are not cleanly separable from commentary and page-break noise, so export would still be incomplete. |
| guofeng-beifeng-017 | 靜女 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.270-271. Only the opening stanza is legible; the rest of the poem collapses into low-font OCR debris and cannot yet be verified. |
| guofeng-beifeng-019 | 二子乘舟 | extraction_failed_non_exportable | do_not_export_until_repaired | Checked part-1 hOCR pp.273-274. The poem body is almost entirely unrecoverable in the current hOCR witness, so no verified English text can be exported yet. |
| guofeng-yongfeng-008 | 相鼠 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.286-287. Only stanza 1 is legible in the current witness; stanzas 2 and 3 drop out before the next book heading, so the poem remains incomplete and non-exportable. |
| guofeng-weifeng-006 | 芄蘭 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.305-306. The surviving lines on p.305 are mostly gibberish, and the recovered verse on p.306 resolves into the following 河廣 witness, so the poem boundary is not yet safe. |
| guofeng-weifeng-010 | 木瓜 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.309-310. The poem is mostly legible, but stanza 3's gift-word line survives as zero-confidence OCR mixed with stray characters ("beautiful Ae^-stone"), so the witness cannot yet be verified cleanly. |
| guofeng-wangfeng-005 | 中谷有蓷 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.318-319. One stanza falls back across the preceding 揚之水 range and the remaining lines do not yield a complete clean witness, so this poem stays non-exportable. |
| guofeng-wangfeng-010 | 丘中有麻 | needs_text_repair | do_not_export_until_repaired | Checked part-1 hOCR pp.324-325. The final stanza ends in OCR/Chinese contamination ("They will give me 是細 -stones for my girdie"), so the witness is not yet clean enough for export. |
| guofeng-zhengfeng-001 | 緇衣 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-002 | 將仲子 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-003 | 叔于田 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-004 | 大叔于田 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-005 | 清人 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-006 | 羔裘 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-007 | 遵大路 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-008 | 女曰鷄鳴 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-009 | 有女同車 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-010 | 山有扶蘇 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-011 | 蘀兮 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-012 | 狡童 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-013 | 褰裳 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-014 | 丰 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |
| guofeng-zhengfeng-015 | 東門之墠 | needs_text_repair | do_not_export_until_repaired | Public-domain witness located, but the English text is not yet verified clean enough for export. |

## Most flagged sections

| Section | Title | Witness | Words | Ratio | Flags |
| --- | --- | --- | ---: | ---: | --- |
| daya-dang-002 | 抑 | SBE transcluded page | 471 | 3.688 | suspiciously long English text, poem-level alignment may hide recoverable stanza segmentation |
| song-lusong-004 | 閟宮 | SBE transcluded page | 863 | 6.466 | suspiciously long English text, poem-level alignment may hide recoverable stanza segmentation |
| guofeng-zhengfeng-018 | 揚之水 | OCR-derived witness | 92 | 1.513 | poem-level alignment may hide recoverable stanza segmentation |
| guofeng-tangfeng-009 | 無衣 | OCR-derived witness | 78 | 3.099 | poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-hongyan-009 | 斯干 | SBE transcluded page | 219 | 3.652 | poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-jienanshan-001 | 節南山 | SBE transcluded page | 452 | 6.378 | suspiciously long English text |
| xiaoya-jienanshan-003 | 十月之交 | SBE transcluded page | 327 | 4.336 | poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-jienanshan-006 | 小宛 | SBE transcluded page | 130 | 9.600 | poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-gufeng-003 | 大東 | SBE transcluded page | 367 | 5.502 | poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-futian-002 | 大田 | SBE transcluded page | 140 | 3.477 | poem-level alignment may hide recoverable stanza segmentation |
| daya-wenwang-001 | 文王 | SBE transcluded page | 395 | 6.384 | suspiciously long English text |
| daya-wenwang-002 | 大明 | SBE transcluded page | 378 | 6.089 | suspiciously long English text |
| daya-wenwang-007 | 皇矣 | SBE transcluded page | 693 | 6.513 | suspiciously long English text |
| daya-shengmin-001 | 生民 | SBE transcluded page | 200 | 2.310 | poem-level alignment may hide recoverable stanza segmentation |
| daya-shengmin-010 | 板 | SBE transcluded page | 156 | 2.331 | poem-level alignment may hide recoverable stanza segmentation |

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
| guofeng-binfeng-001 | 七月 | 7.710 | SBE transcluded page | — |
| guofeng-zhounan-004 | 樛木 | 7.633 | OCR-derived witness | — |

## Hard failures

- None.
