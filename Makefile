PYTHON ?= python3
TEST ?= tests.test_pilot_workflow.PilotWorkflowTest.test_end_to_end

.PHONY: pilot init-db import-pilot export-pilot validate-tmx qc-pilot regression install-hooks serve-api test single-test

pilot:
	$(PYTHON) scripts/pilot_workflow.py

init-db:
	$(PYTHON) scripts/init_db.py

import-pilot:
	$(PYTHON) scripts/import_lunyu_legge_pilot.py

export-pilot:
	$(PYTHON) scripts/export_pilot.py

validate-tmx:
	$(PYTHON) scripts/validate_tmx.py

qc-pilot:
	$(PYTHON) scripts/qc_pilot.py

regression:
	$(MAKE) pilot
	$(MAKE) test

install-hooks:
	$(PYTHON) scripts/install_git_hooks.py

serve-api:
	$(PYTHON) web/api/pilot_api.py

test:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py'

single-test:
	$(PYTHON) -m unittest $(TEST)
