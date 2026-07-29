.PHONY: setup test build clean-generated

setup:
	test -d .venv || python3 -m venv --system-site-packages .venv
	.venv/bin/pip install -r requirements.txt

test:
	MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python -m pytest -q

build:
	MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python build_report.py

clean-generated:
	rm -f generated/*.png
	rm -f tmp/pdfs/three-model-central-charge-report-*.png
