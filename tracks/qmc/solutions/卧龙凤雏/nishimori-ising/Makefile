.PHONY: setup test run run-test clean-generated

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r analysis/requirements.txt

test:
	cargo fmt --check
	cargo clippy --all-targets -- -D warnings
	cargo test --release
	MPLCONFIGDIR=/tmp/nishimori-ising-mpl .venv/bin/pytest -q

run:
	bash run.sh configs/production.toml

run-test:
	bash run.sh configs/test.toml

clean-generated:
	@echo "Generated runs live under tracks/qmc/results/; remove an explicit run directory manually."
