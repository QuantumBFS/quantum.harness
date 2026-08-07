#!/usr/bin/env bash
#SBATCH --job-name=ceffflow
#SBATCH --partition=hx1hdnormal01
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=3800M
#SBATCH --time=24:00:00
#SBATCH --array=0-104
#SBATCH --output=results/ceffflow-production/logs/%A_%a.out
#SBATCH --error=results/ceffflow-production/logs/%A_%a.err

set -euo pipefail

PROJECT_ROOT="${CEFFFLOW_PROJECT_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
DEPENDENCY_ROOT="${CEFFFLOW_DEPENDENCY_ROOT:-${PROJECT_ROOT}/.deps}"
RUN_SPEC="${CEFFFLOW_RUN_SPEC:-results/ceffflow-production/run_spec.json}"
CELL_NUMBER=$((SLURM_ARRAY_TASK_ID + 1))
CELL_ID=$(printf 'cell-%04d' "${CELL_NUMBER}")

cd "${PROJECT_ROOT}"

if [[ -z "${CEFFFLOW_PYTHON:-}" ]]; then
  if type module >/dev/null 2>&1; then
    module load anaconda3/2023.09
  fi
  CEFFFLOW_PYTHON=$(command -v python3 || command -v python)
fi

export PYTHONPATH="${DEPENDENCY_ROOT}:${PROJECT_ROOT}/src${PYTHONPATH:+:${PYTHONPATH}}"

"${CEFFFLOW_PYTHON}" -c '
import sys
import numpy
import pydantic
import scipy

def major_minor(value):
    return tuple(int(part) for part in value.split(".")[:2])

assert sys.version_info >= (3, 11)
assert major_minor(numpy.__version__) >= (2, 0)
assert major_minor(scipy.__version__) >= (1, 13)
assert major_minor(pydantic.__version__) >= (2, 8)
'

if [[ -z "${CEFFFLOW_SOURCE_COMMIT:-}" ]] && \
   [[ -f "${PROJECT_ROOT}/.ceffflow-source-commit" ]]; then
  CEFFFLOW_SOURCE_COMMIT=$(<"${PROJECT_ROOT}/.ceffflow-source-commit")
fi
export CEFFFLOW_SOURCE_COMMIT

export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

mkdir -p results/ceffflow-production/logs
"${CEFFFLOW_PYTHON}" scripts/run_ceffflow_cell.py \
  --run-spec "${RUN_SPEC}" \
  --cell-id "${CELL_ID}"
