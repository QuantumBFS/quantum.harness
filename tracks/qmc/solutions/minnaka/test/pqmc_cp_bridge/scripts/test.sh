#!/usr/bin/env bash
set -euo pipefail

bridge_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
repo_root="$(cd "${bridge_root}/../.." && pwd)"

set +u
source /opt/intel/oneapi/setvars.sh >/dev/null 2>&1 || true
set -u
command -v icpx >/dev/null
command -v mpirun >/dev/null

make -C "${repo_root}/test/cpmc_path_audit" all test
/usr/bin/python3 -m unittest discover \
    -s "${bridge_root}/tests" -p 'test_*.py' -v
/usr/bin/python3 \
    "${repo_root}/test/alf_hirsch_binary/tests/test_binary_hirsch.py"
/usr/bin/python3 "${bridge_root}/scripts/bootstrap_trials.py"

smoke_root="$(mktemp -d "${bridge_root}/runs/test-smoke-XXXXXX")"
cleanup() {
    rm -rf -- "${smoke_root}"
}
trap cleanup EXIT

/usr/bin/python3 "${bridge_root}/scripts/run_alf_batch.py" \
    --ensemble TI --theta 10 --batch 0 --nbin 3 --nsweep 2 \
    --run-root "${smoke_root}" --master-seed 907001 \
    --executable \
    "${repo_root}/test/alf_hirsch_binary/run/binary/bin/ALF.binary.out"

/usr/bin/python3 - "${smoke_root}" "${bridge_root}" <<'PY'
from pathlib import Path
import sys

run_root = Path(sys.argv[1])
bridge_root = Path(sys.argv[2])
sys.path.insert(0, str(bridge_root / "scripts"))
from calibrate_projection import RealBackend

backend = RealBackend(
    run_root=run_root,
    executable=(
        bridge_root.parents[1] / "test" / "alf_hirsch_binary" / "run"
        / "binary" / "bin" / "ALF.binary.out"
    ),
    trial_assets=bridge_root / "assets" / "trials",
    master_seed=907001,
)
estimate = backend.analyze("TI", 10)
if estimate.hard_failure is not None:
    raise SystemExit(estimate.hard_failure)
if estimate.retained_bins != 2 or estimate.negative_sign_bins != 0:
    raise SystemExit(f"unexpected real smoke estimate: {estimate}")
print(f"PASS: real six-chain TI smoke E={estimate.mean:.8f}", flush=True)
PY
