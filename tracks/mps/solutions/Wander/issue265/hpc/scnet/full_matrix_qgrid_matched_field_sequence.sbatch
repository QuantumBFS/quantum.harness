#!/usr/bin/env bash
#SBATCH --job-name=ghd_qgrid_h
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=24:00:00

# The submitter adds --array=0-$((7*REPLICATES_PER_FIELD-1))%<limit> only
# after the single-wave field and q-grid momentum-sampling gates are accepted.
set -euo pipefail
module load anaconda3/2023.09
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
: "${THEORY_ROOT:?THEORY_ROOT is required}"
: "${TRACE_PAIRING_COUNT:?TRACE_PAIRING_COUNT is required}"
: "${MOMENTUM_SAMPLES:?MOMENTUM_SAMPLES is required}"
: "${REPLICATES_PER_FIELD:?REPLICATES_PER_FIELD is required}"

case "${TRACE_PAIRING_COUNT}" in
  1|2|4|8) ;;
  *) echo "TRACE_PAIRING_COUNT must be one of 1,2,4,8" >&2; exit 2 ;;
esac
if ! [[ "${MOMENTUM_SAMPLES}" =~ ^[1-9][0-9]*$ ]]; then
  echo "MOMENTUM_SAMPLES must be a positive integer" >&2
  exit 2
fi
if ! [[ "${REPLICATES_PER_FIELD}" =~ ^[1-9][0-9]*$ ]]; then
  echo "REPLICATES_PER_FIELD must be a positive integer" >&2
  exit 2
fi

fields=(0.3 0.25 0.2 0.16666666666666666 0.125 0.1 0.08333333333333333)
tags=(h0300 h0250 h0200 h016667 h0125 h0100 h008333)
field_index=$((SLURM_ARRAY_TASK_ID / REPLICATES_PER_FIELD))
replicate_index=$((SLURM_ARRAY_TASK_ID % REPLICATES_PER_FIELD))
if (( field_index < 0 || field_index >= ${#fields[@]} )); then
  echo "array task ${SLURM_ARRAY_TASK_ID} is outside the seven-field q grid" >&2
  exit 2
fi

field="${fields[$field_index]}"
field_tag="${tags[$field_index]}"
seed=$((265 + 1000 * replicate_index))
SOURCE_ROOT="${THEORY_ROOT}/source"
RESULT_ROOT="${THEORY_ROOT}/results"
mkdir -p "${RESULT_ROOT}"
output="${RESULT_ROOT}/${field_tag}_pair${TRACE_PAIRING_COUNT}_seed${seed}_srht_P${MOMENTUM_SAMPLES}_F32_tauwall.json"
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
  --momentum-samples "${MOMENTUM_SAMPLES}" \
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
if r["fourier_points"] != 32: raise SystemExit("Fourier grid mismatch")
if r["trace_pairings_per_frame"] != int(sys.argv[2]): raise SystemExit("pairing mismatch")
if r["momentum_samples_per_external_wave"] != int(sys.argv[3]): raise SystemExit("momentum sample mismatch")
if r["trace_source_layout"] != "shared_wave": raise SystemExit("source layout mismatch")
if r["internal_momentum_sum_exact"]: raise SystemExit("unexpected exact momentum sum")
m=p["matrix_diagnostics"]
if m["diffusion_off_diagonal_frobenius_fraction"] <= 0: raise SystemExit("diagonal diffusion")
if m["fdt_noise_off_diagonal_frobenius_fraction"] <= 0: raise SystemExit("diagonal noise")
if m["diffusion_static_metric_commutator_relative_norm"] > 1e-10: raise SystemExit("metric mismatch")
' "${temporary}" "${TRACE_PAIRING_COUNT}" "${MOMENTUM_SAMPLES}"
mv "${temporary}" "${output}"
trap - EXIT
