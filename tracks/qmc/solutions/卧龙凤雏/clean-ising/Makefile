.PHONY: setup test run clean-generated

setup:
	python3 -m venv .venv
	.venv/bin/pip install -r analysis/requirements.txt

test:
	cargo fmt --check
	cargo clippy --all-targets -- -D warnings
	cargo test --release
	MPLCONFIGDIR=/tmp/clean-ising-mpl .venv/bin/pytest analysis/tests -q

run:
	bash run.sh configs/quick.toml

clean-generated:
	@echo "Generated runs live under tracks/qmc/results/; remove an explicit run directory manually."
