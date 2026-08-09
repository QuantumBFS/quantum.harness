PYTHON ?= python3
LATEXMK ?= latexmk
JOBNAME := issue128-proof-carrying-trotter-paper
OUTDIR := output/pdf

.PHONY: check figures pdf

check:
	$(PYTHON) scripts/validate_claims.py

figures:
	$(PYTHON) scripts/generate_figures.py

pdf: check figures
	$(LATEXMK) -pdf -interaction=nonstopmode -halt-on-error \
		-jobname=$(JOBNAME) -outdir=$(OUTDIR) main.tex
