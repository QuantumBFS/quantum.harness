PYTHON ?= python3

.PHONY: test eval examples knowledge-check check report report-check check-all

test:
	$(PYTHON) -m unittest discover -s tests -v

eval:
	$(PYTHON) eval/evaluate.py

examples:
	$(PYTHON) examples/run_example.py

knowledge-check:
	$(PYTHON) -m json.tool knowledge/schema.yaml >/dev/null
	$(PYTHON) -m json.tool knowledge/claims.yaml >/dev/null
	$(PYTHON) -m json.tool knowledge/material_cases.yaml >/dev/null
	$(PYTHON) -m json.tool eval/cases.yaml >/dev/null
	$(PYTHON) -m json.tool examples/toy_common_shift.yaml >/dev/null
	$(PYTHON) -m json.tool examples/toy_orbital_splitting.yaml >/dev/null

check: test eval examples knowledge-check

report:
	$(MAKE) -C report

report-check:
	$(MAKE) -C report check

check-all: check report-check
