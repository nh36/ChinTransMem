PYTHON ?= python3
TEST ?= tests.test_corpus_workflow.CorpusWorkflowTest.test_lunyu_workflow_counts_and_qc
WORK ?= lunyu

.PHONY: bootstrap-corpus bootstrap-work bootstrap-lunyu bootstrap-mengzi corpus corpus-work pilot init-db import-corpus import-pilot export-corpus export-pilot validate-tmx qc-corpus qc-pilot regression install-hooks serve-api test single-test

bootstrap-corpus:
	$(PYTHON) scripts/bootstrap_work_corpus.py --skip-fetch

bootstrap-work:
	$(PYTHON) scripts/bootstrap_work_corpus.py --skip-fetch --work-id $(WORK)

bootstrap-lunyu:
	$(PYTHON) scripts/bootstrap_lunyu_corpus.py --skip-fetch

bootstrap-mengzi:
	$(PYTHON) scripts/bootstrap_mengzi_corpus.py --skip-fetch

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

validate-tmx:
	$(PYTHON) scripts/validate_tmx.py --work-id $(WORK)

qc-corpus:
	$(PYTHON) scripts/qc_corpus.py --work-id $(WORK)

qc-pilot: qc-corpus

regression:
	$(MAKE) corpus
	$(MAKE) test

install-hooks:
	$(PYTHON) scripts/install_git_hooks.py

serve-api:
	$(PYTHON) web/api/corpus_api.py

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

single-test:
	$(PYTHON) -m unittest $(TEST)
