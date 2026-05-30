# Shijing completion quality audit

This report complements the structural preflight checks with verification-ledger enforcement for exportable *Shijing* poems.

## Summary

| Metric | Count |
| --- | ---: |
| complete_sections | 132 |
| metadata_only_sections | 179 |
| non_exportable_extant_sections | 173 |
| exact_alignment_count | 296 |
| ocr_or_fulltext_derived_sections | 29 |
| sections_needing_human_text_review | 0 |
| sections_with_coarse_alignment | 48 |
| sections_with_single_poem_alignment | 48 |
| sections_with_extreme_length_ratio | 0 |
| sections_with_possible_commentary_leakage | 0 |
| sections_with_hard_failures | 0 |
| hard_failure_count | 0 |
| warning_count | 22 |

## Progress

| Metric | Count |
| --- | ---: |
| total_extant_poems | 305 |
| verified_exportable_poems | 132 |
| non_exportable_repair_queue_remaining | 173 |
| newly_repaired_in_this_tranche | 9 |

## Latest repaired tranche

Latest review date: 2026-05-30

| Section | Title | Canonical ref | Verification status |
| --- | --- | --- | --- |
| guofeng-zhaonan-003 | 草蟲 | 詩經·國風·召南·003 | human_verified_ocr |
| guofeng-zhaonan-005 | 甘棠 | 詩經·國風·召南·005 | human_verified_ocr |
| guofeng-zhaonan-007 | 羔羊 | 詩經·國風·召南·007 | human_verified_ocr |
| guofeng-zhaonan-008 | 殷其靁 | 詩經·國風·召南·008 | human_verified_ocr |
| guofeng-zhaonan-009 | 摽有梅 | 詩經·國風·召南·009 | human_verified_ocr |
| guofeng-zhaonan-010 | 小星 | 詩經·國風·召南·010 | human_verified_ocr |
| guofeng-zhaonan-011 | 江有汜 | 詩經·國風·召南·011 | human_verified_ocr |
| guofeng-zhaonan-012 | 野有死麕 | 詩經·國風·召南·012 | human_verified_ocr |
| guofeng-zhaonan-013 | 何彼穠矣 | 詩經·國風·召南·013 | human_verified_ocr |

## Remaining repair queue by subdivision

| Subdivision | Remaining poems |
| --- | ---: |
| 國風 / 鄭風 | 19 |
| 國風 / 邶風 | 17 |
| 小雅 / 魚藻之什 | 13 |
| 國風 / 齊風 | 11 |
| 國風 / 陳風 | 10 |
| 國風 / 唐風 | 9 |
| 國風 / 秦風 | 9 |
| 小雅 / 南有嘉魚之什 | 9 |
| 國風 / 王風 | 8 |
| 國風 / 衛風 | 8 |
| 小雅 / 鴻鴈之什 | 8 |
| 國風 / 鄘風 | 7 |
| 國風 / 魏風 | 7 |
| 小雅 / 甫田之什 | 6 |
| 小雅 / 谷風之什 | 6 |
| 小雅 / 鹿鳴之什 | 6 |
| 國風 / 豳風 | 5 |
| 國風 / 曹風 | 4 |
| 國風 / 檜風 | 3 |
| 大雅 / 生民之什 | 2 |
| 頌 / 魯頌 | 2 |
| 國風 / 召南 | 1 |
| 大雅 / 文王之什 | 1 |
| 大雅 / 蕩之什 | 1 |
| 小雅 / 節南山之什 | 1 |

## Witness mix

| Witness type | Complete sections |
| --- | ---: |
| OCR-derived witness | 29 |
| SBE transcluded page | 102 |
| standalone Wikisource | 1 |

## Verification status mix

| Status | Complete sections |
| --- | ---: |
| human_verified_ocr | 29 |
| verified_transcribed_text | 103 |

## Thresholds

| Heuristic | Value |
| --- | ---: |
| english_word_short_threshold | 41 |
| english_word_long_threshold | 395 |
| english_to_chinese_ratio_low_threshold | 1.413 |
| english_to_chinese_ratio_high_threshold | 8.080 |

## Non-exportable repair queue

| Section | Title | Verification status | Decision | Notes |
| --- | --- | --- | --- | --- |
| guofeng-zhaonan-006 | 行露 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-001 | 柏舟 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-002 | 綠衣 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-003 | 燕燕 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-005 | 終風 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-006 | 擊鼓 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-007 | 凱風 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-008 | 雄雉 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-009 | 匏有苦葉 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-010 | 谷風 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-011 | 式微 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-012 | 旄丘 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-013 | 簡兮 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-014 | 泉水 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-016 | 北風 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-017 | 靜女 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-018 | 新臺 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-beifeng-019 | 二子乘舟 | extraction_failed_non_exportable | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-yongfeng-002 | 牆有茨 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-yongfeng-004 | 桑中 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-yongfeng-005 | 鶉之奔奔 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-yongfeng-007 | 蝃蝀 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-yongfeng-008 | 相鼠 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-yongfeng-009 | 干旄 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |
| guofeng-yongfeng-010 | 載馳 | needs_text_repair | do_not_export_until_repaired | Legge witness located, but this poem is non-exportable until the English text is verified against source and cleaned of OCR/layout contamination. |

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
| daya-wenwang-007 | 皇矣 | SBE transcluded page | 693 | 6.513 | suspiciously long English text |
| daya-shengmin-001 | 生民 | SBE transcluded page | 200 | 2.310 | poem-level alignment may hide recoverable stanza segmentation |
| daya-shengmin-010 | 板 | SBE transcluded page | 156 | 2.331 | poem-level alignment may hide recoverable stanza segmentation |
| daya-dang-001 | 蕩 | SBE transcluded page | 468 | 6.538 | suspiciously long English text |

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
