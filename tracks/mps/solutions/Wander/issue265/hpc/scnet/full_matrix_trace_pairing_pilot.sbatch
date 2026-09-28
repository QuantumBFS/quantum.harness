#!/usr/bin/env bash
#SBATCH --job-name=ghd_pairpilot
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=08:00:00
#SBATCH --array=0-7%4

set -euo pipefail
module load anaconda3/2023.09
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
: "${THEORY_ROOT:?THEORY_ROOT is required}"
SOURCE_ROOT="${THEORY_ROOT}/source"
RESULT_ROOT="${THEORY_ROOT}/results"
mkdir -p "${RESULT_ROOT}"

pairings=(2 4)
seeds=(265 1265 2265 3265)
pairing_index=$((SLURM_ARRAY_TASK_ID / 4))
seed_index=$((SLURM_ARRAY_TASK_ID % 4))
pairing_count="${pairings[$pairing_index]}"
seed="${seeds[$seed_index]}"
field=0.16666666666666666
output="${RESULT_ROOT}/h016667_pair${pairing_count}_seed${seed}_samples8_srht_tauwall.json"
temporary="${output}.partial.${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
trap 'rm -f "${temporary}"' EXIT
mapfile -t times < <(python -c \
  'import math,sys; h=float(sys.argv[1]); tau=27/(10*math.pi); print("\n".join(str(tau*i/(18*h**3)) for i in range(19)))' \
  "${field}")
wave_step=$(python -c 'import sys; h=float(sys.argv[1]); print(0.4*h**2)' "${field}")

cd "${SOURCE_ROOT}"
python scripts/derive_low_rank_self_consistent_full_matrix.py \
  --field "${field}" --string-xi-cutoff 6 \
  --scaled-rapidity-extent 6 --scaled-rapidity-map-alpha 3 \
  --nodes-per-string 12 --fourier-points 4 --wave-step "${wave_step}" \
  --times "${times[@]}" --samples 8 --seed "${seed}" \
  --trace-distribution srht_rademacher --trace-source-layout shared_wave \
  --trace-pairing-count "${pairing_count}" \
  --dyson-iterations 20 --anderson-depth 5 --stop-on-convergence \
  --dyson-convergence-tolerance 1e-3 --output "${temporary}"
python -c '
import json,math,pathlib,sys
p=json.loads(pathlib.Path(sys.argv[1]).read_text())
if not p["iteration"]["converged"]: raise SystemExit("fixed point failed")
if p["uses_target_a_or_D"] or p["uses_target_trajectory"]: raise SystemExit("target dependency")
if not p["fdt"]["positive_semidefinite"]: raise SystemExit("FDT failed")
if p["static_susceptibility_captured_fraction"] < .96: raise SystemExit("capture failed")
if abs(p["scaled_times_tau_equals_t_h3"][-1]-27/(10*math.pi))>1e-12: raise SystemExit("tau failed")
if p["regulator"]["trace_pairings_per_frame"] != int(sys.argv[2]): raise SystemExit("pairing mismatch")
' "${temporary}" "${pairing_count}"
mv "${temporary}" "${output}"
trap - EXIT
