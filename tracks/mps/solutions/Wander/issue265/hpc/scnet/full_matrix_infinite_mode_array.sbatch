#!/usr/bin/env bash
#SBATCH --job-name=ghd_infmat
#SBATCH --partition=xhacnormalb
#SBATCH --account=giggleliu
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=24G
#SBATCH --time=06:00:00
#SBATCH --array=0-15%4

set -euo pipefail

module load anaconda3/2023.09
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export OPENBLAS_NUM_THREADS="${SLURM_CPUS_PER_TASK}"
export MKL_NUM_THREADS="${SLURM_CPUS_PER_TASK}"

: "${THEORY_ROOT:?THEORY_ROOT must name the persistent run directory}"
SOURCE_ROOT="${THEORY_ROOT}/source"
RESULT_ROOT="${THEORY_ROOT}/results"
mkdir -p "${RESULT_ROOT}"

fields=(0.2 0.16666666666666666 0.125 0.1)
seeds=(265 1265 2265 3265)
field_index=$((SLURM_ARRAY_TASK_ID / 4))
seed_index=$((SLURM_ARRAY_TASK_ID % 4))
field="${fields[$field_index]}"
seed="${seeds[$seed_index]}"

case "${field_index}" in
  0) field_tag=h0200 ;;
  1) field_tag=h016667 ;;
  2) field_tag=h0125 ;;
  3) field_tag=h0100 ;;
  *) echo "invalid field index ${field_index}" >&2; exit 2 ;;
esac

output="${RESULT_ROOT}/${field_tag}_seed${seed}_samples8.json"
temporary="${output}.partial.${SLURM_JOB_ID}_${SLURM_ARRAY_TASK_ID}"
trap 'rm -f "${temporary}"' EXIT

# Do not use here-documents here: several SCNet nodes can have a full local
# Slurm spool even while the persistent parallel filesystem is healthy.
mapfile -t times < <(python -c \
  'import sys; h=float(sys.argv[1]); print("\n".join(str(0.025*i/h**3) for i in range(17)))' \
  "${field}")

wave_step=$(python -c \
  'import sys; h=float(sys.argv[1]); print(0.4*h**2)' "${field}")

cd "${SOURCE_ROOT}"
python scripts/derive_low_rank_self_consistent_full_matrix.py \
  --field "${field}" \
  --string-xi-cutoff 6 \
  --scaled-rapidity-extent 6 \
  --scaled-rapidity-map-alpha 3 \
  --nodes-per-string 12 \
  --fourier-points 4 \
  --wave-step "${wave_step}" \
  --times "${times[@]}" \
  --samples 8 \
  --seed "${seed}" \
  --trace-distribution rademacher \
  --dyson-iterations 20 \
  --anderson-depth 5 \
  --stop-on-convergence \
  --dyson-convergence-tolerance 1e-3 \
  --output "${temporary}"

python -c '
import json, pathlib, sys
path = pathlib.Path(sys.argv[1])
payload = json.loads(path.read_text())
if not payload["iteration"]["converged"]:
    raise SystemExit("raw fixed-point convergence criterion was not met")
if payload["uses_target_a_or_D"] or payload["uses_target_trajectory"]:
    raise SystemExit("forbidden target-data dependency reported")
if not payload["fdt"]["positive_semidefinite"]:
    raise SystemExit("FDT covariance is not positive semidefinite")
if payload["static_susceptibility_captured_fraction"] < 0.96:
    raise SystemExit("retained rapidity/string modes capture less than 96% of susceptibility")
' "${temporary}"

mv "${temporary}" "${output}"
trap - EXIT
