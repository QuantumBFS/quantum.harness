#!/usr/bin/env bash
#SBATCH --job-name=kharkov-v2-preflight
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --output=/work/share/giggleliu/cfys01/kharkov_burgers_20260729/logs/production-v2-preflight-%j.out
#SBATCH --error=/work/share/giggleliu/cfys01/kharkov_burgers_20260729/logs/production-v2-preflight-%j.err

set -euo pipefail
unset LC_ALL
export LANG=C

source /usr/share/Modules/init/bash
module purge
module load anaconda3/2023.09

ROOT=/work/share/giggleliu/cfys01/kharkov_burgers_20260729
SOURCE="$ROOT/source"
PYTHON="$ROOT/env/tenpy-py311/bin/python"
OUT="$ROOT/data/preflight/production_v2"
MANIFEST="$SOURCE/results_research_program/production_manifest_v2.json"
EVIDENCE="$SOURCE/results_research_program/hpc/production_v2_validation_20260730.json"

export PYTHONNOUSERSITE=1
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export NUMEXPR_NUM_THREADS="${SLURM_CPUS_PER_TASK}"

mkdir -p "$OUT" "$ROOT/logs"
cd "$SOURCE"

run_smoke() {
  local job_id=$1
  local output=$2
  shift 2
  "$PYTHON" scripts/run_tenpy_production_job.py \
    --manifest "$MANIFEST" \
    --job-id "$job_id" \
    --smoke \
    --L 8 \
    --dt 0.005 \
    --chi-max 128 \
    --truncation-cutoff 1e-12 \
    --t-max 0.5 \
    --output-dt 0.05 \
    --output "$output" \
    --checkpoint-every 1 \
    --overwrite \
    "$@"
}

run_smoke equilibrium_m0__production_a__v2 "$OUT/equilibrium_m0.npz" \
  --fcs-gamma=-0.6,-0.4,-0.2,0,0.2,0.4,0.6
cp "$OUT/equilibrium_m0.npz" "$OUT/equilibrium_m0.pre_reload.npz"
run_smoke equilibrium_m0__production_a__v2 "$OUT/equilibrium_m0.npz" \
  --fcs-gamma=-0.6,-0.4,-0.2,0,0.2,0.4,0.6 \
  --resume
run_smoke response_local_pulse_pos__production_a__v2 "$OUT/pulse_pos.npz"
run_smoke response_local_pulse_neg__production_a__v2 "$OUT/pulse_neg.npz"

"$PYTHON" scripts/validate_production_v2_preflight.py \
  --manifest "$MANIFEST" \
  --j2-evidence "$SOURCE/results_research_program/hpc/j2_validation_20260730.json" \
  --equilibrium "$OUT/equilibrium_m0.npz" \
  --pulse-pos "$OUT/pulse_pos.npz" \
  --pulse-neg "$OUT/pulse_neg.npz" \
  --equilibrium-before-reload "$OUT/equilibrium_m0.pre_reload.npz" \
  --output "$EVIDENCE"

"$PYTHON" - "$EVIDENCE" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text())
if payload.get("status") != "pass":
    raise SystemExit(f"production-v2 compute preflight did not pass: {payload.get('status')}")
PY
