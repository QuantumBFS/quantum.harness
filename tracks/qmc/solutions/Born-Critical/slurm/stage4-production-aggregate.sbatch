#!/bin/bash
#SBATCH --job-name=born-critical-stage4-aggregate
#SBATCH --output=/tmp/born-critical-stage4-aggregate-%j.out
#SBATCH --error=/tmp/born-critical-stage4-aggregate-%j.err
#SBATCH --chdir=/tmp

set -euo pipefail

ws0_host="${BORN_CRITICAL_WS0_HOST:-ystu@ws0}"
source_path="/home/ystu/quantum.harness/tracks/qmc/solutions/Born-Critical"
run_path="/home/ystu/quantum.harness/tracks/qmc/results/born-critical/selfdual-production-v1"
job_id="${SLURM_JOB_ID:?SLURM_JOB_ID is required}"
work="$(mktemp -d "/tmp/born-critical-stage4-aggregate-${job_id}-XXXXXX")"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/source" "$work/run" "$work/output"
rsync -a --exclude '__pycache__/' --exclude '.pytest_cache/' \
    "${ws0_host}:${source_path}/" "$work/source/"
rsync -a "${ws0_host}:${run_path}/run_spec.json" "$work/run/run_spec.json"
rsync -a "${ws0_host}:${run_path}/cells/" "$work/run/cells/"
source /opt/miniconda3/etc/profile.d/conda.sh
conda activate torch
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$work/source"
set +e
PYTHONPATH=src python -u scripts/aggregate_selfdual_production.py \
    --run "$work/run" \
    --declaration configs/selfdual-production-analysis.json \
    --output "$work/output"
return_code=$?
set -e
cp /tmp/born-critical-stage4-aggregate-"${job_id}".out \
    "$work/output/runner.log" 2>/dev/null || true
python - "$work/output" "$job_id" "$return_code" <<'PY'
import json,pathlib,socket,sys
root=pathlib.Path(sys.argv[1])
payload={
    "schema_version":1,
    "stage":"stage4-production-aggregate",
    "status":"success" if int(sys.argv[3]) == 0 else "failed",
    "return_code":int(sys.argv[3]),
    "slurm_job_id":sys.argv[2],
    "hostname":socket.gethostname(),
}
(root/"manifest.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
PY
remote_temporary="${run_path}/.aggregate.incoming-${job_id}"
ssh "$ws0_host" "test ! -e '${remote_temporary}'"
rsync -a "$work/output/" "${ws0_host}:${remote_temporary}/"
ssh "$ws0_host" \
    "if test -e '${run_path}/aggregate'; then mv '${run_path}/aggregate' '${run_path}/aggregate.previous-${job_id}'; fi; mv '${remote_temporary}' '${run_path}/aggregate'"
exit "$return_code"
