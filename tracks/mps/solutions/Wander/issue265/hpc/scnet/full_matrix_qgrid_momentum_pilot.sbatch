#!/usr/bin/env bash
#SBATCH --job-name=ghd_qgrid_p
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
: "${TRACE_PAIRING_COUNT:?TRACE_PAIRING_COUNT is required}"
case "${TRACE_PAIRING_COUNT}" in
  1|2|4|8) ;;
  *) echo "TRACE_PAIRING_COUNT must be one of 1,2,4,8" >&2; exit 2 ;;
esac
SOURCE_ROOT="${THEORY_ROOT}/source"
RESULT_ROOT="${THEORY_ROOT}/results"
mkdir -p "${RESULT_ROOT}"

seeds=(265 1265 2265 3265)
momentum_samples=(4 8)
sample_index=$((SLURM_ARRAY_TASK_ID / 4))
seed_index=$((SLURM_ARRAY_TASK_ID % 4))
p_samples="${momentum_samples[$sample_index]}"
seed="${seeds[$seed_index]}"
field=0.2
output="${RESULT_ROOT}/h0200_pair${TRACE_PAIRING_COUNT}_seed${seed}_srht_P${p_samples}_F32_tauwall.json"
temporary="${output}.partial.${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
trap 'rm -f "${temporary}"' EXIT

mapfile -t times < <(python -c \
  'import math,sys; h=float(sys.argv[1]); tau=27/(10*math.pi); print("\n".join(str(tau*i/(18*h**3)) for i in range(19)))' \
  "${field}")
wave_step=$(python -c 'import sys; h=float(sys.argv[1]); print(0.25*h**2)' "${field}")

cd "${SOURCE_ROOT}"
python scripts/derive_low_rank_self_consistent_full_matrix.py \
  --field "${field}" --string-xi-cutoff 6 \
  --scaled-rapidity-extent 6 --scaled-rapidity-map-alpha 3 \
  --nodes-per-string 12 --fourier-points 32 --wave-step "${wave_step}" \
  --times "${times[@]}" --samples 8 --seed "${seed}" \
  --trace-distribution srht_rademacher --trace-source-layout shared_wave \
  --trace-pairing-count "${TRACE_PAIRING_COUNT}" \
  --momentum-samples "${p_samples}" \
  --dyson-iterations 20 --anderson-depth 5 --stop-on-convergence \
  --dyson-convergence-tolerance 1e-3 --output "${temporary}"
python -c '
import json,math,pathlib,sys
p=json.loads(pathlib.Path(sys.argv[1]).read_text())
if not p["iteration"]["converged"]: raise SystemExit("fixed point failed")
if p["uses_target_a_or_D"] or p["uses_target_trajectory"]: raise SystemExit("target dependency")
if not p["fdt"]["positive_semidefinite"]: raise SystemExit("FDT failed")
if not p["scope"].get("colored_memory_available_for_exact_mori_prefix_matching"): raise SystemExit("colored Mori memory missing")
if p["scope"].get("white_noise_contact_inserted_into_colored_memory"): raise SystemExit("bare white contact inserted")
if len(p.get("projected_colored_continuity_memory_by_wave_then_time", [])) != p["regulator"]["fourier_points"]: raise SystemExit("colored Mori memory shape failed")
if p["static_susceptibility_captured_fraction"] < .96: raise SystemExit("capture failed")
if abs(p["scaled_times_tau_equals_t_h3"][-1]-27/(10*math.pi))>1e-12: raise SystemExit("tau failed")
r=p["regulator"]
if r["trace_distribution"] != "srht_rademacher": raise SystemExit("trace distribution mismatch")
if r["trace_source_layout"] != "shared_wave": raise SystemExit("source layout mismatch")
if r["trace_pairings_per_frame"] != int(sys.argv[2]): raise SystemExit("pairing mismatch")
if r["internal_momentum_sum_exact"]: raise SystemExit("pilot unexpectedly used exact momentum sum")
if r["fourier_points"] != 32: raise SystemExit("Fourier grid mismatch")
' "${temporary}" "${TRACE_PAIRING_COUNT}"
mv "${temporary}" "${output}"
trap - EXIT
