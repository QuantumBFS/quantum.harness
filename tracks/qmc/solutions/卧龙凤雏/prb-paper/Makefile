PYTHON ?= .venv/bin/python
MPLCONFIGDIR ?= /private/tmp/prb-paper-matplotlib

.PHONY: setup test figures manuscript verify clean

setup:
	test -d .venv || python3 -m venv --system-site-packages .venv
	.venv/bin/pip install -r requirements.txt

test:
	MPLCONFIGDIR="$(MPLCONFIGDIR)" "$(PYTHON)" -m pytest -q

figures:
	MPLCONFIGDIR="$(MPLCONFIGDIR)" "$(PYTHON)" build_values.py
	MPLCONFIGDIR="$(MPLCONFIGDIR)" "$(PYTHON)" build_figures.py

manuscript: figures
	latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex

verify: manuscript
	"$(PYTHON)" verify_pdf.py paper.pdf

clean:
	latexmk -C paper.tex
	rm -f generated/*.pdf generated/*.png generated/headline_values.tex
