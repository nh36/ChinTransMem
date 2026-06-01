# Yijing ingestion plan

## Scope

- Work ID: `yijing`
- Source mapping: `data/corpus/yijing.csv`
- Source directory: `corpus/yijing/`
- Target corpus model: one section per hexagram

## Source assessment

- ChineseNotes supplies 64 bilingual hexagram files plus an introductory source note file.
- The bilingual section files carry Chinese base text together with James Legge's public-domain English translation.
- The active corpus uses the ChineseNotes bilingual files as both the Chinese base-text witness and the English translation witness, with explicit provenance to the upstream repository commit `1f6b1d3e7a40b6886a4b943c898125639e993544`.

## Section model

- One active section per hexagram.
- Exportable units inside each section:
  - the hexagram judgment;
  - the six line statements;
  - `用九` / `用六` where present.
- Non-exportable structural material:
  - trigram headings such as `乾下乾上`;
  - `彖曰`, `象曰`, and `文言曰` commentary;
  - rights notices and translator/source note lines.

## Alignment model

- Default alignment strategy: deterministic exact block alignment from structural parsing.
- Each exportable Chinese unit is paired with the immediately following English translation line.
- Repeated line-position markers are filtered so later commentary cannot be mistaken for base text.
- Drift guardrail: line-position QC verifies that `初` / `二` / `三` / `四` / `五` / `上` / `用` markers align with the corresponding English position cues.
- Section-level fallback is allowed only as a last resort and is not expected for the promoted corpus.

## Promotion criteria

Promote Yijing to the active corpus only if:

1. all 64 hexagrams can be modeled as sections;
2. every active section has clean Chinese and English witness coverage;
3. exportable rows exclude commentary, headings, and notices;
4. text-integrity QC reports zero hard failures;
5. line-position drift QC reports zero active failures;
6. every active section has provenance, an export decision, and processed segment/alignment files.

## Provenance and rights

- Upstream repository: `https://github.com/alexamies/chinesenotes.com`
- Upstream commit: `1f6b1d3e7a40b6886a4b943c898125639e993544`
- English translator attribution: James Legge, 1882
- Rights basis: public-domain text mirrored in ChineseNotes and re-exported with explicit provenance metadata
