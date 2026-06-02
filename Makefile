PYTHON ?= python3
TEST ?= tests.test_corpus_workflow.CorpusWorkflowTest.test_lunyu_workflow_counts_and_qc
WORK ?= lunyu

.PHONY: bootstrap-corpus bootstrap-work bootstrap-lunyu bootstrap-mengzi bootstrap-shijing bootstrap-laozi bootstrap-shangshu bootstrap-yijing bootstrap-mozi ingest-candidate qc-candidate ai-review-candidate refine-candidate promote-candidate ingestion-gauntlet corpus corpus-work pilot init-db import-corpus import-pilot export-corpus export-pilot validate-policy audit-coverage validate-granularity audit-shijing-quality preflight-work validate-tmx qc-corpus qc-pilot regression install-hooks serve-api test single-test

bootstrap-corpus:
	$(PYTHON) scripts/bootstrap_work_corpus.py --skip-fetch

bootstrap-work:
	$(PYTHON) scripts/bootstrap_work_corpus.py --skip-fetch --work-id $(WORK)

bootstrap-lunyu:
	$(PYTHON) scripts/bootstrap_lunyu_corpus.py --skip-fetch

bootstrap-mengzi:
	$(PYTHON) scripts/bootstrap_mengzi_corpus.py --skip-fetch

bootstrap-shijing:
	$(PYTHON) scripts/bootstrap_shijing_corpus.py --skip-fetch

bootstrap-laozi:
	$(PYTHON) scripts/bootstrap_laozi_corpus.py --skip-fetch

bootstrap-shangshu:
	$(PYTHON) scripts/bootstrap_shangshu_corpus.py --skip-fetch

bootstrap-yijing:
	$(PYTHON) scripts/bootstrap_yijing_corpus.py --skip-fetch

bootstrap-mozi:
	$(PYTHON) scripts/bootstrap_mozi_corpus.py --skip-fetch

ingest-candidate:
	$(PYTHON) scripts/ingestion_gauntlet.py ingest --work-id $(WORK) --skip-fetch

qc-candidate:
	$(PYTHON) scripts/ingestion_gauntlet.py qc --work-id $(WORK)

ai-review-candidate:
	$(PYTHON) scripts/ingestion_gauntlet.py ai-review --work-id $(WORK)

refine-candidate:
	$(PYTHON) scripts/ingestion_gauntlet.py refine --work-id $(WORK) --skip-fetch

promote-candidate:
	$(PYTHON) scripts/ingestion_gauntlet.py promote --work-id $(WORK)

ingestion-gauntlet:
	$(PYTHON) scripts/ingestion_gauntlet.py run --work-id $(WORK) --skip-fetch

corpus:
	$(PYTHON) scripts/corpus_workflow.py --work-id lunyu

corpus-work:
	$(PYTHON) scripts/corpus_workflow.py --work-id $(WORK)

pilot: corpus

init-db:
	$(PYTHON) scripts/init_db.py

import-corpus:
	$(PYTHON) scripts/import_corpus.py

import-pilot: import-corpus

export-corpus:
	$(PYTHON) scripts/export_corpus.py --work-id $(WORK)

export-pilot: export-corpus

validate-policy:
	$(PYTHON) scripts/validate_ingestion_policy.py

audit-coverage:
	$(PYTHON) scripts/audit_work_coverage.py --work-id $(WORK)

validate-granularity:
	$(PYTHON) scripts/validate_alignment_granularity.py --work-id $(WORK)

audit-shijing-quality:
	$(PYTHON) scripts/audit_shijing_completion_quality.py

preflight-work:
	$(PYTHON) scripts/validate_ingestion_policy.py --work-id $(WORK)
	$(PYTHON) scripts/audit_work_coverage.py --work-id $(WORK)
	$(PYTHON) scripts/validate_alignment_granularity.py --work-id $(WORK)

validate-tmx:
	$(PYTHON) scripts/validate_tmx.py --work-id $(WORK)

qc-corpus:
	$(PYTHON) scripts/qc_corpus.py --work-id $(WORK)

qc-pilot: qc-corpus

regression:
	$(MAKE) bootstrap-corpus
	$(MAKE) validate-policy
	$(MAKE) corpus
	$(MAKE) corpus-work WORK=laozi
	$(MAKE) corpus-work WORK=shangshu
	$(MAKE) corpus-work WORK=yijing
	$(MAKE) corpus-work WORK=mozi
	$(MAKE) corpus-work WORK=mengzi
	$(MAKE) corpus-work WORK=shijing
	$(MAKE) preflight-work WORK=lunyu
	$(MAKE) preflight-work WORK=laozi
	$(MAKE) preflight-work WORK=shangshu
	$(MAKE) preflight-work WORK=yijing
	$(MAKE) preflight-work WORK=mozi
	$(MAKE) preflight-work WORK=mengzi
	$(MAKE) preflight-work WORK=shijing
	$(MAKE) audit-shijing-quality
	$(MAKE) test

install-hooks:
	$(PYTHON) scripts/install_git_hooks.py

serve-api:
	$(PYTHON) web/api/corpus_api.py

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

single-test:
	$(PYTHON) -m unittest $(TEST)
