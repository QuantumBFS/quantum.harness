.PHONY: setup test build build-en build-zh build-all clean-generated

setup:
	test -d .venv || python3 -m venv --system-site-packages .venv
	.venv/bin/pip install -r requirements.txt

test:
	MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python -m pytest -q

build:
	MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python build_report.py

build-en:
	MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python build_report.py --language en

build-zh:
	MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python build_report.py --language zh

build-all:
	MPLCONFIGDIR=/tmp/integrated-report-mpl .venv/bin/python build_report.py --language all

clean-generated:
	rm -f generated/*.png
	rm -f generated/zh/*.png
	rm -f generated/zh/clean-ising/*.png
	rm -f generated/zh/nishimori-ising/*.png
	rm -f generated/zh/weak-self-dual/*.png
	rm -f tmp/pdfs/three-model-central-charge-report-*.png
