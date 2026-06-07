# Unit failure inventory

Total tests run: 71
Failure count: 15

- Test: test_corpus_workflow.CorpusWorkflowTest.test_lunyu_workflow_counts_and_qc
  - work_id: lunyu
  - failure_type: segmentation_mismatch
  - expected: 20464, actual: 20324
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_corpus_workflow.py

- Test: test_corpus_workflow.CorpusWorkflowTest.test_manifest_policy_and_exports_are_consistent
  - work_id: None
  - failure_type: manifest_vs_export_count_mismatch
  - expected: 20, actual: 0
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_corpus_workflow.py

- Test: test_ingestion_gauntlet.IngestionGauntletTest.test_existing_work_guardrails_remain_stable
  - work_id: shangshu
  - failure_type: other
  - expected: 129, actual: 135
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_ingestion_gauntlet.py

- Test: test_ingestion_gauntlet.IngestionGauntletTest.test_shiji_batch_exports_are_clean_and_agree_with_active
  - work_id: shiji
  - failure_type: other
  - expected: None, actual: None
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_ingestion_gauntlet.py

- Test: test_mozi_staging.MoziPromotionTest.test_existing_work_guardrails_remain_stable
  - work_id: mozi
  - failure_type: other
  - expected: 129, actual: 135
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_mozi_staging.py

- Test: test_mozi_staging.MoziPromotionTest.test_mozi_alignment_qc_and_fallbacks_are_explicit
  - work_id: mozi
  - failure_type: other
  - expected: 654, actual: 663
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_mozi_staging.py

- Test: test_mozi_staging.MoziPromotionTest.test_mozi_chapter_three_alignment_and_leakage_regressions
  - work_id: mozi
  - failure_type: other
  - expected: 8, actual: 10
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_mozi_staging.py

- Test: test_mozi_staging.MoziPromotionTest.test_mozi_exports_have_clean_traceable_proof_of_concept_text
  - work_id: mozi
  - failure_type: other
  - expected: None, actual: None
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_mozi_staging.py

- Test: test_mozi_staging.MoziPromotionTest.test_mozi_manifest_inventory_ledger_and_exports_agree
  - work_id: mozi
  - failure_type: manifest_vs_export_count_mismatch
  - expected: 654, actual: 663
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_mozi_staging.py

- Test: test_shangshu_promotion.ShangshuPromotionTest.test_canon_of_yao_anchor_boundaries_remain_aligned
  - work_id: shangshu
  - failure_type: other
  - expected: None, actual: None
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_shangshu_promotion.py

- Test: test_shangshu_promotion.ShangshuPromotionTest.test_shangshu_exports_and_alignment_qc_are_clean
  - work_id: shangshu
  - failure_type: qc_vs_export_count_mismatch
  - expected: 129, actual: 135
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_shangshu_promotion.py

- Test: test_shangshu_promotion.ShangshuPromotionTest.test_shangshu_is_active_with_exportable_and_metadata_only_sections
  - work_id: shangshu
  - failure_type: manifest_vs_export_count_mismatch
  - expected: 129, actual: 135
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_shangshu_promotion.py

- Test: test_shangshu_promotion.ShangshuPromotionTest.test_shangshu_mapping_metadata_matches_generated_qc
  - work_id: shangshu
  - failure_type: other
  - expected: 135, actual: 129
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_shangshu_promotion.py

- Test: test_yijing_promotion.YijingPromotionTest.test_existing_work_guardrails_remain_stable
  - work_id: shangshu
  - failure_type: other
  - expected: 129, actual: 135
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_yijing_promotion.py

- Test: unittest.loader._FailedTest.test_placeholder_promotion
  - work_id: None
  - failure_type: placeholder_dependency
  - expected: None, actual: None
  - affected_files: Users/nathanhill/Code/ChinTransMem/tests/test_placeholder_promotion.py, opt/homebrew/Cellar/python@3.14/3.14.3_1/Frameworks/Python.framework/Versions/3.14/lib/python3.14/unittest/loader.py
