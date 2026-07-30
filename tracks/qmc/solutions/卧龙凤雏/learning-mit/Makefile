PYTHON ?= .venv/bin/python
MPLCONFIGDIR ?= /private/tmp/learning-mit-matplotlib

.PHONY: setup test run-test run-pilot run-production

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/python -m pip install -r analysis/requirements.txt

test:
	cargo test --offline --all-targets
	MPLCONFIGDIR="$(MPLCONFIGDIR)" "$(PYTHON)" -m pytest analysis/tests -q

run-test:
	LEARNING_MIT_PYTHON="$(PYTHON)" LEARNING_MIT_CARGO_PROFILE="" MPLCONFIGDIR="$(MPLCONFIGDIR)" ./run.sh test

run-pilot:
	LEARNING_MIT_PYTHON="$(PYTHON)" LEARNING_MIT_CARGO_PROFILE="--release" MPLCONFIGDIR="$(MPLCONFIGDIR)" ./run.sh pilot

run-production:
	LEARNING_MIT_PYTHON="$(PYTHON)" LEARNING_MIT_CARGO_PROFILE="--release" MPLCONFIGDIR="$(MPLCONFIGDIR)" ./run.sh production
