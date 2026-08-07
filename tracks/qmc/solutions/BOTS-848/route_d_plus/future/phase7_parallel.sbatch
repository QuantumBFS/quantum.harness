#!/usr/bin/env bash
#SBATCH --job-name=rdp-phase7
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=14
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH --time=02:00:00

set -euo pipefail

: "${ROUTE_D_PLUS_REPO_ROOT:?set the remote repository root}"
: "${ROUTE_D_PLUS_DISPATCH:?set the immutable Phase 7 dispatch}"
: "${ROUTE_D_PLUS_WORKER:?set the Phase 7 worker executable}"

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
if [[ "${#task_rows[@]}" -ne 7 ]]; then
  echo "Phase 7 requires exactly seven isolated tasks" >&2
  exit 2
fi

pids=()
for row in "${task_rows[@]}"; do
  IFS=$'\t' read -r task_id run_dir <<<"${row}"
  mkdir -p "${run_dir}"
  srun --exclusive --nodes=1 --ntasks=1 --cpus-per-task=2 \
    "${ROUTE_D_PLUS_WORKER}" \
    --dispatch "${ROUTE_D_PLUS_DISPATCH}" \
    --task-id "${task_id}" \
    --run-dir "${run_dir}" \
    >"${run_dir}/stdout.log" 2>"${run_dir}/stderr.log" &
  pids+=("$!")
done

status=0
for pid in "${pids[@]}"; do
  if ! wait "${pid}"; then
    status=1
  fi
done
if [[ "${status}" -eq 0 ]]; then
  for row in "${task_rows[@]}"; do
    IFS=$'\t' read -r task_id run_dir <<<"${row}"
    "${python}" -m route_d_plus.future.verify verify-task \
      --dispatch "${ROUTE_D_PLUS_DISPATCH}" \
      --task-id "${task_id}"
  done
fi
exit "${status}"
