#!/usr/bin/env bash
#SBATCH --job-name=rdp-phase8
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --gres=gpu:1
#SBATCH --mem=24G
#SBATCH --time=04:00:00
#SBATCH --array=0-5

set -euo pipefail

: "${ROUTE_D_PLUS_REPO_ROOT:?set the remote repository root}"
: "${ROUTE_D_PLUS_DISPATCH:?set the immutable Phase 8 dispatch}"
: "${ROUTE_D_PLUS_WORKER:?set the Phase 8 worker executable}"
: "${SLURM_ARRAY_TASK_ID:?submit this script as a Slurm array}"

repo_root="$(cd -- "${ROUTE_D_PLUS_REPO_ROOT}" && pwd)"
solution_root="${repo_root}/tracks/qmc/solutions/BOTS-848"
python="${repo_root}/.venv/bin/python"

cd "${solution_root}"
"${python}" -m route_d_plus.future.verify preflight \
  --dispatch "${ROUTE_D_PLUS_DISPATCH}" \
  --repo-root "${repo_root}"
mapfile -t task_rows < <(
  "${python}" -m route_d_plus.future.verify list-tasks \
    --dispatch "${ROUTE_D_PLUS_DISPATCH}"
)
if (( SLURM_ARRAY_TASK_ID >= ${#task_rows[@]} )); then
  echo "array index exceeds the pre-registered task set" >&2
  exit 2
fi

IFS=$'\t' read -r task_id run_dir \
  <<<"${task_rows[SLURM_ARRAY_TASK_ID]}"
mkdir -p "${run_dir}"
"${ROUTE_D_PLUS_WORKER}" \
  --dispatch "${ROUTE_D_PLUS_DISPATCH}" \
  --task-id "${task_id}" \
  --run-dir "${run_dir}" \
  >"${run_dir}/stdout.log" 2>"${run_dir}/stderr.log"
"${python}" -m route_d_plus.future.verify verify-task \
  --dispatch "${ROUTE_D_PLUS_DISPATCH}" \
  --task-id "${task_id}"
