PYTHON := .raw/venv/bin/python
PIP := .raw/venv/bin/pip

.PHONY: setup julia-setup test test-python test-julia graphs campaign aggregate study rooted-study rooted-issue-scan final-report clean-results

setup:
	python3 -m venv .raw/venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

test: test-python test-julia

test-python:
	PYTHONPATH=src $(PYTHON) -m unittest discover -s tests -v

julia-setup:
	JULIA_DEPOT_PATH=.raw/julia-depot: julia --project=julia -e 'using Pkg; Pkg.instantiate(); Pkg.precompile()'

test-julia:
	JULIA_DEPOT_PATH=.raw/julia-depot: julia --project=julia julia/test/runtests.jl

graphs:
	PYTHONPATH=src $(PYTHON) scripts/export_hierarchy_graphs.py --max-radius 3

campaign:
	$(PYTHON) scripts/build_campaign.py

aggregate:
	$(PYTHON) scripts/aggregate_campaign.py

study:
	PYTHONPATH=src $(PYTHON) scripts/run_study.py

rooted-study:
	MPLCONFIGDIR=.raw/matplotlib PYTHONPATH=src $(PYTHON) scripts/run_rooted_study.py

rooted-issue-scan:
	MPLCONFIGDIR=.raw/matplotlib PYTHONPATH=src $(PYTHON) scripts/run_rooted_issue_scan.py

final-report:
	MPLCONFIGDIR=.raw/matplotlib PYTHONPATH=src $(PYTHON) scripts/analyze_deadline.py --nested-results results/deadline_nested_mkl
	$(PYTHON) scripts/build_final_submission.py

clean-results:
	@echo "Remove results/ and .figures/ manually if you really want to discard them."
