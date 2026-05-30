# Shijing completion quality audit

This report complements the structural preflight checks with plausibility and review signals for the 305 complete extant *Shijing* poems.

## Summary

| Metric | Count |
| --- | ---: |
| complete_sections | 305 |
| metadata_only_sections | 6 |
| exact_alignment_count | 452 |
| ocr_or_fulltext_derived_sections | 202 |
| sections_needing_human_text_review | 202 |
| sections_with_coarse_alignment | 205 |
| sections_with_single_poem_alignment | 230 |
| sections_with_extreme_length_ratio | 30 |
| sections_with_possible_commentary_leakage | 146 |
| hard_failure_count | 0 |
| warning_count | 460 |

## Witness mix

| Witness type | Complete sections |
| --- | ---: |
| SBE transcluded page | 102 |
| full-text/OCR-derived witness | 202 |
| standalone Wikisource | 1 |

## Text-review status mix

| Status | Complete sections |
| --- | ---: |
| ocr_extracted_needs_review | 202 |
| verified_transcribed_text | 103 |

## Thresholds

| Heuristic | Value |
| --- | ---: |
| english_word_short_threshold | 34 |
| english_word_long_threshold | 336 |
| english_to_chinese_ratio_low_threshold | 1.300 |
| english_to_chinese_ratio_high_threshold | 8.844 |

## Most flagged sections

| Section | Title | Witness | Words | Ratio | Flags |
| --- | --- | --- | ---: | ---: | --- |
| guofeng-zhounan-004 | 樛木 | full-text/OCR-derived witness | 0 | 0.033 | suspiciously short English text, suspiciously low English/Chinese length ratio, possible commentary, page furniture, or OCR junk, Chinese text appears inside the English segment, complete section still needs human text review |
| guofeng-zhaonan-001 | 鵲巢 | full-text/OCR-derived witness | 778 | 57.733 | suspiciously long English text, suspiciously high English/Chinese length ratio, possible commentary, page furniture, or OCR junk, Chinese text appears inside the English segment, complete section still needs human text review |
| guofeng-zhaonan-014 | 騶虞 | full-text/OCR-derived witness | 969 | 135.281 | suspiciously long English text, suspiciously high English/Chinese length ratio, possible commentary, page furniture, or OCR junk, Chinese text appears inside the English segment, complete section still needs human text review |
| guofeng-zhengfeng-016 | 風雨 | full-text/OCR-derived witness | 7 | 0.417 | suspiciously short English text, suspiciously low English/Chinese length ratio, possible commentary, page furniture, or OCR junk, Chinese text appears inside the English segment, complete section still needs human text review |
| guofeng-zhengfeng-018 | 揚之水 | full-text/OCR-derived witness | 4 | 0.060 | suspiciously short English text, suspiciously low English/Chinese length ratio, possible commentary, page furniture, or OCR junk, Chinese text appears inside the English segment, complete section still needs human text review |
| guofeng-tangfeng-009 | 無衣 | full-text/OCR-derived witness | 6 | 0.162 | suspiciously short English text, suspiciously low English/Chinese length ratio, possible commentary, page furniture, or OCR junk, Chinese text appears inside the English segment, complete section still needs human text review |
| guofeng-chenfeng-009 | 株林 | full-text/OCR-derived witness | 0 | 0.051 | suspiciously short English text, suspiciously low English/Chinese length ratio, possible commentary, page furniture, or OCR junk, Chinese text appears inside the English segment, complete section still needs human text review |
| xiaoya-nanyoujiayu-001 | 南有嘉魚 | full-text/OCR-derived witness | 0 | 0.045 | suspiciously short English text, suspiciously low English/Chinese length ratio, possible commentary, page furniture, or OCR junk, Chinese text appears inside the English segment, complete section still needs human text review |
| guofeng-zhaonan-013 | 何彼穠矣 | full-text/OCR-derived witness | 65 | 0.914 | suspiciously low English/Chinese length ratio, possible commentary, page furniture, or OCR junk, complete section still needs human text review, poem-level alignment may hide recoverable stanza segmentation |
| guofeng-weifeng-007 | 河廣 | full-text/OCR-derived witness | 4 | 0.300 | suspiciously short English text, suspiciously low English/Chinese length ratio, possible commentary, page furniture, or OCR junk, complete section still needs human text review |
| guofeng-kuaifeng-004 | 匪風 | full-text/OCR-derived witness | 7 | 0.567 | suspiciously short English text, suspiciously low English/Chinese length ratio, possible commentary, page furniture, or OCR junk, complete section still needs human text review |
| guofeng-binfeng-005 | 伐柯 | full-text/OCR-derived witness | 3 | 0.250 | suspiciously short English text, suspiciously low English/Chinese length ratio, possible commentary, page furniture, or OCR junk, complete section still needs human text review |
| xiaoya-luming-010 | 魚麗 | full-text/OCR-derived witness | 214 | 12.630 | suspiciously high English/Chinese length ratio, possible commentary, page furniture, or OCR junk, Chinese text appears inside the English segment, complete section still needs human text review |
| xiaoya-nanyoujiayu-011 | 采芑 | full-text/OCR-derived witness | 336 | 6.679 | suspiciously long English text, possible commentary, page furniture, or OCR junk, complete section still needs human text review, poem-level alignment may hide recoverable stanza segmentation |
| daya-shengmin-007 | 泂酌 | full-text/OCR-derived witness | 345 | 19.500 | suspiciously long English text, suspiciously high English/Chinese length ratio, possible commentary, page furniture, or OCR junk, complete section still needs human text review |

## Extreme English/Chinese ratios

| Section | Title | Ratio | Witness | Notes |
| --- | --- | ---: | --- | --- |
| guofeng-zhaonan-014 | 騶虞 | 135.281 | full-text/OCR-derived witness | suspiciously long English text; suspiciously high English/Chinese length ratio; possible commentary, page furniture, or OCR junk; Chinese text appears inside the English segment; complete section still needs human text review |
| guofeng-zhaonan-001 | 鵲巢 | 57.733 | full-text/OCR-derived witness | suspiciously long English text; suspiciously high English/Chinese length ratio; possible commentary, page furniture, or OCR junk; Chinese text appears inside the English segment; complete section still needs human text review |
| guofeng-zhounan-004 | 樛木 | 0.033 | full-text/OCR-derived witness | suspiciously short English text; suspiciously low English/Chinese length ratio; possible commentary, page furniture, or OCR junk; Chinese text appears inside the English segment; complete section still needs human text review |
| guofeng-zhounan-005 | 螽斯 | 25.961 | full-text/OCR-derived witness | suspiciously high English/Chinese length ratio; possible commentary, page furniture, or OCR junk; complete section still needs human text review |
| xiaoya-nanyoujiayu-001 | 南有嘉魚 | 0.045 | full-text/OCR-derived witness | suspiciously short English text; suspiciously low English/Chinese length ratio; possible commentary, page furniture, or OCR junk; Chinese text appears inside the English segment; complete section still needs human text review |
| guofeng-chenfeng-009 | 株林 | 0.051 | full-text/OCR-derived witness | suspiciously short English text; suspiciously low English/Chinese length ratio; possible commentary, page furniture, or OCR junk; Chinese text appears inside the English segment; complete section still needs human text review |
| daya-shengmin-007 | 泂酌 | 19.500 | full-text/OCR-derived witness | suspiciously long English text; suspiciously high English/Chinese length ratio; possible commentary, page furniture, or OCR junk; complete section still needs human text review |
| guofeng-zhengfeng-018 | 揚之水 | 0.060 | full-text/OCR-derived witness | suspiciously short English text; suspiciously low English/Chinese length ratio; possible commentary, page furniture, or OCR junk; Chinese text appears inside the English segment; complete section still needs human text review |
| xiaoya-luming-010 | 魚麗 | 12.630 | full-text/OCR-derived witness | suspiciously high English/Chinese length ratio; possible commentary, page furniture, or OCR junk; Chinese text appears inside the English segment; complete section still needs human text review |
| guofeng-zhengfeng-015 | 東門之墠 | 12.550 | full-text/OCR-derived witness | suspiciously high English/Chinese length ratio; complete section still needs human text review |

## Hard failures

- None.
