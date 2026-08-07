#!/usr/bin/env bash
#SBATCH --job-name=kharkov-j2-preflight
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=01:00:00
#SBATCH --output=/work/share/giggleliu/cfys01/kharkov_burgers_20260729/logs/j2-preflight-%j.out
#SBATCH --error=/work/share/giggleliu/cfys01/kharkov_burgers_20260729/logs/j2-preflight-%j.err

set -euo pipefail
unset LC_ALL
export LANG=C

source /usr/share/Modules/init/bash
module purge
module load anaconda3/2023.09

ROOT=/work/share/giggleliu/cfys01/kharkov_burgers_20260729
SOURCE="$ROOT/source"
PYTHON="$ROOT/env/tenpy-py311/bin/python"
OUT="$ROOT/data/preflight/j2"
MANIFEST="$SOURCE/results_research_program/manifest.json"
OBSERVABLES=magnetization,local_spin_current,czz,fcs_logZ

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
  "$PYTHON" scripts/run_tenpy_research_job.py \
    --manifest "$MANIFEST" \
    --job-id "$job_id" \
    --smoke \
    --L 8 \
    --dt 0.005 \
    --chi-max 128 \
    --truncation-cutoff 1e-12 \
    --t-max 0.2 \
    --output-dt 0.05 \
    --observables "$OBSERVABLES" \
    --fcs-gamma=-0.2,0,0.2 \
    --output "$output" \
    --checkpoint-every 1 \
    --overwrite \
    "$@"
}

run_smoke control_j2_up__production_a "$OUT/j2_up.npz"
run_smoke control_j2_down__production_a "$OUT/j2_down.npz"

"$PYTHON" scripts/validate_tenpy_exact_diagonalization.py \
  --input "$OUT/j2_up.npz" \
  --outdir "$OUT/exact_j2_up"
"$PYTHON" scripts/validate_tenpy_exact_diagonalization.py \
  --input "$OUT/j2_down.npz" \
  --outdir "$OUT/exact_j2_down"
"$PYTHON" scripts/validate_tenpy_backend.py \
  --up "$OUT/j2_up.npz" \
  --down "$OUT/j2_down.npz" \
  --outdir "$OUT/symmetry"
"$PYTHON" scripts/validate_tenpy_fcs.py \
  --up "$OUT/j2_up.npz" \
  --down "$OUT/j2_down.npz" \
  --outdir "$OUT/fcs"

run_smoke amp_mu005_up__convergence__coarse \
  "$OUT/j2zero_ungrouped.npz"
run_smoke amp_mu005_up__convergence__coarse \
  "$OUT/j2zero_grouped.npz" \
  --force-grouped
"$PYTHON" scripts/validate_tenpy_grouped_equivalence.py \
  --ungrouped "$OUT/j2zero_ungrouped.npz" \
  --grouped "$OUT/j2zero_grouped.npz" \
  --outdir "$OUT/grouped_equivalence"

cp "$OUT/j2_up.npz" "$OUT/j2_up.pre_reload.npz"
run_smoke control_j2_up__production_a "$OUT/j2_up.npz" --resume
"$PYTHON" scripts/validate_tenpy_resume.py \
  --resumed "$OUT/j2_up.npz" \
  --uninterrupted "$OUT/j2_up.pre_reload.npz" \
  --fcs-resumed "$OUT/j2_up.npz" \
  --fcs-uninterrupted "$OUT/j2_up.pre_reload.npz" \
  --interruption-after-saved-time 0.2 \
  --outdir "$OUT/checkpoint_reload"
