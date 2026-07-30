#!/usr/bin/env bash
#SBATCH --job-name=issue128-verify
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --qos=user_acamtw70yu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=32G
#SBATCH --time=04:30:00
#SBATCH --output=results/slurm-%x-%j.out
#SBATCH --error=results/slurm-%x-%j.err

set -euo pipefail
: "${ISSUE128_RUN_ID:?ISSUE128_RUN_ID must name the result run}"

export PYTHONHASHSEED=0
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1

REPOSITORY_ROOT="${SLURM_SUBMIT_DIR:?}"
ISSUE_ROOT="$REPOSITORY_ROOT/tracks/qcs/solutions/WangTheoPhys/issue128"
OUT="$REPOSITORY_ROOT/results/$ISSUE128_RUN_ID/verification"
mkdir -p "$OUT"
cd "$ISSUE_ROOT"

set +e
"$REPOSITORY_ROOT/.venv/bin/python" -u scripts/verify.py \
  certificates/issue128-certificate.json --deep \
  >"$OUT/deep-verifier.stdout" 2>"$OUT/deep-verifier.stderr"
VERIFY_RC=$?
"$REPOSITORY_ROOT/.venv/bin/python" -m pytest -q -o addopts='' \
  >"$OUT/pytest.stdout" 2>"$OUT/pytest.stderr"
PYTEST_RC=$?
set -e

"$REPOSITORY_ROOT/.venv/bin/python" - "$OUT" "$VERIFY_RC" "$PYTEST_RC" <<'PY'
import datetime
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
verify_rc = int(sys.argv[2])
pytest_rc = int(sys.argv[3])
files = {}
for path in sorted(root.glob("*.std*")):
    files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
payload = {
    "schema_version": 1,
    "kind": "issue128_hpc_verification",
    "status": "complete" if verify_rc == 0 and pytest_rc == 0 else "failed",
    "deep_verifier_exit_code": verify_rc,
    "pytest_exit_code": pytest_rc,
    "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "sha256": files,
}
(root / "manifest.json.tmp").write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
(root / "manifest.json.tmp").replace(root / "manifest.json")
PY

test "$VERIFY_RC" -eq 0
test "$PYTEST_RC" -eq 0
