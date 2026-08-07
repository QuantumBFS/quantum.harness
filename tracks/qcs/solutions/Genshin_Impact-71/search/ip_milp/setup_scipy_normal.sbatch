#!/bin/bash
#SBATCH --job-name=occam71-scipy
#SBATCH --partition=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --time=00:15:00
#SBATCH --output=/home/user_milksang/private/homefile/quantum_harness/issue71_occam/results/occam71/ip-milp/setup-%j.log

set -euo pipefail
ROOT=/home/user_milksang/private/homefile/quantum_harness/issue71_occam
VENV="$ROOT/results/occam71/tools/scipy-milp-venv"
mkdir -p "$ROOT/results/occam71/ip-milp"
python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install --disable-pip-version-check \
  --require-hashes -r "$ROOT/tracks/qcs/solutions/Genshin_Impact-71/search/ip_milp/requirements.lock"
"$VENV/bin/python" - <<'PY'
import numpy, scipy
from scipy.optimize import milp
print("SCIPY_MILP_READY", numpy.__version__, scipy.__version__, milp.__module__, flush=True)
PY
