#!/bin/bash
#SBATCH --job-name=occ71-pysat-env
#SBATCH --partition=home
#SBATCH --nodelist=n006
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=00:15:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/tools/logs/pysat-setup-%j.out
#SBATCH --error=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/tools/logs/pysat-setup-%j.err

set -euo pipefail

ROOT=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
TOOLS="$ROOT/results/occam71/tools"
WHEELS="$TOOLS/pysat-wheels-cp313"
FINAL="$TOOLS/pysat-venv-job-$SLURM_JOB_ID"
STAGING="$TOOLS/.pysat-venv-job-$SLURM_JOB_ID.staging"

mkdir -p "$TOOLS/logs"
test ! -e "$FINAL"
test ! -e "$STAGING"
test -s "$WHEELS/python_sat-1.8.dev20-cp313-cp313-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"
test -s "$WHEELS/six-1.17.0-py2.py3-none-any.whl"

export PYTHONHASHSEED=42
python3 -m venv "$STAGING"
"$STAGING/bin/python" -m pip install \
  --no-index \
  --disable-pip-version-check \
  --find-links "$WHEELS" \
  python-sat six

"$STAGING/bin/python" - <<'PY'
from pysat.solvers import Solver

available = []
for name in ("cadical195", "cadical153", "glucose42", "minisat22"):
    try:
        with Solver(name=name, bootstrap_with=[[1]]) as solver:
            if solver.solve() is not True:
                raise RuntimeError(f"{name} failed positive control")
            available.append(name)
    except Exception:
        pass
if not available:
    raise RuntimeError("none of the audited SAT backends is available")
print("PYSAT_BACKENDS_OK", ",".join(available), flush=True)
PY

mv "$STAGING" "$FINAL"
printf 'job_id=%s\nseed=42\n' "$SLURM_JOB_ID" > "$FINAL/READY"
test -s "$FINAL/READY"
printf 'PYSAT_VENV=%s\n' "$FINAL"
