# BurmeseCorpus Translation-Source Discovery Handoff

This handoff is for restarting the ChatGPT chain for the `nh36/BurmeseCorpus` project.

Repository: <https://github.com/nh36/BurmeseCorpus>

Last observed commit in the previous chain:

- `8e2324796408e9417205e0259c644a5a0e765dac`
- Commit message: `Promote verified direct witnesses`

The next assistant should first inspect the current repository state, because there may be newer commits by the time this file is used.

---

## 1. High-level project state

The project has been moving through these phases:

1. Establish a stable release layer for the Burmese inscription corpus.
2. Build a bibliography/source authority layer.
3. Resolve corpus citation acronyms and source-family abbreviations.
4. Build source-work and locator-system authority tables.
5. Begin translation-source discovery by identifying which source works contain editions, translations, plates, catalogue metadata, or only secondary discussion.
6. Verify candidate witnesses against local files and OCR/title-page snippets.

The release layer should be treated as stable for now.

Do not modify:

```text
data/release/corpus_release_v0_3/
```

The current work is in the translation-source discovery phase, not corpus rewriting and not translation generation.

---

## 2. Completed authority-layer work

The bibliography/source authority phase is effectively closed for current purposes.

Important completed decisions:

- No unresolved priority acronyms remain.
- `IPPA` is treated as an alias/variant locator family into `PPA`, while raw `IPPA` strings are preserved.
- `Pl.` and `IOB` are locator systems into *Inscriptions of Burma*.
- `MP`, `OR`, `Luce D`, and `Luce J` are locator/private-collection systems, not ordinary BibTeX publications.
- Locator systems are kept separate from source works and from publication-style BibTeX records.
- Source-work authority is centralized in `data/working/bibliography/bibtex_authority/source_work_authority.tsv`.

Relevant stable authority files include:

```text
data/working/bibliography/bibtex_authority/acronym_resolution_status.tsv
data/working/bibliography/bibtex_authority/source_family_authority.tsv
data/working/bibliography/bibtex_authority/source_work_authority.tsv
data/working/bibliography/bibtex_authority/source_work_locator_systems.tsv
data/working/bibliography/bibtex_authority/raw_reference_to_bibtex.tsv
data/working/bibliography/bibtex_authority/bibliography_authority.bib
data/working/bibliography/bibtex_authority/bibliography_candidates.bib
```

Important source/acronym resolutions already made:

```text
ARASI = Annual Reports of the Archaeological Survey of India
BBHC = Bulletin of the Burma Historical Commission
EB = Epigraphia Birmanica
JBRS = Journal of the Burma Research Society
JRAS = Journal of the Royal Asiatic Society
List = A List of Inscriptions Found in Burma
MM = Middle Mon
OBI = Old Burmese Inscriptions
PPA = Inscriptions of Pagan, Pinya and Ava
SIP = Pe Maung Tin and G. H. Luce, Selections from the Inscriptions of Pagan
TN = U Tun Nyein, Inscriptions of Pagan, Pinya and Ava
UB = Inscriptions Collected in Upper Burma
UEM = U E Maung, Selections from the Inscriptions of Pagan
IPPA = alias/variant locator family into PPA
U Min Hswe = named person/source family, not an acronym
```

The source-authority QC pass was also closed:

- No open BibTeX field-quality issues.
- No OCR-like evidence in emitted BibTeX.
- No non-normalized script values.
- No locator-publication leak.
- No duplicate IPPA BibTeX entry.
- `TN, p.` is documented as a low-severity incomplete raw-reference residue.

---

## 3. Translation-source discovery phase

Current directory:

```text
data/working/bibliography/translation_source_discovery/
```

Key files:

```text
data/working/bibliography/translation_source_discovery_plan.tsv
data/working/bibliography/translation_source_discovery/witness_candidates.tsv
data/working/bibliography/translation_source_discovery/witness_classification.tsv
data/working/bibliography/translation_source_discovery/witness_verification.tsv
data/working/bibliography/translation_source_discovery/witness_titlepage_toc_snippets.tsv
data/working/bibliography/translation_source_discovery/witness_verification_report.json
data/working/bibliography/translation_source_discovery/translation_source_discovery_report.json
data/working/bibliography/translation_source_discovery/source_work_witness_gaps.tsv
```

Important scripts:

```text
scripts/discover_translation_sources.py
scripts/verify_translation_witnesses.py
scripts/validate_translation_source_discovery.py
```

Important tests:

```text
tests/test_translation_source_discovery.py
tests/test_translation_witness_verification.py
```

Current principle:

> This phase is about finding and classifying published/local witnesses, not generating translations.

Do not start AI translation generation.

Do not commit copyrighted PDFs, full OCR text, page images, or long extracted passages.

Short evidence snippets in TSVs are fine.

---

## 4. Current verified witness state at last observed commit

From the last inspected state, the translation-source discovery report said approximately:

```text
candidate_witness_count: 31
classified_witness_count: 31
verified_direct_witness_count: 4
verified_edition_witness_count: 4
verified_plate_witness_count: 2
verified_translation_witness_count: 0
verified_secondary_work_count: 9
weak_false_positive_count: 1
source_works_with_verified_direct_witness: 2
source_works_still_needing_direct_witness: 5
eb_verified_fascicle_count: 3
inscriptions_of_burma_text_witness_found: 0
```

The main verified source-work state:

### SIP / Selections from the Inscriptions of Pagan

Verified direct witness:

```text
Luce 1928 inscriptions of Pagan.pdf
```

This is a verified edition/transliteration witness for `sipSelectionsPagan`.

It is **not** a UEM witness.

Current status:

- Direct witness found.
- Edition status confirmed from title-page evidence.
- Translation status unconfirmed.
- No reliable sample-entry OCR was recovered.

### UEM / U E Maung, Selections from the Inscriptions of Pagan

Current status:

- Still needs direct witness.
- The SIP witness must not be inherited by UEM.
- The match to `Luce 1928 inscriptions of Pagan.pdf` was correctly marked as a false positive for UEM.

### TN / U Tun Nyein, Inscriptions of Pagan, Pinya and Ava

Current status:

- Still needs direct witness.

### PPA / Inscriptions of Pagan, Pinya and Ava

Current status:

- Still needs direct witness.
- IPPA is treated as an alias/variant into PPA, but that does not supply a direct witness.

### UB / Inscriptions Collected in Upper Burma

Current status:

- Still needs direct witness.
- Only bibliographic clues have been found, not a direct local witness.

### Epigraphia Birmanica

Promoted direct-looking EB fascicle witnesses:

```text
Duroiselle - Epigraphica Birmanica1.pdf
Duroiselle - Epigraphica Birmanica3.pdf
Duroiselle - Epigraphica Birmanica Talaing Plaques on Ananda Plates.pdf
```

Current status:

- These are verified/direct EB edition witnesses or very strong direct fascicle witnesses.
- Translation coverage remains unknown.
- The Talaing plaques file is also a plate/image witness.
- Need content-profile inspection before claiming translation coverage.

### Inscriptions of Burma

Current verified plate witnesses:

```text
Luce&PeMaungTin_InscriptionsOfBurma(Plates3,4,5)_1960.pdf
Luce&PeMaungTin_InscriptionsOfBurma(Plates6-20)_1963.pdf
```

Current status:

- Verified plate/facsimile witnesses.
- No text witness has been found yet.
- Plate volumes must not count as text witnesses.

---

## 5. Current semantic bug to fix

At the last observed commit, there were two important semantic issues:

### 5.1 SIP sample-entry inspection is overreported

The report says:

```text
sip_sample_entry_inspected: true
```

But the SIP inspection table says no recoverable sample-entry OCR was isolated.

This should **not** count as real sample-entry inspection.

Correct semantics should distinguish:

```text
sip_title_page_inspected = true
sip_sample_entry_ocr_attempted = true
sip_sample_entry_inspected = false
sip_translation_status = unconfirmed
sip_edition_status = confirmed
sip_needs_sample_entry_review = true
```

Failed OCR means unknown/unconfirmed, not false.

### 5.2 Inscriptions of Burma plate volumes are being caught as text-witness candidates

The text-witness search for *Inscriptions of Burma* still catches plate volumes. These are useful, but they do not satisfy the text-witness requirement.

For rows matching:

```text
Luce&PeMaungTin_InscriptionsOfBurma(Plates3,4,5)_1960.pdf
Luce&PeMaungTin_InscriptionsOfBurma(Plates6-20)_1963.pdf
```

the search table should say:

```text
is_plate_witness_candidate = true
is_text_witness_candidate = false
false_positive_for_text = true
reason_not_text_witness = plate/facsimile volume, not companion text volume
```

---

## 6. Recommended next agent task

Use this as the next instruction to the coding agent.

```text
Task: Correct witness-inspection semantics and begin content-profile inspection for SIP, EB, and Inscriptions of Burma.

Context

The latest commit promoted direct witnesses and added:

- epigraphia_birmanica_fascicle_coverage.tsv
- inscriptions_of_burma_text_witness_search.tsv
- expanded sip_witness_inspection.tsv
- updated witness verification/classification/report files

Current state:

- 31 classified witnesses
- 4 verified direct witnesses
- 4 verified edition witnesses
- 2 verified plate witnesses
- 0 verified translation witnesses
- 3 verified EB fascicle witnesses
- SIP has a verified direct witness and edition evidence
- SIP translation coverage remains unconfirmed
- Inscriptions of Burma has verified plate witnesses but no verified text witness
- UEM, TN, PPA, and UB still lack direct witnesses

Immediate semantic problems:

1. The report says `sip_sample_entry_inspected = true`, but the SIP inspection row says no recoverable sample-entry OCR was isolated. That should not count as real sample-entry inspection.
2. The Inscriptions of Burma text-witness search is still allowing plate volumes to appear as text-witness candidates. Plate volumes are useful, but they do not satisfy the text-witness requirement.

Do not modify corpus_release_v0_3.
Do not generate translations.
Do not commit PDFs, page images, full OCR text, or long extracted text.
Do not claim translation coverage without actual witness evidence.
Do not let plate/facsimile volumes count as text witnesses.
Do not let failed sample-entry OCR count as sample-entry inspection.

Main goal

Clean up the witness-inspection semantics, then inspect the content profiles of the verified SIP and EB witnesses enough to determine whether they contain editions, translations, notes/commentary, plates, or only source text.

1. Fix SIP inspection/report semantics

Update:

data/working/bibliography/translation_source_discovery/sip_witness_inspection.tsv
data/working/bibliography/translation_source_discovery/translation_source_discovery_report.json
data/working/bibliography/translation_source_discovery/witness_verification_report.json
data/working/bibliography/translation_source_discovery/source_work_witness_gaps.tsv

Use separate fields:

sip_title_page_inspected = true
sip_contents_inspected = false or uncertain
sip_sample_entry_inspected = false
sip_sample_entry_ocr_attempted = true
sip_translation_status = unconfirmed
sip_edition_status = confirmed
sip_needs_sample_entry_review = true

In sip_witness_inspection.tsv, add or update status fields so the sample-entry row says:

inspection_status = attempted_no_recoverable_text
contains_translation = unknown
contains_edition_or_transliteration = unknown

Do not set `contains_translation = false` from failed OCR. Failed OCR supports “unconfirmed”, not “false”.

2. Add content-profile tables for verified witnesses

Create:

data/working/bibliography/translation_source_discovery/source_witness_content_profile.tsv

Fields:

source_work_key
witness_id
file_label
verified_witness_type
content_profile_status
title_page_status
contents_status
sample_entry_status
translation_status
edition_status
notes_commentary_status
plate_image_status
catalogue_metadata_status
coverage_scope
confidence
next_action
notes

Suggested status values:

confirmed
possible
unknown
not_present
attempted_no_recoverable_text
needs_manual_review
not_applicable

Populate it for at least:

- SIP direct witness
- EB Vol. 1
- EB Vol. 3
- EB Talaing plaques file
- Inscriptions of Burma plates 3/4/5
- Inscriptions of Burma plates 6–20

The goal is to stop overloading witness_verification.tsv with content inspection semantics.

3. Inspect EB fascicle content profiles

Update:

data/working/bibliography/translation_source_discovery/epigraphia_birmanica_fascicle_coverage.tsv

For each promoted EB fascicle:

- Duroiselle - Epigraphica Birmanica1.pdf
- Duroiselle - Epigraphica Birmanica3.pdf
- Duroiselle - Epigraphica Birmanica Talaing Plaques on Ananda Plates.pdf

Try to inspect title page, contents, first page, and one sample entry via existing OCR/text snippets or targeted extraction.

Create:

data/working/bibliography/translation_source_discovery/eb_fascicle_content_inspection.tsv

Fields:

witness_id
file_label
inspection_area
short_snippet
contains_translation
contains_edition_or_transliteration
contains_notes_or_commentary
contains_plate_or_image
confidence
inspection_status
next_action
notes

Use short snippets only.

Do not mark translation confirmed unless there is explicit English translation or translation-heading evidence. If the EB fascicle contains editions/transliterations only, mark translation unknown or not_present, depending on evidence.

4. Correct Inscriptions of Burma text-witness search

Update:

data/working/bibliography/translation_source_discovery/inscriptions_of_burma_text_witness_search.tsv

Add fields:

is_text_witness_candidate
is_plate_witness_candidate
false_positive_for_text
reason_not_text_witness

For rows matching the known plate volumes, set:

is_plate_witness_candidate = true
is_text_witness_candidate = false
false_positive_for_text = true
reason_not_text_witness = plate/facsimile volume, not companion text volume

Keep the plate witnesses in the project, but do not let them satisfy the text-witness gap.

5. Search specifically for Inscriptions of Burma text volumes using volume/portfolio clues

Create:

data/working/bibliography/translation_source_discovery/inscriptions_of_burma_text_volume_hunt.tsv

Fields:

query
matched_file_label
matched_file_id
match_type
match_confidence
short_evidence
searched_sources
search_scope
search_result_status
recommended_action
notes

Search targeted terms:

Inscriptions of Burma text
Inscriptions of Burma portfolio text
Inscriptions of Burma Portfolio I text
Inscriptions of Burma Portfolio II text
Inscriptions of Burma text volume
Pe Maung Tin Luce Inscriptions of Burma text
Inscriptions of Burma transliteration
Inscriptions of Burma list text
Inscriptions of Burma readings
Inscriptions of Burma captions
Luce Pe Maung Tin Portfolio I
Luce Pe Maung Tin Portfolio II
Inscriptions of Burma 1933
Inscriptions of Burma 1956
Inscriptions of Burma 1960 text
Inscriptions of Burma 1963 text

Also search local paths for files near the existing plate volumes. If the plate files are in a folder with sibling files, search sibling directory names through the manifest if available.

6. Continue focused direct-witness search for UEM, TN, PPA, and UB

Create or update:

data/working/bibliography/translation_source_discovery/missing_core_witness_hunt.tsv

Fields:

source_work_key
query
variant_type
matched_file_label
matched_file_id
match_type
match_confidence
short_evidence
search_result_status
recommended_action
notes

For UEM, try:

U E Maung
U. E. Maung
E Maung
U E Maung Selections
U E Maung Pagan
U E Maung inscriptions
Selections from the Inscriptions of Pagan U E Maung
Rangoon 1958 inscriptions Pagan
UEM no.

For TN, try:

U Tun Nyein
Tun Nyein
Tun Nyein 1897
Tun Nyein Pagan
Tun Nyein Pinya
Tun Nyein Ava
Pagan Pinya Ava
Inscriptions Pagan Pinya Ava
Rangoon Gazette Press inscriptions
Government Printing Burma 1897 inscriptions

For PPA, try:

Pagan Pinya Ava
Pagan Pinya and Ava
Inscriptions Pagan Pinya Ava
Inscriptions of Pagan Pinya and Ava
PPA inscription
PPA catalogue
IPPA
Pinya Ava inscriptions

For UB, try:

Upper Burma inscriptions
Inscriptions Collected in Upper Burma
Collected in Upper Burma
Upper Burma Archaeological Survey
Upper Burma Stone Inscriptions
UB 1
UB 2
Archaeological Survey Burma Upper Burma
Report Superintendent Archaeological Survey Burma Upper Burma

Do not add only not_found rows. If no file is found, record whether the search actually covered local manifest, OCR index, author folders, source-library manifest, and raw-reference evidence.

7. Fix report counts and gap semantics

Update:

data/working/bibliography/translation_source_discovery/translation_source_discovery_report.json
data/working/bibliography/translation_source_discovery/witness_verification_report.json
data/working/bibliography/translation_source_discovery/source_work_witness_gaps.tsv

Add or correct:

sip_title_page_inspected
sip_sample_entry_ocr_attempted
sip_sample_entry_inspected
sip_translation_status
sip_edition_status
eb_content_profile_count
eb_translation_confirmed_count
eb_translation_unconfirmed_count
inscriptions_of_burma_text_witness_found
inscriptions_of_burma_plate_false_positive_count
missing_core_witness_hunt_count
source_works_still_needing_direct_witness

Make sure `source_works_still_needing_direct_witness` is not contradictory with the gap table.

8. Validation

Update:

scripts/validate_translation_source_discovery.py

Checks:

- source_witness_content_profile.tsv exists.
- eb_fascicle_content_inspection.tsv exists.
- inscriptions_of_burma_text_volume_hunt.tsv exists.
- missing_core_witness_hunt.tsv exists.
- SIP sample-entry inspection cannot be true if the row says no recoverable sample-entry OCR was isolated.
- Failed OCR must not imply `contains_translation = false`; it should be unknown/unconfirmed.
- Plate volumes cannot satisfy Inscriptions of Burma text-witness requirement.
- EB direct witnesses must have content-profile rows.
- Translation confirmed counts require explicit snippet evidence.
- UEM cannot inherit SIP witness.
- No source work is marked direct-witness complete unless it has verified direct witness rows.

9. Tests

Add or update tests for:

- failed sample-entry OCR producing unknown/unconfirmed, not false.
- report `sip_sample_entry_inspected` false when no sample-entry snippet exists.
- plate volumes marked false_positive_for_text for Inscriptions of Burma text searches.
- EB fascicles requiring content-profile rows.
- translation confirmed only with explicit evidence.
- missing_core_witness_hunt coverage fields.
- gap table/report consistency.

10. Documentation

Update:

docs/phase2_translation_source_discovery.md

Add a section:

Content profiles and failed OCR

Explain:

- title-page verification proves identity, not translation coverage;
- failed OCR should not be interpreted as absence of translation;
- edition status, translation status, and plate status are separate;
- plate witnesses do not replace text witnesses;
- direct-witness gaps remain open for UEM, TN, PPA, UB, and the Inscriptions of Burma text volume.

Acceptance criteria

The task is complete when:

- SIP sample-entry/report semantics are corrected;
- source_witness_content_profile.tsv exists;
- eb_fascicle_content_inspection.tsv exists;
- EB fascicles have content-profile rows;
- Inscriptions of Burma plate files are explicitly excluded as text witnesses;
- inscriptions_of_burma_text_volume_hunt.tsv exists;
- missing_core_witness_hunt.tsv exists;
- reports use `unknown/unconfirmed` rather than false where OCR failed;
- validation passes;
- tests pass;
- no translation generation has been attempted;
- corpus_release_v0_3 remains unchanged.
```

---

## 7. Important style and process constraints for the next assistant/agent

Use the following constraints in future instructions:

```text
Do not modify corpus_release_v0_3.
Do not generate translations yet.
Do not reopen acronym/source-family work unless a direct contradiction appears.
Do not run broad OCR unless a specific file requires it.
Do not commit copyrighted PDFs, Word files, page images, or full OCR text.
Do not infer translation coverage from titles alone.
Do not treat title-page identity evidence as content evidence.
Do not treat failed OCR as evidence that translation is absent.
Do not let plate/facsimile volumes satisfy text-witness requirements.
Keep raw strings and uncertainty visible.
Use short snippets only.
Validation and tests should pass after each commit.
```

---

## 8. Suggested first prompt for the next chain

You can start the next chain with:

```text
We are continuing the BurmeseCorpus project. Please read this handoff file, then inspect the latest GitHub commit in https://github.com/nh36/BurmeseCorpus. The latest state in the old chain was around commit 8e2324796408e9417205e0259c644a5a0e765dac, but there may now be newer commits. Focus on the translation-source discovery phase. The immediate next task is to correct witness-inspection semantics: failed OCR should mean unknown/unconfirmed, not false; SIP sample-entry inspection should not count as complete if no sample-entry snippet was recovered; and Inscriptions of Burma plate volumes must be excluded as text witnesses. After inspecting the repo, give the agent precise next instructions.
```
