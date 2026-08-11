#!/bin/sh
set -eu

project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"

python_bin="${PYTHON_BIN:-$project_dir/.venv/bin/python}"
"$python_bin" -m floquet_if_manybody.cli baselines --output results --figures figures
"$python_bin" -m floquet_if_manybody.cli audit results
