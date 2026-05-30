# Shijing completion quality audit

This report complements the structural preflight checks with plausibility and review signals for the 305 complete extant *Shijing* poems.

## Summary

| Metric | Count |
| --- | ---: |
| complete_sections | 303 |
| metadata_only_sections | 8 |
| exact_alignment_count | 450 |
| ocr_or_fulltext_derived_sections | 200 |
| sections_needing_human_text_review | 180 |
| sections_with_coarse_alignment | 215 |
| sections_with_single_poem_alignment | 228 |
| sections_with_extreme_length_ratio | 30 |
| sections_with_possible_commentary_leakage | 130 |
| sections_with_hard_failures | 0 |
| hard_failure_count | 0 |
| warning_count | 414 |

## Witness mix

| Witness type | Complete sections |
| --- | ---: |
| OCR-derived witness | 200 |
| SBE transcluded page | 102 |
| standalone Wikisource | 1 |

## Text-review status mix

| Status | Complete sections |
| --- | ---: |
| human_reviewed_ocr | 20 |
| ocr_extracted_needs_review | 180 |
| sbe_transcluded_verified | 102 |
| verified_transcribed_text | 1 |

## Thresholds

| Heuristic | Value |
| --- | ---: |
| english_word_short_threshold | 41 |
| english_word_long_threshold | 312 |
| english_to_chinese_ratio_low_threshold | 1.678 |
| english_to_chinese_ratio_high_threshold | 8.317 |

## Most flagged sections

| Section | Title | Witness | Words | Ratio | Flags |
| --- | --- | --- | ---: | ---: | --- |
| guofeng-zhaonan-013 | 何彼穠矣 | OCR-derived witness | 65 | 0.914 | suspiciously low English/Chinese length ratio, possible commentary, page furniture, or OCR junk, complete section still needs human text review, poem-level alignment may hide recoverable stanza segmentation |
| guofeng-beifeng-010 | 谷風 | OCR-derived witness | 312 | 3.985 | suspiciously long English text, possible commentary, page furniture, or OCR junk, complete section still needs human text review, poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-luming-008 | 出車 | OCR-derived witness | 329 | 6.217 | suspiciously long English text, possible commentary, page furniture, or OCR junk, complete section still needs human text review, poem-level alignment may hide recoverable stanza segmentation |
| xiaoya-nanyoujiayu-011 | 采芑 | OCR-derived witness | 336 | 6.679 | suspiciously long English text, possible commentary, page furniture, or OCR junk, complete section still needs human text review, poem-level alignment may hide recoverable stanza segmentation |
| daya-shengmin-007 | 泂酌 | OCR-derived witness | 345 | 19.500 | suspiciously long English text, suspiciously high English/Chinese length ratio, possible commentary, page furniture, or OCR junk, complete section still needs human text review |
| daya-dang-009 | 常武 | OCR-derived witness | 341 | 6.440 | suspiciously long English text, possible commentary, page furniture, or OCR junk, complete section still needs human text review, poem-level alignment may hide recoverable stanza segmentation |
| guofeng-zhaonan-006 | 行露 | OCR-derived witness | 38 | 1.651 | suspiciously short English text, suspiciously low English/Chinese length ratio, complete section still needs human text review |
| guofeng-zhaonan-012 | 野有死麕 | OCR-derived witness | 130 | 10.086 | suspiciously high English/Chinese length ratio, possible commentary, page furniture, or OCR junk, complete section still needs human text review |
| guofeng-beifeng-001 | 柏舟 | OCR-derived witness | 158 | 9.097 | suspiciously high English/Chinese length ratio, possible commentary, page furniture, or OCR junk, complete section still needs human text review |
| guofeng-beifeng-007 | 凱風 | OCR-derived witness | 111 | 5.975 | possible commentary, page furniture, or OCR junk, complete section still needs human text review, poem-level alignment may hide recoverable stanza segmentation |
| guofeng-weifeng-003 | 碩人 | OCR-derived witness | 252 | 8.521 | suspiciously high English/Chinese length ratio, possible commentary, page furniture, or OCR junk, complete section still needs human text review |
| guofeng-weifeng-005 | 竹竿 | OCR-derived witness | 181 | 9.012 | suspiciously high English/Chinese length ratio, possible commentary, page furniture, or OCR junk, complete section still needs human text review |
| guofeng-weifeng-010 | 木瓜 | OCR-derived witness | 85 | 1.463 | suspiciously low English/Chinese length ratio, possible commentary, page furniture, or OCR junk, complete section still needs human text review |
| guofeng-zhengfeng-009 | 有女同車 | OCR-derived witness | 34 | 2.767 | suspiciously short English text, possible commentary, page furniture, or OCR junk, complete section still needs human text review |
| guofeng-zhengfeng-017 | 子衿 | OCR-derived witness | 147 | 10.082 | suspiciously high English/Chinese length ratio, possible commentary, page furniture, or OCR junk, complete section still needs human text review |

## Extreme English/Chinese ratios

| Section | Title | Ratio | Witness | Notes |
| --- | --- | ---: | --- | --- |
| daya-shengmin-007 | 泂酌 | 19.500 | OCR-derived witness | suspiciously long English text; suspiciously high English/Chinese length ratio; possible commentary, page furniture, or OCR junk; complete section still needs human text review |
| guofeng-zhengfeng-015 | 東門之墠 | 12.550 | OCR-derived witness | suspiciously high English/Chinese length ratio; complete section still needs human text review |
| guofeng-kuaifeng-003 | 隰有萇楚 | 12.413 | OCR-derived witness | suspiciously high English/Chinese length ratio; possible commentary, page furniture, or OCR junk; complete section still needs human text review |
| guofeng-zhaonan-014 | 騶虞 | 11.062 | OCR-derived witness | suspiciously high English/Chinese length ratio |
| guofeng-zhaonan-012 | 野有死麕 | 10.086 | OCR-derived witness | suspiciously high English/Chinese length ratio; possible commentary, page furniture, or OCR junk; complete section still needs human text review |
| guofeng-zhengfeng-017 | 子衿 | 10.082 | OCR-derived witness | suspiciously high English/Chinese length ratio; possible commentary, page furniture, or OCR junk; complete section still needs human text review |
| guofeng-yongfeng-006 | 定之方中 | 9.733 | SBE transcluded page | suspiciously high English/Chinese length ratio; possible commentary, page furniture, or OCR junk |
| xiaoya-jienanshan-006 | 小宛 | 9.600 | SBE transcluded page | suspiciously high English/Chinese length ratio; poem-level alignment may hide recoverable stanza segmentation |
| guofeng-chenfeng-008 | 月出 | 9.383 | OCR-derived witness | suspiciously high English/Chinese length ratio; possible commentary, page furniture, or OCR junk; complete section still needs human text review |
| guofeng-beifeng-001 | 柏舟 | 9.097 | OCR-derived witness | suspiciously high English/Chinese length ratio; possible commentary, page furniture, or OCR junk; complete section still needs human text review |

## Hard failures

- None.
