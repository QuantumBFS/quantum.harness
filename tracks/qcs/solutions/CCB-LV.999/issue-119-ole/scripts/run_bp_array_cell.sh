#!/bin/bash

set -euo pipefail

export JULIA_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=16
export OMP_NUM_THREADS=16
export HARNESS_JULIA_BIN="${HARNESS_JULIA_BIN:-$HOME/.juliaup/bin/julia}"

exec python3 "$(dirname "$0")/run_bp_array_cell.py"
